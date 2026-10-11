#!/usr/bin/env python3
"""ZYWY test fetcherow (kilka zapytan do kazdego serwisu, zapis do katalogu tymczasowego - nie rusza stan/ ani pipeline/out/).

  python zrodla/tests/live_check.py [--eurlex] [--saos] [--keep]

Dla kazdego zrodla uruchamia fetch.py z --force --limit 5 i sprawdza wynik:
  * kazdy wiersz jest poprawnym JSON-em zgodnym z docs/SPEC.md (_common.validate_chunk), doc_id jest pierwszym kluczem,
  * brak znakow zastepczych U+FFFD, sa polskie znaki diakrytyczne (na poziomie kodow Unicode) i brak sladow mojibake,
  * pipeline/load_to_postgres.py --dry-run akceptuje plik,
  * statystyki: dokumenty, fragmenty, srednia dlugosc tekstu (do szacowania rozmiaru bazy).
SAOS bywa niedostepny (HTTP 200 z HTML 'Przerwa techniczna') - wtedy wynik to SKIP, a nie blad.
"""
import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ZR = Path(__file__).resolve().parents[1]
ROOT = ZR.parent
sys.path.insert(0, str(ZR))
import _common as C  # noqa: E402

PL_CHARS = "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ"
MOJIBAKE = ["Ä…", "Å‚", "Ã³", "Å›", "Ĺ‚", "Ä™", "Å¼"]


def check_output(path: Path, label: str) -> list[str]:
    """Zwraca liste problemow (pusta = OK) i wypisuje statystyki."""
    problems = []
    if not path.is_file():
        return [f"{label}: brak pliku wyjsciowego"]
    docs: dict[str, int] = {}
    total_chars = 0
    max_chunk = 0
    pl_counts = {ch: 0 for ch in PL_CHARS}
    raw_all = []
    with open(path, "rb") as f:
        for n, raw in enumerate(f, 1):
            if C.line_doc_id(raw) is None:
                problems.append(f"{label}: linia {n}: doc_id nie jest pierwszym kluczem")
                continue
            try:
                r = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                problems.append(f"{label}: linia {n}: zly JSON/UTF-8 ({e})")
                continue
            for e in C.validate_chunk(r):
                problems.append(f"{label}: {r.get('doc_id')} ord {r.get('ord')}: {e}")
            docs[r["doc_id"]] = docs.get(r["doc_id"], 0) + 1
            total_chars += len(r["text"])
            max_chunk = max(max_chunk, len(r["text"]))
            for ch in PL_CHARS:
                pl_counts[ch] += r["text"].count(ch)
            raw_all.append(r["text"])
    text = "\n".join(raw_all)
    if C.FFFD in text:
        problems.append(f"{label}: znaki zastepcze U+FFFD w tekscie ({text.count(C.FFFD)})")
    if sum(pl_counts.values()) == 0:
        problems.append(f"{label}: brak polskich znakow diakrytycznych")
    for m in MOJIBAKE:
        if m in text:
            problems.append(f"{label}: slad mojibake {m!r}")
    # spojnosc dokumentow (ord 1..n) po ponownym wczytaniu
    by_doc: dict[str, list[dict]] = {}
    with open(path, "rb") as f:
        for raw in f:
            r = json.loads(raw.decode("utf-8"))
            by_doc.setdefault(r["doc_id"], []).append(r)
    for d, rows in by_doc.items():
        for e in C.validate_rows(rows):
            problems.append(f"{label}: {d}: {e}")
    nd, nc = len(docs), sum(docs.values())
    print(f"  {label}: dokumentow {nd}, fragmentow {nc}, tekst {total_chars/1024:.0f} KB, "
          f"srednio {total_chars/max(nd,1)/1024:.1f} KB/dok., najdluzszy fragment {max_chunk} zn.")
    print("  polskie znaki (liczba wystapien, kody): "
          + ", ".join(f"{ch}=U+{ord(ch):04X}:{n}" for ch, n in pl_counts.items() if n))
    return problems


def run(cmd: list[str], timeout: int) -> tuple[int, str]:
    p = subprocess.run(cmd, capture_output=True, timeout=timeout, cwd=str(ROOT))
    return p.returncode, (p.stdout + p.stderr).decode("utf-8", errors="replace")


def loader_dry_run(path: Path) -> list[str]:
    code, out = run([sys.executable, "-X", "utf8", str(ROOT / "pipeline" / "load_to_postgres.py"), "--dry-run",
                     "--input", str(path)], 120)
    if code != 0:
        return [f"load_to_postgres --dry-run zwrocil kod {code}: {out[-300:]}"]
    print("  load_to_postgres.py --dry-run: OK")
    return []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--eurlex", action="store_true")
    ap.add_argument("--saos", action="store_true")
    ap.add_argument("--keep", action="store_true", help="nie usuwaj katalogu tymczasowego")
    a = ap.parse_args()
    both = not (a.eurlex or a.saos)
    tmp = Path(tempfile.mkdtemp(prefix="zrodla_live_"))
    print(f"Katalog tymczasowy: {tmp}")
    problems: list[str] = []
    skipped: list[str] = []
    py = [sys.executable, "-X", "utf8"]
    try:
        if a.eurlex or both:
            print("== EUR-Lex (Cellar): --limit 5")
            out = tmp / "chunks_eurlex.jsonl"
            code, log = run(py + [str(ZR / "eurlex" / "fetch.py"), "--force", "--limit", "5", "--out", str(out),
                                  "--stan-dir", str(tmp / "stan")], 900)
            print("  " + "\n  ".join(log.strip().splitlines()[-8:]))
            if code == C.EXIT_UNAVAILABLE:
                skipped.append("eurlex: zrodlo niedostepne (kod 3)")
            elif code != 0:
                problems.append(f"eurlex: fetch.py kod wyjscia {code}")
            else:
                problems += check_output(out, "eurlex") + loader_dry_run(out)
        if a.saos or both:
            print("== SAOS: --limit 5 (od 3 dni, maks. 3 strony API + slownik sadow)")
            out = tmp / "chunks_saos.jsonl"
            since = (dt.date.today() - dt.timedelta(days=3)).isoformat()
            code, log = run(py + [str(ZR / "saos" / "fetch.py"), "--force", "--limit", "5", "--typy", "wszystkie",
                                  "--since", since, "--max-stron", "3", "--delay", "3", "--out", str(out),
                                  "--stan-dir", str(tmp / "stan")], 1500)
            print("  " + "\n  ".join(log.strip().splitlines()[-6:]))
            if code == C.EXIT_UNAVAILABLE:
                skipped.append("saos: zrodlo niedostepne (kod 3) - np. 'Przerwa techniczna'")
            elif code != 0:
                problems.append(f"saos: fetch.py kod wyjscia {code}")
            elif not out.is_file():
                skipped.append("saos: zadne z pobranych orzeczen nie mialo tresci (swieze wpisy SAOS maja pusty textContent)")
            else:
                problems += check_output(out, "saos") + loader_dry_run(out)
    finally:
        if a.keep:
            print(f"Zachowano: {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    print()
    for s in skipped:
        print("SKIP:", s)
    if problems:
        print("PROBLEMY:")
        for p in problems[:40]:
            print(" -", p)
        return 1
    print("OK: wszystkie sprawdzone zrodla zgodne ze schematem" + (" (czesc pominieta)" if skipped else ""))
    return 0


if __name__ == "__main__":
    C.setup_console()
    sys.exit(main())
