#!/usr/bin/env python3
"""Fetcher orzeczen sadowych z SAOS (System Analizy Orzeczen Sadowych) - przyrostowy. Zrodlo USPIONE (enabled:false).

Uzycie:
  python zrodla/saos/fetch.py [--limit N] [--since YYYY-MM-DD] [--typy SUPREME,ADMINISTRATIVE | wszystkie]
                              [--out PLIK] [--stan-dir DIR] [--max-stron N] [--dry-run] [--force]

Jak dziala: GET https://www.saos.org.pl/api/dump/judgments?withGenerated=false&sinceModificationDate=...&pageSize=100
(tylko dodane/zmienione od daty), strony po kolei (bez rownoleglosci, z odstepem), upsert po id. Dump nie ma filtra po
rodzaju sadu, wiec filtr (opcje.typy_sadow w sources.json / --typy) dziala po stronie klienta. Wpisy z pustym textContent
(swieze) trafiaja do kolejki ponowien w stanie i sa dociagane przez GET /api/judgments/{id}.
Wynik: pipeline/out/chunks_saos.jsonl (kategoria "wyrok", doc_id "SAOS/<id>", status "orzeczenie").
Stan: stan/zrodlo_saos.json (watermark = start ostatniego KOMPLETNEGO przebiegu, count, newest_date, kolejka ponowien,
punkt wznowienia przerwanego przebiegu). Odejmujemy 2 dni zapasu od watermarku.

UWAGA: robots.txt SAOS ma 'Disallow: /api/', a dokumentacja zacheca do pobierania przez API i nie podaje limitow ani
licencji - przed wlaczeniem skontaktuj sie z operatorem SAOS (patrz zrodla/README.md). Tresci orzeczen sa anonimizowane
przez sady zrodlowe. Kody wyjscia: 0 ok, 1 blad, 3 zrodlo niedostepne (np. 'Przerwa techniczna' zamiast JSON).
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _common as C  # noqa: E402

SOURCE_ID = "saos"
BASE = "https://www.saos.org.pl"
DUMP_URL = BASE + "/api/dump/judgments"
JUDGMENT_API = BASE + "/api/judgments/{id}"
JUDGMENT_PAGE = BASE + "/judgments/{id}"
CHUNK_TARGET = 2000
SINCE_MARGIN_DAYS = 2
MAX_RETRY_ATTEMPTS = 6

DEFAULTS = {
    "typy_sadow": ["SUPREME", "ADMINISTRATIVE", "CONSTITUTIONAL_TRIBUNAL", "NATIONAL_APPEAL_CHAMBER"],
    "okno_poczatkowe_dni": 30,
    "rozmiar_strony": 100,
    "opoznienie_s": 3.0,
    "max_stron": 100,
    "max_znakow_orzeczenia": 150000,
    "max_ponowien_na_przebieg": 30,
}
ALL_TYPES = ["COMMON", "SUPREME", "ADMINISTRATIVE", "CONSTITUTIONAL_TRIBUNAL", "NATIONAL_APPEAL_CHAMBER"]
COURT_LABEL = {
    "COMMON": "Sąd powszechny", "SUPREME": "Sąd Najwyższy", "ADMINISTRATIVE": "Sąd administracyjny",
    "CONSTITUTIONAL_TRIBUNAL": "Trybunał Konstytucyjny", "NATIONAL_APPEAL_CHAMBER": "Krajowa Izba Odwoławcza",
}
JUDGMENT_LABEL = {"SENTENCE": "Wyrok", "DECISION": "Postanowienie", "RESOLUTION": "Uchwała",
                  "REGULATION": "Zarządzenie", "REASONS": "Uzasadnienie"}

_CAP = "A-ZŁŚŻŹĆŃÓ"
_LOW = "a-ząćęłńóśźż"
_WORD = rf"[{_CAP}][\w{_LOW}\-\.]*"
COURT_PATTERNS = {
    "COMMON": re.compile(rf"Sąd (?:Okręgowy|Rejonowy|Apelacyjny)(?: dla {_WORD}(?: {_WORD})?)? (?:w|we) ((?:{_WORD})(?: {_WORD}){{0,3}})"),
    "SUPREME": re.compile(r"Sąd Najwyższy"),
    "ADMINISTRATIVE": re.compile(rf"(?:Wojewódzki Sąd Administracyjny (?:w|we) ((?:{_WORD})(?: {_WORD}){{0,3}})|Naczelny Sąd Administracyjny)"),
    "CONSTITUTIONAL_TRIBUNAL": re.compile(r"Trybunał Konstytucyjny"),
    "NATIONAL_APPEAL_CHAMBER": re.compile(r"Krajowa Izba Odwoławcza"),
}
_CITY_STOP = {"Wydział", "Wydziału", "Wydziale", "Wydz.", "Sąd", "Sądu", "Izba", "Izby", "Rzeczypospolitej", "Polskiej",
              "Karny", "Cywilny", "Pracy", "Gospodarczy", "Rodzinny", "Ośrodek", "Zamiejscowy", "Na", "Dnia", "Dnia:"}


def _trim_city(words: str) -> str:
    out = []
    for w in words.split(" "):
        if w in _CITY_STOP or re.fullmatch(r"[IVXL]+\.?", w) or w.isdigit():
            break
        out.append(w.rstrip("."))
    return " ".join(out)


# ------------------------------------------------------------------ budowanie wierszy

def date_pl(iso: str | None) -> str:
    if iso and re.match(r"^\d{4}-\d{2}-\d{2}$", iso):
        return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}"
    return iso or ""


def guess_court(court_type: str, text: str) -> str:
    """Nazwa sadu z poczatku tresci (heurystyka, gdy brak slownika sadow); inaczej ogolna etykieta rodzaju sadu."""
    pat = COURT_PATTERNS.get(court_type)
    if pat:
        m = pat.search(text[:2500])
        if m:
            full = m.group(0)
            if m.lastindex:
                city = _trim_city(m.group(1))
                if not city:
                    return COURT_LABEL.get(court_type, "Sąd")
                full = full[:m.start(1) - m.start(0)] + city
            return full
    return COURT_LABEL.get(court_type, "Sąd")


def original_url(item: dict) -> str | None:
    u = ((item.get("source") or {}).get("judgmentUrl") or "").strip()
    return u if u.startswith(("http://", "https://")) else None


def resolve_court(item: dict, text: str, courts: dict | None) -> tuple[str, str]:
    """-> (nazwa sadu, wydzial/izba lub ''). Slownik sadow z API SAOS (division.id), a gdy brak - heurystyka z tresci."""
    ctype = item.get("courtType") or ""
    div = (item.get("division") or {}).get("id")
    if courts and div is not None:
        if ctype == "COMMON":
            c = (courts.get("common") or {}).get(str(div))
            if c:
                return c["court"], c.get("division", "")
        elif ctype == "SUPREME":
            d = (courts.get("sc") or {}).get(str(div))
            if d:
                return "Sąd Najwyższy", d
    return guess_court(ctype, text), ""


def build_meta_text(item: dict, court: str, sygn: str, original: str | None, division: str = "") -> str:
    jt = JUDGMENT_LABEL.get(item.get("judgmentType"), "Orzeczenie")
    lines = [f"Orzeczenie: {jt}. Sąd: {court}." + (f" Wydział/izba: {division}." if division else "")
             + f" Sygnatura: {sygn}. Data orzeczenia: {date_pl(item.get('judgmentDate'))}."]
    regs = []
    for r in (item.get("referencedRegulations") or [])[:15]:
        y, n, e = r.get("journalYear"), r.get("journalNo"), r.get("journalEntry")
        if isinstance(y, int) and isinstance(e, int):
            label = f"Dz.U. {y}" + (f" nr {n}" if n else "") + f" poz. {e}"
            title = re.sub(r"\s+", " ", str(r.get("journalTitle") or "")).strip()
            regs.append(f"{label} (DU/{y}/{e})" + (f" – {title}" if title else ""))
    if regs:
        lines.append("Powołane akty: " + "; ".join(regs) + ".")
    bases = [re.sub(r"\s+", " ", str(b)).strip() for b in (item.get("legalBases") or [])[:10]]
    bases = [b for b in bases if b]
    if bases:
        lines.append("Podstawy prawne: " + "; ".join(bases) + ".")
    kws = [re.sub(r"\s+", " ", str(k)).strip() for k in (item.get("keywords") or [])[:15]]
    kws = [k for k in kws if k]
    if kws:
        lines.append("Słowa kluczowe: " + "; ".join(kws) + ".")
    src = f"Źródło: SAOS, orzeczenie nr {item.get('id')}"
    lines.append(src + (f"; oryginał: {original}." if original else "."))
    return "\n".join(lines)


def item_to_rows(item: dict, types: set[str], max_chars: int, courts: dict | None = None) -> tuple[list[dict] | None, str]:
    """-> (wiersze, powod). powod: 'ok' | 'typ' (odfiltrowany) | 'pusty' (brak tresci) | 'zly' (niepoprawny rekord)."""
    try:
        jid = int(item["id"])
    except (KeyError, TypeError, ValueError):
        return None, "zly"
    ctype = item.get("courtType") or ""
    if types and ctype not in types:
        return None, "typ"
    html = item.get("textContent") or ""
    text, _ = C.clean_text(C.html_to_text(html)) if html.strip() else ("", 0)
    if len(text.strip()) < 20:
        return None, "pusty"
    cases = [str(c.get("caseNumber")).strip() for c in (item.get("courtCases") or []) if c.get("caseNumber")]
    sygn = ", ".join(cases) if cases else f"SAOS {jid}"
    date = item.get("judgmentDate") if re.match(r"^\d{4}-\d{2}-\d{2}$", str(item.get("judgmentDate") or "")) else None
    court, division = resolve_court(item, text, courts)
    original = original_url(item)
    page = JUDGMENT_PAGE.format(id=jid)
    # source_url: oryginal u zrodla, jesli to strona czytelna dla czlowieka; adresy backendu XML portalu (ncourt-api)
    # i brak adresu -> strona orzeczenia w SAOS (zawiera odnosnik do oryginalu)
    src_url = original if original and "ncourt-api" not in original else page
    jt = JUDGMENT_LABEL.get(item.get("judgmentType"), "Orzeczenie")
    title = f"{jt} – {court}, sygn. {sygn}, {date_pl(date)}".rstrip(", ")
    meta = {
        "doc_id": f"SAOS/{jid}", "eli": f"SAOS/{jid}", "kategoria": "wyrok", "publisher": "SAOS",
        "year": int(date[:4]) if date else None, "pos": jid, "title": title,
        "display_address": f"{court}, sygn. {sygn}, {date_pl(date)} (SAOS {jid})",
        "announcement_date": date, "status": "orzeczenie", "is_consolidated": False, "source_url": src_url,
    }
    heading = f"{court}, sygn. {sygn}, {date_pl(date)}"
    if len(text) > max_chars:
        cut = text.rfind("\n", 0, max_chars)
        text = text[:cut if cut > max_chars // 2 else max_chars].rstrip()
        text += f"\n[… dalsza część orzeczenia pominięta (limit rozmiaru); pełny tekst: {page}]"
    rows = []
    meta_text, _ = C.clean_text(build_meta_text(item, court, sygn, original, division))
    rows.append(C.make_row(meta, 1, None, heading, meta_text))
    for part in C.split_text(text, CHUNK_TARGET):
        rows.append(C.make_row(meta, len(rows) + 1, None, heading, part))
    errs = C.validate_rows(rows)
    if errs:
        C.warn(f"SAOS/{jid}: {errs[:2]}")
        return None, "zly"
    return rows, "ok"


# ------------------------------------------------------------------ slownik sadow (division.id -> nazwa)

COURTS_FILE = "zrodlo_saos_sady.json"
COURTS_MAX_AGE_DAYS = 30


def fetch_courts(limiter: C.RateLimiter) -> dict:
    """/api/dump/commonCourts (strony) + /api/dump/scChambers -> {'common': {division_id: {court, division}}, 'sc': {division_id: nazwa}}."""
    common: dict = {}
    url = f"{BASE}/api/dump/commonCourts?pageSize=100&pageNumber=0"
    for _ in range(30):
        data = get_json(url, limiter)
        for c in data.get("items") or []:
            for d in c.get("divisions") or []:
                if d.get("id") is not None and c.get("name"):
                    common[str(d["id"])] = {"court": c["name"], "division": d.get("name") or ""}
        url = next_link(data)
        if not url:
            break
    sc: dict = {}
    for ch in get_json(f"{BASE}/api/dump/scChambers", limiter).get("items") or []:
        for d in ch.get("divisions") or []:
            if d.get("id") is not None:
                sc[str(d["id"])] = d.get("fullName") or f"{ch.get('name', '')} {d.get('name', '')}".strip()
    return {"common": common, "sc": sc}


def load_courts(limiter: C.RateLimiter, stan_dir: Path | None) -> dict | None:
    """Slownik sadow z cache (stan/zrodlo_saos_sady.json, odswiezany co 30 dni). Blad -> None (dziala heurystyka)."""
    p = Path(stan_dir or C.DEFAULT_STAN_DIR) / COURTS_FILE
    try:
        if p.is_file():
            d = json.loads(p.read_text(encoding="utf-8"))
            age = (dt.date.today() - dt.date.fromisoformat(d.get("fetched", "1970-01-01"))).days
            if d.get("common") and age < COURTS_MAX_AGE_DAYS:
                return d
        d = fetch_courts(limiter)
        d["fetched"] = dt.date.today().isoformat()
        C.atomic_write_json(p, d)
        return d
    except (C.FetchError, OSError, ValueError, KeyError) as e:
        C.warn(f"slownik sadow niedostepny ({e}) - nazwy sadow z heurystyki")
        return None


# ------------------------------------------------------------------ zapytania

def dump_url(since_iso: str, page: int, page_size: int) -> str:
    q = urllib.parse.urlencode({"pageSize": page_size, "pageNumber": page, "withGenerated": "false",
                                "sinceModificationDate": since_iso})
    return f"{DUMP_URL}?{q}"


def next_link(data: dict) -> str | None:
    for l in data.get("links") or []:
        if l.get("rel") == "next" and l.get("href"):
            h = l["href"]
            if h.startswith("http://"):
                h = "https://" + h[len("http://"):]
            return h if urllib.parse.urlparse(h).hostname == "www.saos.org.pl" else None
    return None


def get_json(url: str, limiter: C.RateLimiter) -> dict:
    r = C.http_get(url, expect="json", headers={"Accept": "application/json"}, timeout=150, retries=2,
                   backoff=20.0, retry_unexpected=2, limiter=limiter)
    return r.json()


def since_param(d: dt.date | dt.datetime) -> str:
    if isinstance(d, dt.datetime):
        return d.strftime("%Y-%m-%dT%H:%M:%S.000")
    return d.strftime("%Y-%m-%dT00:00:00.000")


# ------------------------------------------------------------------ glowny przebieg

def prune_retry(retry: dict, today: dt.date) -> dict:
    """Kolejka ponowien: bez wpisow wyczerpanych/starszych niz 60 dni, maks. 2000 najnowszych (utracone wpisy wroca
    przy kolejnej modyfikacji rekordu w SAOS - dump zwraca je przez sinceModificationDate)."""
    keep = {}
    for k, v in retry.items():
        try:
            age = (today - dt.date.fromisoformat(v.get("od", today.isoformat()))).days
        except ValueError:
            age = 0
        if v.get("n", 0) < MAX_RETRY_ATTEMPTS and age <= 60:
            keep[k] = v
    if len(keep) > 2000:
        keep = dict(sorted(keep.items(), key=lambda kv: kv[1].get("od", ""), reverse=True)[:2000])
    return keep


def resolve_options(cfg: dict, a) -> dict:
    o = dict(DEFAULTS)
    o.update(cfg.get("opcje") or {})
    if a.typy:
        o["typy_sadow"] = ALL_TYPES if a.typy.lower() in ("wszystkie", "all") else \
            [x.strip().upper() for x in a.typy.split(",") if x.strip()]
    if a.max_stron is not None:
        o["max_stron"] = a.max_stron
    if a.delay is not None:
        o["opoznienie_s"] = a.delay
    bad = [t for t in o["typy_sadow"] if t not in ALL_TYPES]
    if bad:
        raise SystemExit(f"Nieznane typy sadow: {bad}. Dozwolone: {', '.join(ALL_TYPES)}")
    return o


def main(argv=None) -> int:
    C.setup_console()
    ap = C.base_parser(__doc__.split("\n")[0], SOURCE_ID)
    ap.add_argument("--typy", default=None, help="courtType po przecinku (SUPREME,ADMINISTRATIVE,...) lub 'wszystkie'; "
                                                 "domyslnie z opcje.typy_sadow w sources.json")
    ap.add_argument("--max-stron", type=int, default=None, help="maks. liczba stron API w jednym przebiegu")
    ap.add_argument("--delay", type=float, default=None, help="min. odstep miedzy zapytaniami [s]")
    a = ap.parse_args(argv)
    if not C.check_enabled(SOURCE_ID, a.force, a.dry_run):
        return C.EXIT_OK
    try:
        cfg = C.source_config(SOURCE_ID)
    except (OSError, KeyError, ValueError):
        cfg = {}
    o = resolve_options(cfg, a)
    if not a.dry_run:
        C.warn("SAOS: robots.txt serwisu zabrania /api/ (Disallow), a dokumentacja API tego nie wyklucza; "
               "upewnij sie, ze masz zgode operatora SAOS (patrz zrodla/README.md).")
    stan_dir = Path(a.stan_dir) if a.stan_dir else None
    out = Path(a.out) if a.out else C.DEFAULT_OUT_DIR / "chunks_saos.jsonl"
    state = C.load_state(SOURCE_ID, stan_dir)
    today = dt.date.today()
    started = dt.datetime.now().replace(microsecond=0)

    partial = state.get("partial") or {}
    page0 = 0
    if a.since:
        since_iso = since_param(C.parse_date(a.since))
        run_started = started
    elif partial.get("since"):
        since_iso, page0 = partial["since"], int(partial.get("next_page", 0))
        run_started = dt.datetime.fromisoformat(partial.get("started") or started.isoformat())
    elif state.get("watermark"):
        wm = dt.datetime.fromisoformat(state["watermark"])
        since_iso = since_param(wm - dt.timedelta(days=SINCE_MARGIN_DAYS))
        run_started = started
    else:
        since_iso = since_param(today - dt.timedelta(days=int(o["okno_poczatkowe_dni"])))
        run_started = started
    types = set(o["typy_sadow"])
    C.log(f"SAOS: od {since_iso}, strona startowa {page0}, typy sadow: {','.join(sorted(types))}, "
          f"maks. stron {o['max_stron']}, limit dokumentow {a.limit if a.limit is not None else 'brak'}")
    if a.dry_run:
        C.log(f"[dry-run] pierwsze zapytanie: {dump_url(since_iso, page0, int(o['rozmiar_strony']))}")
        C.log(f"[dry-run] kolejka ponowien: {len(state.get('retry') or {})} id; plik wyjsciowy: {out}")
        return C.EXIT_OK

    limiter = C.RateLimiter(float(o["opoznienie_s"]))
    courts = load_courts(limiter, stan_dir) if types & {"COMMON", "SUPREME"} else None
    existing = C.read_doc_ids(out)
    writer = C.PartWriter(out)
    rec = writer.recover()
    if rec:
        C.log(f"Odzyskano {rec} dokumentow z przerwanego przebiegu.")
        existing = C.read_doc_ids(out)
    retry: dict = dict(state.get("retry") or {})
    added: list[str] = []
    changed: list[str] = []
    stats = {"stron": 0, "rekordow": 0, "typ": 0, "pusty": 0, "zly": 0, "zapisane": 0}
    newest = state.get("newest_date")
    unavailable = False
    failure = False
    complete = False
    next_page = page0
    max_chars = int(o["max_znakow_orzeczenia"])

    def store(rows: list[dict], item: dict) -> None:
        nonlocal newest
        did = rows[0]["doc_id"]
        writer.add(rows)
        (changed if did in existing else added).append(did)
        existing.add(did)
        stats["zapisane"] += 1
        jd = item.get("judgmentDate")
        if jd and (newest is None or jd > newest):
            newest = jd

    def limit_hit() -> bool:
        return a.limit is not None and stats["zapisane"] >= a.limit

    try:
        # 1) kolejka ponowien (wpisy, ktore wczesniej nie mialy tresci)
        due = [k for k, v in retry.items() if v.get("last") != today.isoformat()]  # kazdy id najwyzej raz dziennie
        for jid in due[:int(o["max_ponowien_na_przebieg"])]:
            if limit_hit():
                break
            retry[jid]["last"] = today.isoformat()
            try:
                data = get_json(JUDGMENT_API.format(id=jid), limiter).get("data") or {}
            except C.HttpStatus as e:
                if e.status == 404:
                    retry.pop(jid, None)
                    continue
                raise
            rows, why = item_to_rows(data, types, max_chars, courts)
            if rows:
                store(rows, data)
                retry.pop(jid, None)
            else:
                retry[jid]["n"] = retry[jid].get("n", 0) + 1
                if why != "pusty" or retry[jid]["n"] >= MAX_RETRY_ATTEMPTS:
                    retry.pop(jid, None)
        # 2) kolejne strony dumpa
        url = dump_url(since_iso, page0, int(o["rozmiar_strony"]))
        page = page0
        while True:
            if stats["stron"] >= int(o["max_stron"]) or limit_hit():
                next_page = page
                break
            data = get_json(url, limiter)
            stats["stron"] += 1
            items = data.get("items") or []
            stopped_mid_page = False
            for it in items:
                stats["rekordow"] += 1
                if limit_hit():
                    stopped_mid_page = True
                    break
                rows, why = item_to_rows(it, types, max_chars, courts)
                if rows:
                    store(rows, it)
                    retry.pop(str(it.get("id")), None)
                else:
                    stats[why] += 1
                    if why == "pusty" and it.get("id") is not None and (it.get("courtType") in types):
                        retry.setdefault(str(it["id"]), {"n": 0, "od": today.isoformat()})
            if stopped_mid_page:
                next_page = page
                break
            nxt = next_link(data)
            if not nxt or not items:
                complete = True
                break
            url, page = nxt, page + 1
            next_page = page
            if stats["stron"] % 10 == 0:
                C.log(f"  ... strona {stats['stron']}, zapisane {stats['zapisane']}, odfiltrowane wg typu {stats['typ']}")
    except C.NotExpectedContent as e:
        C.warn(f"SAOS niedostepny: {e}")
        unavailable = True
    except C.FetchError as e:
        C.warn(f"blad pobierania: {e}")
        unavailable = isinstance(e, C.HttpStatus) and e.status in (429, 502, 503, 504)
        failure = not unavailable
    n_flushed = writer.flush_to_out()

    ids = C.read_doc_ids(out)
    state.update({"last_run": C.now_iso(), "count": len(ids), "newest_date": newest,
                  "retry": prune_retry(retry, today)})
    if complete:
        old_wm = state.get("watermark")
        # reczne --since pozniejsze niz dotychczasowy watermark nie moze go przesunac (powstalaby luka w danych)
        if not (a.since and old_wm and since_iso > since_param(dt.datetime.fromisoformat(old_wm))):
            state["watermark"] = run_started.isoformat()
        state["partial"] = None
    else:
        state["partial"] = {"since": since_iso, "next_page": next_page, "started": run_started.isoformat()}
    if stats["stron"] or stats["zapisane"] or n_flushed:
        C.save_state(SOURCE_ID, state, stan_dir)
        C.write_changes(SOURCE_ID, added, changed, stan_dir)
    C.log(f"Gotowe: stron {stats['stron']}, rekordow {stats['rekordow']}, zapisane {stats['zapisane']} "
          f"(nowe {len(added)}, zmienione {len(changed)}), odfiltrowane wg typu {stats['typ']}, bez tresci {stats['pusty']} "
          f"(kolejka ponowien: {len(state['retry'])}), niepoprawne {stats['zly']}. "
          f"{'Przebieg kompletny.' if complete else 'Przebieg NIEKOMPLETNY - kolejne uruchomienie wznowi od strony ' + str(next_page) + '.'}")
    if unavailable:
        return C.EXIT_UNAVAILABLE
    return C.EXIT_ERROR if failure else C.EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
