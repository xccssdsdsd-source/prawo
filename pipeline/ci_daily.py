"""Dzienna, w pelni automatyczna aktualizacja (GitHub Actions) - zwykly Python, bez udzialu AI.

Kroki:
  1. update_data.py --ci     : porownanie z API Sejmu wg ci_stan/manifest.json, pobranie TYLKO nowych/zmienionych aktow
  2. export_chunks.py        : podzial zmienionych aktow na artykuly (delta)
  3. load_to_postgres.py     : synchronizacja bazy (usun zmienione/wycofane, zaladuj nowe/zmienione)
  4. build_data_info.py      : nowy vercel/public/data-info.json + daty w index.html / podlacz.html

Zatwierdzenie zmian (commit + push) robi workflow YAML - dopiero po sukcesie WSZYSTKICH krokow, wiec manifest
nigdy nie wyprzedza bazy. Przy bledzie nic nie jest zatwierdzane, a nastepny przebieg powtarza prace
(operacje sa idempotentne).

Zmienne srodowiskowe:
  DATABASE_URL   (wymagana, chyba ze --bez-bazy)  - connection string Postgresa (sekret GitHub Actions)
  DB_MAX_MB      (opcjonalna, domyslnie 450)      - limit rozmiaru bazy dla NOWYCH dokumentow
Kody wyjscia: 0 ok, 1 blad kroku, 2 brak konfiguracji (np. DATABASE_URL), 3 zablokowane ze wzgledow bezpieczenstwa.

Uzycie lokalne (test):  python pipeline/ci_daily.py --dane TMP/dane --stan TMP/stan --out TMP/out --bez-bazy
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)


def run(cmd, what):
    log(f"=== {what}: {' '.join(str(c) for c in cmd)}")
    rc = subprocess.call([str(c) for c in cmd], cwd=ROOT)
    log(f"=== {what}: kod wyjscia {rc}")
    return rc


def summary(lines):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    text = "\n".join(lines) + "\n"
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text)
    print(text)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dane", default=str(ROOT / "dane"))
    ap.add_argument("--stan", default=str(ROOT / "ci_stan"))
    ap.add_argument("--out", default=str(ROOT / "pipeline" / "out"), help="katalog na chunks.jsonl i chunks_delta.jsonl")
    ap.add_argument("--bez-bazy", action="store_true", help="pomin ladowanie do Postgresa (testy)")
    ap.add_argument("--force-removals", action="store_true")
    ap.add_argument("--max-akty", type=int, default=None, help="limit pobran (testy)")
    ap.add_argument("--lata", default=None, help="np. 2026 (testy)")
    ap.add_argument("--bez-info", action="store_true", help="pomin build_data_info (testy)")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    stan, out = Path(a.stan), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if not (stan / "manifest.json").exists():
        log(f"BLAD: brak {stan / 'manifest.json'}. Pierwszy manifest tworzy sie lokalnie: "
            "python pipeline/update_data.py --bootstrap --hash --stan ci_stan  (potem commit ci_stan/manifest.json).")
        return 2
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not a.bez_bazy and not db_url:
        log("BLAD: brak sekretu DATABASE_URL (GitHub: Settings > Secrets and variables > Actions). "
            "Bez bazy aktualizacja nie ma sensu - manifest wyprzedzilby baze.")
        return 2

    # 1. dane
    cmd = [PY, "pipeline/update_data.py", "--ci", "--dane", a.dane, "--stan", a.stan]
    if a.force_removals:
        cmd.append("--force-removals")
    if a.max_akty is not None:
        cmd += ["--max-akty", a.max_akty]
    if a.lata:
        cmd += ["--lata", a.lata]
    rc = run(cmd, "1/4 dane")
    if rc != 0:
        log("PRZERWANO: aktualizacja danych nie powiodla sie - nic nie zostanie zatwierdzone.")
        return 3 if rc == 3 else 1
    zm = json.loads((stan / "zmiany.json").read_text("utf-8"))
    n_add, n_chg, n_rem = len(zm.get("added") or []), len(zm.get("changed") or []), len(zm.get("removed") or [])
    log(f"Zmiany: nowe {n_add}, zmienione {n_chg}, wycofane {n_rem}, bez zmian {zm.get('unchanged')}")

    # 2-3. eksport + baza (tylko gdy cos sie zmienilo)
    if n_add or n_chg or n_rem:
        chunks = out / "chunks.jsonl"
        rc = run([PY, "pipeline/export_chunks.py", "--changed", stan / "zmiany.json", "--out", chunks,
                  "--dane", a.dane], "2/4 eksport")
        if rc != 0:
            return 1
        if not a.bez_bazy:
            cmd = [PY, "pipeline/load_to_postgres.py", "--sync", stan / "zmiany.json",
                   "--input", out / "chunks_delta.jsonl", "--max-mb", os.environ.get("DB_MAX_MB") or "450"]
            rc = run(cmd, "3/4 baza")
            if rc != 0:
                return 1
        else:
            log("3/4 baza: pominieto (--bez-bazy)")
    else:
        log("2-3/4: brak zmian - eksport i baza pominiete")

    # 4. data-info
    if not a.bez_info:
        rc = run([PY, "pipeline/build_data_info.py", "--dane", a.dane, "--stan", a.stan], "4/4 data-info")
        if rc != 0:
            return 1

    lines = ["## Dzienna aktualizacja danych", "",
             f"- Nowe akty: **{n_add}**, zmienione: **{n_chg}**, wycofane: **{n_rem}**, bez zmian: {zm.get('unchanged')}",
             f"- Najnowsze: {json.dumps(zm.get('latest') or {}, ensure_ascii=False)}"]
    if zm.get("failed"):
        lines.append(f"- UWAGA: {len(zm['failed'])} aktow nie udalo sie pobrac (zostana ponowione jutro)")
    for w in (zm.get("warnings") or [])[:10]:
        lines.append(f"- Ostrzezenie: {w}")
    summary(lines)
    return 0


if __name__ == "__main__":
    sys.exit(main())
