"""Generuje vercel/public/data-info.json i odświeża statyczne fallbacki w stronach (bez ręcznej edycji).

Uruchamiaj po każdym odświeżeniu danych (robi to też `python aktualizuj.py`, krok `info`):

    python pipeline/build_data_info.py

Co robi:
 1. liczy daty i liczby z metadanych w dane/ (indeks_obowiazujacych.json, indeks_mp.json, indeks_ujednolicone.json),
 2. zapisuje vercel/public/data-info.json (dotychczasowe pola + `sources`, `last_update_run`, `last_update_summary`,
    `knowledge_base`),
 3. PATCHUJE blok między <!--DATA-INFO:START--> i <!--DATA-INFO:END--> w vercel/public/index.html
    (strona pokazuje aktualne daty także bez JavaScriptu),
 4. w vercel/public/podlacz.html odświeża datę (<!--ASOF:START-->…<!--ASOF:END-->) oraz prompt
    (<!--PROMPT:START-->…<!--PROMPT:END--> z ai/SYSTEM_PROMPT.md, sekcja "Wersja krótka").

Skrypt jest idempotentny: ponowne uruchomienie na tych samych danych nie zmienia żadnego pliku.
Brak znaczników w pliku HTML = ostrzeżenie, plik pozostaje nietknięty.

Opcje (przydatne do testów na kopii): --dane --stan --zrodla --out --index --podlacz --prompt-src --wiedza
--dry-run (nic nie zapisuje) --json (wypisz cały data-info.json) --quiet.
"""
import argparse
import html
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

START = "<!--DATA-INFO:START-->"
END = "<!--DATA-INFO:END-->"
ASOF_START, ASOF_END = "<!--ASOF:START-->", "<!--ASOF:END-->"
PROMPT_START, PROMPT_END = "<!--PROMPT:START-->", "<!--PROMPT:END-->"

# Lista awaryjna, gdy brak zrodla/sources.json (kontrakt: docs/UPDATE_SPEC.md, sekcja źródeł dodatkowych).
DEFAULT_SOURCES = [
    {"id": "eli-du", "nazwa": "Dziennik Ustaw (ELI Sejmu)", "status": "aktywne", "enabled": True,
     "opis": "Obowiązujące akty z Dz.U.: ustawy, rozporządzenia, umowy międzynarodowe."},
    {"id": "eli-mp", "nazwa": "Monitor Polski (ELI Sejmu)", "status": "aktywne", "enabled": True,
     "opis": "Obowiązujące akty z M.P.: uchwały, zarządzenia, obwieszczenia."},
    {"id": "isap-ujednolicone", "nazwa": "Teksty ujednolicone (ISAP)", "status": "aktywne", "enabled": True,
     "opis": "Teksty jednolite ustaw i rozporządzeń uwzględniające nowelizacje."},
    {"id": "saos", "nazwa": "Orzecznictwo sądów (SAOS)", "status": "uśpione", "enabled": False,
     "opis": "Orzeczenia sądów z bazy SAOS – dodane do repozytorium, jeszcze nie włączone."},
    {"id": "eurlex", "nazwa": "Prawo UE (EUR-Lex)", "status": "uśpione", "enabled": False,
     "opis": "Akty prawa Unii Europejskiej z EUR-Lex – dodane do repozytorium, jeszcze nie włączone."},
    {"id": "tk", "nazwa": "Trybunał Konstytucyjny", "status": "planowane", "enabled": False,
     "opis": "Orzeczenia Trybunału Konstytucyjnego – w planach."},
    {"id": "sn", "nazwa": "Sąd Najwyższy", "status": "planowane", "enabled": False,
     "opis": "Orzeczenia Sądu Najwyższego – w planach."},
    {"id": "nsa", "nazwa": "Naczelny Sąd Administracyjny", "status": "planowane", "enabled": False,
     "opis": "Orzeczenia sądów administracyjnych – w planach."},
]
BUILTIN_IDS = ("eli-du", "eli-mp", "isap-ujednolicone")
STATUSES = ("aktywne", "uśpione", "planowane")


def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text("utf-8"))
    except (OSError, ValueError):
        return default


def latest(items):
    if not items:            # zakres.json moze nie obejmowac danej kategorii (np. M.P.)
        return None
    return max(items, key=lambda x: (x.get("promulgation") or "", x.get("pos") or 0))


def fmt_date(iso):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", iso or "")
    return f"{m.group(3)}.{m.group(2)}.{m.group(1)}" if m else (iso or "")


def fmt_num(n):
    return f"{n:,}".replace(",", "&nbsp;")


def esc(text):
    return html.escape(str(text), quote=False)


def read_text_raw(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read()


def write_text_raw(path, text):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


# ---------------------------------------------------------------- źródła
def normalize_sources(raw):
    if isinstance(raw, dict):
        raw = raw.get("sources") or raw.get("zrodla") or []
    if not isinstance(raw, list) or not raw:
        return [dict(s) for s in DEFAULT_SOURCES]
    return [s for s in raw if isinstance(s, dict) and s.get("id")]


def effective_status(entry):
    """Status wyliczany z `enabled` i `status` (źródło planowane zostaje planowane)."""
    declared = entry.get("status")
    enabled = entry.get("enabled")
    if enabled is None:
        enabled = entry.get("id") in BUILTIN_IDS
    if declared == "planowane":
        return "planowane", bool(enabled)
    return ("aktywne" if enabled else "uśpione"), bool(enabled)


def build_sources(raw_sources, stan_dir, du, mp, uj):
    out = []
    for e in normalize_sources(raw_sources):
        sid = e["id"]
        status, enabled = effective_status(e)
        count = newest = None
        if sid == "eli-du":
            count, newest = len(du), (latest(du) or {}).get("promulgation")
        elif sid == "eli-mp":
            count, newest = len(mp), (latest(mp) or {}).get("promulgation")
        elif sid == "isap-ujednolicone":
            count, newest = len(uj), (latest(uj) or {}).get("promulgation")
        else:
            st = load_json(stan_dir / f"zrodlo_{sid}.json", {}) or {}
            if isinstance(st.get("count"), int):
                count = st["count"]
            newest = st.get("newest_date") or None
        item = {
            "id": sid,
            "nazwa": e.get("nazwa") or sid,
            "status": status,
            "enabled": enabled,
            "count": count,
            "newest_date": newest,
        }
        if e.get("opis"):
            item["opis"] = e["opis"]
        out.append(item)
    return out


def build_not_covered(sources):
    active = {s["id"] for s in sources if s["status"] == "aktywne"}
    items = ["akty uchylone i wygasłe"]
    if "eurlex" not in active:
        items.append("prawo UE")
    if "saos" not in active:
        items.append("orzecznictwo sądów (poza wyrokami TK ogłaszanymi w Dz.U.)")
    else:
        items.append("orzecznictwo spoza włączonych źródeł (część orzeczeń może nie być załadowana)")
    items.append("akty prawa miejscowego i dzienniki wojewódzkie")
    items.append("akty ogłoszone po dacie stanu danych")
    return items


# ---------------------------------------------------------------- ostatnia aktualizacja
def last_update(stan_dir):
    """(ISO czas, podsumowanie) z stan/zmiany.json lub stan/ostatnia_aktualizacja.json."""
    zm = load_json(stan_dir / "zmiany.json")
    run_at = summary = None
    if isinstance(zm, dict):
        run_at = zm.get("run_at")
        summary = {
            "added": len(zm.get("added") or []),
            "changed": len(zm.get("changed") or []),
            "removed": len(zm.get("removed") or []),
            "unchanged": zm.get("unchanged"),
        }
    if not run_at:
        oa = load_json(stan_dir / "ostatnia_aktualizacja.json")
        if isinstance(oa, dict):
            for k in ("run_at", "finished_at", "koniec", "zakonczono", "timestamp", "czas", "data"):
                if isinstance(oa.get(k), str) and oa[k]:
                    run_at = oa[k]
                    break
    return run_at, summary


# ---------------------------------------------------------------- blok HTML dla index.html
def render_index_block(info, nl="\n"):
    L = []
    L.append(f'  <p class="asof" id="asof">Stan danych na dzień {fmt_date(info["data_as_of"])}</p>')
    L.append('  <dl class="grid">')

    def stat(label, dd_id, main, small=None, small_id=None):
        sm = ""
        if small:
            sm = f'<small id="{small_id}">{esc(small)}</small>' if small_id else f"<small>{esc(small)}</small>"
        return f'    <div class="stat"><dt>{label}</dt><dd id="{dd_id}">{main}{sm}</dd></div>'

    d, m, c = info["dz_u"], info["m_p"], info["consolidated_texts"]
    L.append(stat("Najnowszy akt Dz.U.", "dzu", esc(d["latest_act"]),
                  f'ogłoszony {fmt_date(d["latest_promulgation_date"])}' if d.get("latest_promulgation_date") else None))
    L.append(stat("Najnowszy akt M.P.", "mp", esc(m["latest_act"]),
                  f'ogłoszony {fmt_date(m["latest_promulgation_date"])}' if m.get("latest_promulgation_date") else None))
    L.append(stat("Dokumenty Dz.U.", "n-dzu", fmt_num(d["documents"])))
    L.append(stat("Dokumenty M.P.", "n-mp", fmt_num(m["documents"])))
    cons_small = "najnowszy: " + c["latest_act_with_consolidated_text"]
    if c.get("latest_promulgation_date_among_them"):
        cons_small += f' ({fmt_date(c["latest_promulgation_date_among_them"])})'
    L.append(stat("Teksty ujednolicone", "n-cons", fmt_num(c["documents"]), cons_small, "cons-latest"))
    L.append("  </dl>")
    L.append(f'  <p class="note" id="cons-note"><strong>Teksty ujednolicone:</strong> {esc(c["note"])}</p>')
    if info.get("last_update_run"):
        L.append(f'  <p class="note" id="last-run">Ostatnia aktualizacja danych: {fmt_date(info["last_update_run"])}.</p>')
    L.append("  <h3>Czego nie obejmuje</h3>")
    L.append('  <ul class="plain" id="notcov">')
    for t in info["not_covered"]:
        L.append(f"    <li>{esc(t)}</li>")
    L.append("  </ul>")
    L.append("  <h3>Źródła danych</h3>")
    L.append('  <ul class="srclist" id="sources">')
    for s in info["sources"]:
        label = "wkrótce" if s["status"] == "planowane" else s["status"]
        parts = []
        if isinstance(s.get("count"), int):
            parts.append(f'{fmt_num(s["count"])} dokumentów')
        if s.get("newest_date"):
            parts.append(f'najnowszy z {fmt_date(s["newest_date"])}')
        tail = esc(", ".join(parts)).replace("&amp;nbsp;", "&nbsp;") if parts else ""
        desc = f'<span class="d">{esc(s["opis"])}</span>' if s.get("opis") else ""
        L.append(f'    <li><strong>{esc(s["nazwa"])}</strong><span class="st st-{s["status"]}">{label}</span>{tail}{desc}</li>')
    L.append("  </ul>")
    return nl.join(L)


def patch_between(text, start, end, content, pad_nl=None):
    """Zamienia wszystko między znacznikami. pad_nl=None: bez dodatkowych łamań linii."""
    i = text.find(start)
    j = text.find(end, i + len(start)) if i >= 0 else -1
    if i < 0 or j < 0:
        return None
    if pad_nl is None:
        return text[: i + len(start)] + content + text[j:]
    return text[: i + len(start)] + pad_nl + content + pad_nl + "  " + text[j:]


def patch_all_between(text, start, end, content):
    """Zamienia treść między KAŻDĄ parą znaczników; zwraca (tekst, liczba_zamian)."""
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    new, n = pattern.subn(lambda _m: start + content + end, text)
    return new, n


def extract_short_prompt(path):
    text = read_text_raw(path).replace("\r\n", "\n")
    i = text.find("## Wersja krótka")
    if i < 0:
        return None
    m = re.search(r"```[^\n]*\n(.*?)\n```", text[i:], re.S)
    return m.group(1) if m else None


# ---------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dane", default=str(ROOT / "dane"))
    ap.add_argument("--stan", default=str(ROOT / "stan"))
    ap.add_argument("--zrodla", default=str(ROOT / "zrodla" / "sources.json"))
    ap.add_argument("--out", default=str(ROOT / "vercel" / "public" / "data-info.json"))
    ap.add_argument("--index", default=str(ROOT / "vercel" / "public" / "index.html"))
    ap.add_argument("--podlacz", default=str(ROOT / "vercel" / "public" / "podlacz.html"))
    ap.add_argument("--prompt-src", default=str(ROOT / "ai" / "SYSTEM_PROMPT.md"))
    ap.add_argument("--wiedza", default=str(ROOT / "vercel" / "public" / "wiedza" / "index.json"))
    ap.add_argument("--chunks", default=str(ROOT / "pipeline" / "out" / "chunks.jsonl"))
    ap.add_argument("--dry-run", action="store_true", help="nic nie zapisuj, tylko pokaż co by się zmieniło")
    ap.add_argument("--json", action="store_true", help="wypisz cały data-info.json")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    dane, stan = Path(a.dane), Path(a.stan)
    names = ("indeks_obowiazujacych.json", "indeks_mp.json", "indeks_ujednolicone.json")
    missing = [n for n in names if not (dane / n).exists()]
    if missing:
        print(f"BŁĄD: brak plików indeksów w {dane}: {', '.join(missing)}", file=sys.stderr)
        return 2
    du, mp, uj = (json.loads((dane / n).read_text("utf-8")) for n in names)
    # data pobrania = czas zapisu najświeższego pliku z metadanymi
    pobrano_dt = datetime.fromtimestamp(max((dane / n).stat().st_mtime for n in names), timezone.utc)
    # data stanu = ostatnie UDANE, pelne sprawdzenie API (stan/zmiany.json), jesli nowsze niz zapis indeksow
    # (indeksy sa zapisywane tylko przy zmianie, wiec same nie odzwierciedlaja dnia sprawdzenia)
    _zm = load_json(stan / "zmiany.json")
    if isinstance(_zm, dict) and _zm.get("run_at") and not _zm.get("dry_run") and not _zm.get("partial") \
            and not _zm.get("bootstrap"):
        try:
            _t = datetime.fromisoformat(str(_zm["run_at"]).replace("Z", "+00:00"))
            if _t.tzinfo is None:
                _t = _t.replace(tzinfo=timezone.utc)
            if _t > pobrano_dt:
                pobrano_dt = _t.astimezone(timezone.utc)
        except ValueError:
            pass

    l_du, l_mp, l_uj = latest(du), latest(mp), latest(uj)
    _zakres = load_json(ROOT / "zakres.json", {}) or {}
    zakres_n = len(_zakres.get("akty") or []) if isinstance(_zakres, dict) else 0
    sources = build_sources(load_json(a.zrodla), stan, du, mp, uj)
    run_at, run_summary = last_update(stan)

    info = {
        "data_as_of": pobrano_dt.date().isoformat(),
        "downloaded_at_utc": pobrano_dt.isoformat(timespec="minutes"),
        "source": "API ELI Sejmu RP (https://api.sejm.gov.pl/eli)",
        "scope": (f"Tylko akty z zakres.json ({zakres_n} aktów; obowiązujące + teksty ujednolicone ISAP)"
                  if zakres_n else
                  "Dz.U. i M.P. – tylko akty o statusie 'obowiązujący' (+ teksty ujednolicone ISAP)"),
        "dz_u": {
            "documents": len(du),
            "latest_act": l_du["displayAddress"] if l_du else None,
            "latest_promulgation_date": l_du.get("promulgation") if l_du else None,
            "latest_api_change_date": max((x.get("changeDate") or "" for x in du), default="")[:10],
        },
        "m_p": {
            "documents": len(mp),
            "latest_act": l_mp["displayAddress"] if l_mp else None,
            "latest_promulgation_date": l_mp.get("promulgation") if l_mp else None,
        },
        "consolidated_texts": {
            "documents": len(uj),
            "latest_act_with_consolidated_text": l_uj["displayAddress"] if l_uj else None,
            "latest_promulgation_date_among_them": l_uj.get("promulgation") if l_uj else None,
            "note": "Tekst ujednolicony odzwierciedla stan prawny na dzień jego sporządzenia; zmiany ogłoszone później mogą nie być w nim ujęte.",
        },
        "categories": dict(Counter(x.get("kategoria") for x in du + mp + uj)),
        "sources": sources,
        "last_update_run": run_at,
        "not_covered": build_not_covered(sources),
        "legal_notice": "Narzędzie pomocnicze, nie porada prawna. Aktualne brzmienie przepisu zawsze zweryfikuj w ISAP (isap.sejm.gov.pl).",
    }
    if run_summary is not None:
        info["last_update_summary"] = run_summary
    chunks = Path(a.chunks)
    if chunks.exists():
        info["indexed_chunks_file_mb"] = round(chunks.stat().st_size / 1e6, 1)
    wiedza = load_json(a.wiedza)
    if isinstance(wiedza, list):
        info["knowledge_base"] = {"index": "/wiedza/index.json", "entries": len(wiedza)}

    log = None if a.quiet else []
    changed = []

    def save(path, text, label):
        p = Path(path)
        old = read_text_raw(p) if p.exists() else None
        if old == text:
            if log is not None:
                log.append(f"  bez zmian: {label}")
            return
        changed.append(label)
        if not a.dry_run:
            p.parent.mkdir(parents=True, exist_ok=True)
            write_text_raw(p, text)
        if log is not None:
            log.append(f"  {'zmieniłby się' if a.dry_run else 'zapisano'}: {label}")

    save(a.out, json.dumps(info, ensure_ascii=False, indent=2), "data-info.json")

    # index.html – blok fallbacku
    ip = Path(a.index)
    if ip.exists():
        text = read_text_raw(ip)
        nl = "\r\n" if "\r\n" in text else "\n"
        new = patch_between(text, START, END, render_index_block(info, nl), pad_nl=nl)
        if new is None:
            print(f"OSTRZEŻENIE: brak znaczników {START} / {END} w {ip.name} – fallback nie został zaktualizowany.", file=sys.stderr)
        else:
            save(ip, new, ip.name)
    else:
        print(f"OSTRZEŻENIE: brak pliku {ip}", file=sys.stderr)

    # podlacz.html – data i prompt
    pp = Path(a.podlacz)
    if pp.exists():
        text = read_text_raw(pp)
        text, n_asof = patch_all_between(text, ASOF_START, ASOF_END, fmt_date(info["data_as_of"]))
        if n_asof == 0:
            print(f"OSTRZEŻENIE: brak znaczników {ASOF_START} w {pp.name}.", file=sys.stderr)
        prompt = extract_short_prompt(a.prompt_src) if Path(a.prompt_src).exists() else None
        if prompt is None:
            print(f"OSTRZEŻENIE: nie znaleziono sekcji 'Wersja krótka' z blokiem kodu w {a.prompt_src} – prompt nie został zaktualizowany.", file=sys.stderr)
        else:
            p_new = patch_between(text, PROMPT_START, PROMPT_END, esc(prompt))
            if p_new is None:
                print(f"OSTRZEŻENIE: brak znaczników {PROMPT_START} w {pp.name}.", file=sys.stderr)
            else:
                text = p_new
        save(pp, text, pp.name)
    else:
        print(f"OSTRZEŻENIE: brak pliku {pp}", file=sys.stderr)

    if a.json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
    if log is not None:
        print(f"Stan danych na dzień {fmt_date(info['data_as_of'])}; "
              f"Dz.U.: {info['dz_u']['latest_act']} ({fmt_date(info['dz_u']['latest_promulgation_date'])}); "
              f"M.P.: {info['m_p']['latest_act']} ({fmt_date(info['m_p']['latest_promulgation_date'])})")
        akt = [s["id"] for s in sources if s["status"] == "aktywne"]
        usp = [s["id"] for s in sources if s["status"] == "uśpione"]
        print(f"Źródła aktywne: {', '.join(akt) or '-'}; uśpione: {', '.join(usp) or '-'}; "
              f"ostatnia aktualizacja: {fmt_date(run_at) if run_at else 'brak danych'}")
        print("\n".join(log))
    return 0


if __name__ == "__main__":
    sys.exit(main())
