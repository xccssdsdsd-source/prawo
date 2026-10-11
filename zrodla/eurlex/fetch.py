#!/usr/bin/env python3
"""Fetcher aktow prawa UE po polsku (Publications Office / Cellar, po numerze CELEX). Zrodlo USPIONE (enabled:false).

Uzycie:
  python zrodla/eurlex/fetch.py [--limit N] [--celex 32016R0679 ...] [--out PLIK] [--stan-dir DIR]
                                [--odswiez] [--dry-run] [--force]
  python zrodla/eurlex/fetch.py --odkryj [--since YYYY-MM-DD] [--limit N]   # tylko lista nowych aktow z SPARQL

Lista aktow: zrodla/eurlex/seed.json (zweryfikowane CELEX) + opcjonalnie --celex. Wynik: pipeline/out/chunks_eurlex.jsonl
(kategoria "ue", doc_id "CELEX/<celex>", dzielenie na "Artykul N", reszta na fragmenty ~2000 znakow).
Stan: stan/zrodlo_eurlex.json (count, newest_date, last_run, per akt: sha256 + data pobrania).

Pobieranie wylacznie z publications.europa.eu (strona eur-lex.europa.eu jest za AWS WAF i nie nadaje sie do skryptow).
Kody wyjscia: 0 ok, 1 blad (czesc aktow sie nie powiodla), 3 zrodlo niedostepne.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _common as C  # noqa: E402

SOURCE_ID = "eurlex"
CELLAR = "http://publications.europa.eu/resource/celex/"
SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"
EURLEX_PAGE = "https://eur-lex.europa.eu/legal-content/PL/TXT/?uri=CELEX:"
ACCEPT = {"xhtml": "application/xhtml+xml", "html": "text/html", "pdf": "application/pdf"}
FORMAT_ORDER = ["xhtml", "html", "pdf"]
META_TARGET = 2000        # rozmiar fragmentow preambuly / zalacznikow / aktow bez artykulow
ART_MAX = 5500            # artykul krotszy zostaje w calosci; dluzszy dzielony na kawalki ART_SPLIT
ART_SPLIT = 3500
ODSWIEZ_DNI = 90          # po ilu dniach ponownie pobrac akt juz zaladowany

CELEX_RE = re.compile(r"^([0-9])(\d{4})([A-Z])(\d{1,5})(?:-(\d{8}))?$")
MONTHS = {"stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5, "czerwca": 6, "lipca": 7,
          "sierpnia": 8, "września": 9, "października": 10, "listopada": 11, "grudnia": 12}
ART_RE = re.compile(r"^Artykuł\s+(\d+[a-z]?)$")
SECTION_RE = re.compile(r"^(CZĘŚĆ|TYTUŁ|ROZDZIAŁ|SEKCJA|DZIAŁ|ODDZIAŁ|PODSEKCJA)\s+([IVXLCDM]+|\d+[A-Za-z]?|[A-ZĄĆĘŁŃÓŚŹŻ]+)$")
SECTION_LEVEL = {"CZĘŚĆ": 1, "DZIAŁ": 2, "TYTUŁ": 2, "ROZDZIAŁ": 3, "ODDZIAŁ": 4, "SEKCJA": 4, "PODSEKCJA": 5}
ANNEX_RE = re.compile(r"^ZAŁĄCZNIK(?:\s+([IVXLCDM]+|\d+[A-Za-z]?))?$")
TITLE_START = re.compile(r"^(ROZPORZĄDZENIE|DYREKTYWA|DECYZJA|TRAKTAT|UMOWA|PROTOKÓŁ|KONWENCJA|AKT|WSPÓLNE|"
                         r"ZALECENIE|OPINIA|KOMUNIKAT|POROZUMIENIE)\b", re.I)
TITLE_STOP = re.compile(r"^(\(Tekst|PARLAMENT EUROPEJSKI|RADA\b|KOMISJA\b|EUROPEJSKI BANK|Dziennik Urzędowy)", re.I)
MARKERS = re.compile(r"[▼►◄](?:[A-Z]\d*)?\s*")
POL = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
CAP_WORDS = {"parlamentu", "europejskiego", "rady", "komisji", "unii", "europejskiej", "wspólnot", "europejskich",
             "rzeczypospolitej", "polskiej", "bankowego", "centralnego"}


# ------------------------------------------------------------------ CELEX / tytul

def parse_celex(celex: str) -> dict | None:
    m = CELEX_RE.match(celex)
    if not m:
        return None
    sector, year, typ, num, date = m.groups()
    return {"sektor": sector, "rok": int(year), "typ": typ, "numer": int(num), "data_wersji": date,
            "ujednolicony": sector == "0"}


def fix_title(t: str) -> str:
    """'ROZPORZĄDZENIE PARLAMENTU EUROPEJSKIEGO I RADY (UE) 2016/679 z dnia ...' -> zapis jak w Dz.Urz."""
    t = C.normalize_line(t)
    m = re.search(r"\s+z dnia\s", t)
    head, rest = (t[:m.start()], t[m.start():]) if m else (t, "")
    words = []
    for i, w in enumerate(head.split(" ")):
        core = w.lower()
        if re.fullmatch(r"\(?(ue|we|ewg|euratom|ewwia|wpzib|eu)\)?", core):
            w = w.upper()
        elif re.search(r"\d", core):
            w = re.sub(r"/([a-z]+)$", lambda mm: "/" + mm.group(1).upper(), core)
        elif i == 0 or core in CAP_WORDS:
            w = core.capitalize()
        else:
            w = core
        words.append(w)
    return " ".join(words) + rest


def parse_act_date(title: str) -> str | None:
    m = re.search(r"z dnia\s+(\d{1,2})\s+([a-ząćęłńóśźż]+)\s+(\d{4})", title)
    if m and m.group(2) in MONTHS:
        return f"{int(m.group(3)):04d}-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}"
    return None


# ------------------------------------------------------------------ pobieranie

def fetch_act(celex: str, hint: str | None, limiter: C.RateLimiter) -> tuple[str, bytes, str]:
    """Probuje formatow w kolejnosci: podpowiedz z seed -> xhtml -> html -> pdf. 404 (brak danego formatu) = nastepny.
    Zwraca (format, bajty, url_koncowy). Brak tresci w zadnym formacie -> FetchError."""
    order = ([hint] if hint in ACCEPT else []) + [f for f in FORMAT_ORDER if f != hint]
    last: Exception | None = None
    for fmt in order:
        try:
            r = C.http_get(CELLAR + urllib.parse.quote(celex), expect="any", timeout=120, retries=3, backoff=5.0,
                           limiter=limiter, headers={"Accept": ACCEPT[fmt], "Accept-Language": "pl"})
        except C.HttpStatus as e:
            if e.status in (404, 406):
                last = e
                continue
            raise
        ctype = r.content_type
        if fmt == "pdf":
            if r.body[:5] != b"%PDF-":
                last = C.NotExpectedContent(f"{celex}: oczekiwano PDF, Content-Type '{ctype}'")
                continue
        elif not ("html" in ctype or "xml" in ctype):
            last = C.NotExpectedContent(f"{celex}: oczekiwano HTML, Content-Type '{ctype}'")
            continue
        if not r.body.strip():
            last = C.FetchError(f"{celex}: pusta odpowiedz ({fmt})")
            continue
        return fmt, r.body, r.url
    raise C.FetchError(f"{celex}: brak tekstu w formatach {order} ({last})")


def pdf_blocks(data: bytes) -> list[tuple[str, str]]:
    try:
        import pymupdf  # type: ignore
        doc = pymupdf.open(stream=data, filetype="pdf")
        text = "\n".join(p.get_text() for p in doc)
        doc.close()
    except ImportError:
        try:
            import io
            from pypdf import PdfReader  # type: ignore
            text = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)
        except ImportError:
            raise C.FetchError("do odczytu PDF potrzebna biblioteka pymupdf lub pypdf (pip install pymupdf)")
    return [("", C.normalize_line(l)) for l in text.split("\n") if l.strip()]


def to_blocks(fmt: str, body: bytes, ctype: str = "text/html; charset=utf-8") -> tuple[list[tuple[str, str]], int]:
    """-> (bloki (klasa, tekst), liczba znakow U+FFFD w zrodle)."""
    if fmt == "pdf":
        return pdf_blocks(body), 0
    text, bad = C.decode_body(body, ctype)
    return C.html_blocks(text), bad


# ------------------------------------------------------------------ struktura aktu

def looks_polish(text: str) -> bool:
    letters = sum(ch.isalpha() for ch in text)
    if letters < 200:
        return sum(ch in POL for ch in text) >= 2
    return sum(ch in POL for ch in text) / letters >= 0.02


def clean_blocks(blocks: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Usuwa przypisy koncowe i znaczniki wersji ujednoliconej, zwraca czyste bloki."""
    out = []
    for cls, t in blocks:
        if re.search(r"(^|-)note$", cls) or re.search(r"(^|-)final$", cls):
            continue  # przypisy dolne (oj-note) i linia konczaca
        if re.fullmatch(r"-{8,}", t):
            break      # starsze HTML: za linia '-----' sa juz tylko przypisy
        t = MARKERS.sub("", t).strip()
        if t:
            out.append((cls, t))
    return out


def find_title(blocks: list[tuple[str, str]], seed: dict, celex: str) -> tuple[str, int, str | None]:
    """-> (tytul, indeks_pierwszego_bloku_tresci, display_address_czesc_Dz.Urz.). Tresc zaczyna sie po tytule."""
    ref = None
    # naglowek Dz.Urz. (nowsze: klasy *hd-date / *hd-oj; starsze: tekst 'Dziennik Urzedowy L 201 , 31/07/2002 P. 0037')
    for _, t in blocks[:12]:
        m = re.match(r"^(\d{1,2}\.\d{1,2}\.\d{4})\s+PL\s+Dziennik Urzędowy Unii Europejskiej\s+([LC])\s*(\d+)\s*/\s*(\d+)", t)
        if m:  # nowszy format: wiersz tabeli naglowka "4.5.2016 PL Dziennik Urzędowy Unii Europejskiej L 119/1"
            ref = f"Dz.Urz. UE {m.group(2)} {m.group(3)} z {m.group(1)}, s. {m.group(4)}"
            break
        m = re.search(r"Dziennik Urzędowy\s+([LC]\s*\d+)\s*,\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*P\.\s*0*(\d+)", t)
        if m:  # starszy HTML: "Dziennik Urzędowy L 201 , 31/07/2002 P. 0037 - 0047"
            ref = f"Dz.Urz. UE {m.group(1)} z {int(m.group(2))}.{int(m.group(3))}.{m.group(4)}, s. {m.group(5)}"
            break
    first = next((i for i, (c, _) in enumerate(blocks[:15]) if c.endswith("doc-ti")), None)
    if first is not None:  # tytul = ciagly poczatkowy ciag blokow doc-ti (dalsze doc-ti to tytuly zalacznikow)
        end = first
        while end < len(blocks) and blocks[end][0].endswith("doc-ti"):
            end += 1
        parts = [t for _, t in blocks[first:end] if not t.startswith("(Tekst")]
        return fix_title(" ".join(parts)), end, ref
    for i, (_, t) in enumerate(blocks[:40]):
        if TITLE_START.match(t):
            parts, j = [t], i + 1
            while (j < len(blocks) and len(parts) < 4 and not TITLE_STOP.match(blocks[j][1])
                   and ("z dnia" not in parts[0] or re.match(r"^(dotycz|w sprawie|ustanawiaj|zmieniaj)", blocks[j][1], re.I))):
                parts.append(blocks[j][1])
                j += 1
            while j < len(blocks) and blocks[j][1].startswith("Dziennik Urzędowy"):
                j += 1
            return fix_title(" ".join(parts)), j, ref
    return (seed.get("nazwa") or celex), 0, ref


def split_structure(blocks: list[tuple[str, str]]) -> list[dict]:
    """Bloki tresci -> sekcje: {'kind': 'pre'|'art'|'annex', 'article', 'heading', 'lines'}."""
    sections: list[dict] = []
    levels: dict[int, str] = {}
    heading = ""
    cur = {"kind": "pre", "article": None, "heading": "", "lines": []}
    in_annex = False
    n = len(blocks)
    i = 0

    def push():
        nonlocal cur
        if cur["lines"]:
            sections.append(cur)

    while i < n:
        t = blocks[i][1]
        am = ANNEX_RE.match(t)
        if am:
            push()
            label = t
            if i + 1 < n and len(blocks[i + 1][1]) < 200 and not ANNEX_RE.match(blocks[i + 1][1]) \
                    and not ART_RE.match(blocks[i + 1][1]):
                label = f"{t} {blocks[i + 1][1]}"
                i += 1
            in_annex = True
            cur = {"kind": "annex", "article": None, "heading": label, "lines": []}
            i += 1
            continue
        if not in_annex:
            sm = SECTION_RE.match(t)
            if sm and t.upper() == t:
                lab = t
                if i + 1 < n and len(blocks[i + 1][1]) < 200 and not SECTION_RE.match(blocks[i + 1][1]) \
                        and not ART_RE.match(blocks[i + 1][1]):
                    lab = f"{t} {blocks[i + 1][1]}"
                    i += 1
                lvl = SECTION_LEVEL[sm.group(1)]
                for k in [k for k in levels if k >= lvl]:
                    del levels[k]
                levels[lvl] = lab
                heading = " > ".join(levels[k] for k in sorted(levels))
                i += 1
                continue
            m = ART_RE.match(t)
            if m:
                push()
                cur = {"kind": "art", "article": m.group(1), "heading": heading, "lines": [t]}
                i += 1
                continue
            if cur["kind"] == "pre" and not cur["lines"]:
                cur["heading"] = heading
        cur["lines"].append(t)
        i += 1
    push()
    return sections


def build_rows(celex: str, seed: dict, blocks: list[tuple[str, str]], fff: int = 0) -> tuple[list[dict], dict]:
    """-> (wiersze chunks, info). Rzuca ValueError przy tresci nienadajacej sie do zapisu."""
    cx = parse_celex(celex)
    if not cx:
        raise ValueError(f"nieprawidlowy numer CELEX: {celex!r}")
    blocks = clean_blocks(blocks)
    if not blocks:
        raise ValueError("pusty dokument po oczyszczeniu")
    title, start, addr = find_title(blocks, seed, celex)
    if seed.get("tytul"):
        title = seed["tytul"]
    body_blocks = blocks[start:]
    alltext = "\n".join(t for _, t in body_blocks)
    if not looks_polish(alltext):
        raise ValueError("tekst nie wyglada na polski (brak polskich znakow diakrytycznych) - odrzucony")
    if len(alltext) < 200 and not seed.get("dopusc_krotki"):
        raise ValueError(f"podejrzanie krotki tekst ({len(alltext)} znakow)")
    sections = split_structure(body_blocks)
    ujednolicony = cx["ujednolicony"]
    traktat = cx["sektor"] == "1"
    status = ("tekst ujednolicony UE (dokumentacyjny)" if ujednolicony
              else "traktat – wersja skonsolidowana z Dz.Urz. UE" if traktat
              else "tekst z Dz.Urz. UE (brzmienie z dnia publikacji)")
    meta = {
        "doc_id": f"CELEX/{celex}", "eli": f"CELEX/{celex}", "kategoria": "ue", "publisher": "UE",
        "year": cx["rok"], "pos": cx["numer"], "title": title,
        "display_address": f"{addr} (CELEX {celex})" if addr else f"CELEX {celex}",
        "announcement_date": parse_act_date(title), "status": status, "is_consolidated": ujednolicony,
        "source_url": EURLEX_PAGE + celex,
    }
    rows: list[dict] = []

    def add(article, heading, text):
        text, _ = C.clean_text(text)
        heading, _ = C.clean_text(heading)
        if text.strip():
            rows.append(C.make_row(meta, len(rows) + 1, article, heading, text.strip()))

    intro = [f"Akt prawa Unii Europejskiej (CELEX {celex}). {title}."]
    if seed.get("nazwa"):
        intro.append(f"Nazwa skrócona: {seed['nazwa']}.")
    intro.append(
        "Tekst ujednolicony (dokumentacyjny) – wiążąca jest wersja opublikowana w Dzienniku Urzędowym UE."
        if ujednolicony else
        "Fragment traktatu w wersji skonsolidowanej opublikowanej w Dzienniku Urzędowym UE; sprawdź aktualny tekst w EUR-Lex."
        if traktat else
        "Tekst w polskiej wersji z Dziennika Urzędowego UE w brzmieniu z dnia publikacji; późniejsze zmiany "
        "i sprostowania nie są uwzględnione – sprawdź aktualną wersję w EUR-Lex.")
    add(None, "Informacje o akcie", "\n".join(intro))

    has_art = any(s["kind"] == "art" for s in sections)
    n_art = 0
    for s in sections:
        text = "\n".join(s["lines"])
        if s["kind"] == "art":
            n_art += 1
            if len(text) <= ART_MAX:
                add(s["article"], s["heading"], text)
            else:
                first_line = s["lines"][0]
                for k, part in enumerate(C.split_text(text, ART_SPLIT)):
                    add(s["article"], s["heading"], part if k == 0 else f"{first_line} (ciąg dalszy)\n{part}")
        else:
            if s["kind"] == "pre":
                head = "Preambuła" if has_art else (s["heading"] or "")
            else:
                head = s["heading"][:300]
            for part in C.split_text(text, META_TARGET):
                add(None, head, part)
    errs = C.validate_rows(rows)
    if errs:
        raise ValueError("wiersze niezgodne ze schematem: " + "; ".join(errs[:3]))
    return rows, {"title": title, "articles": n_art, "chunks": len(rows), "date": meta["announcement_date"],
                  "chars": len(alltext), "ffd_in_source": fff}


# ------------------------------------------------------------------ discovery (SPARQL)

def discover(since: str, limit: int, limiter: C.RateLimiter) -> list[dict]:
    q = ("PREFIX cdm: <http://publications.europa.eu/ontology/cdm#> PREFIX xsd: <http://www.w3.org/2001/XMLSchema#> "
         "SELECT ?celex ?date WHERE { ?w cdm:resource_legal_id_celex ?celex ; cdm:work_date_document ?date . "
         f'FILTER(?date >= "{since}"^^xsd:date) FILTER(REGEX(STR(?celex),"^3[0-9]{{4}}[RL][0-9]+$")) }} '
         f"ORDER BY DESC(?date) LIMIT {int(limit)}")
    url = SPARQL + "?" + urllib.parse.urlencode({"query": q})
    r = C.http_get(url, expect="json", headers={"Accept": "application/sparql-results+json"}, timeout=90,
                   limiter=limiter)
    rows = r.json()["results"]["bindings"]
    return [{"celex": b["celex"]["value"], "date": b["date"]["value"]} for b in rows]


# ------------------------------------------------------------------ glowny przebieg

def load_seed(path: Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    acts = data.get("akty", data) if isinstance(data, dict) else data
    out, seen = [], set()
    for a in acts:
        if isinstance(a, str):
            a = {"celex": a}
        c = a.get("celex", "").strip()
        if not parse_celex(c):
            C.warn(f"seed: pomijam nieprawidlowy CELEX {c!r}")
            continue
        if c in seen:
            continue
        seen.add(c)
        out.append(a)
    return out


def main(argv=None) -> int:
    C.setup_console()
    ap = C.base_parser(__doc__.split("\n")[0], SOURCE_ID)
    ap.add_argument("--celex", nargs="+", default=[], metavar="CELEX", help="dodatkowe numery CELEX poza seed.json")
    ap.add_argument("--seed", default=str(HERE / "seed.json"), help="plik z lista aktow")
    ap.add_argument("--tylko-celex", action="store_true", help="pobierz tylko numery z --celex (bez seed.json)")
    ap.add_argument("--odswiez", action="store_true", help=f"pobierz ponownie nawet akty pobrane <{ODSWIEZ_DNI} dni temu")
    ap.add_argument("--odkryj", action="store_true", help="tylko wypisz nowe akty (R/L) z SPARQL od --since (domyslnie 30 dni)")
    ap.add_argument("--delay", type=float, default=1.5, help="min. odstep miedzy zapytaniami [s]")
    a = ap.parse_args(argv)

    if not C.check_enabled(SOURCE_ID, a.force, a.dry_run or a.odkryj):
        return C.EXIT_OK
    stan_dir = Path(a.stan_dir) if a.stan_dir else None
    limiter = C.RateLimiter(a.delay)

    if a.odkryj:
        since = a.since or (C.dt.date.today() - C.dt.timedelta(days=30)).isoformat()
        C.parse_date(since)
        try:
            found = discover(since, a.limit or 25, limiter)
        except C.FetchError as e:
            C.warn(f"SPARQL niedostepny: {e}")
            return C.EXIT_UNAVAILABLE
        C.log(f"Nowe akty (R/L) od {since}: {len(found)}")
        for f in found:
            C.log(f"  {f['celex']}  {f['date']}")
        C.log("Aby pobrac wybrane: python zrodla/eurlex/fetch.py --tylko-celex --celex <CELEX> ... (albo dopisz do seed.json)")
        if not a.dry_run:
            C.atomic_write_json(C.state_path("eurlex_kandydaci", stan_dir),
                                {"run_at": C.now_iso(), "od": since, "akty": found})
        return C.EXIT_OK

    acts = [] if a.tylko_celex else load_seed(Path(a.seed))
    known = {x["celex"] for x in acts}
    for c in a.celex:
        if not parse_celex(c):
            raise SystemExit(f"Zly numer CELEX: {c!r}")
        if c not in known:
            acts.append({"celex": c})
            known.add(c)
    if a.tylko_celex and not a.celex:
        raise SystemExit("--tylko-celex wymaga --celex")

    out = Path(a.out) if a.out else C.DEFAULT_OUT_DIR / "chunks_eurlex.jsonl"
    state = C.load_state(SOURCE_ID, stan_dir)
    docs_state: dict = state.get("docs", {})
    existing = C.read_doc_ids(out)
    today = C.dt.date.today()
    todo = []
    for act in acts:
        c = act["celex"]
        st = docs_state.get(c)
        fresh = False
        if st and f"CELEX/{c}" in existing and not a.odswiez and c not in a.celex:
            try:
                age = (today - C.dt.date.fromisoformat(st.get("fetched", "1970-01-01"))).days
                fresh = age < ODSWIEZ_DNI
            except ValueError:
                fresh = False
        if not fresh:
            todo.append(act)
    n_fresh = len(acts) - len(todo)
    if a.limit is not None:
        todo = todo[:a.limit]
    C.log(f"EUR-Lex: aktow na liscie {len(acts)}, swiezych (pomijam) {n_fresh}, do pobrania w tym przebiegu {len(todo)}.")
    if a.dry_run:
        for act in todo:
            C.log(f"  [dry-run] {act['celex']} {act.get('nazwa', '')}")
        return C.EXIT_OK

    writer = C.PartWriter(out)
    rec = writer.recover()
    if rec:
        C.log(f"Odzyskano {rec} dokumentow z przerwanego przebiegu.")
    added, changed, unchanged, failed, unavailable = [], [], 0, {}, False
    newest = state.get("newest_date")
    for k, act in enumerate(todo, 1):
        c = act["celex"]
        try:
            fmt, body, url = fetch_act(c, act.get("format"), limiter)
            blocks, bad = to_blocks(fmt, body)
            rows, info = build_rows(c, act, blocks, bad)
        except (C.FetchError, ValueError) as e:
            msg = str(e) if c in str(e) else f"{c}: {e}"
            failed[c] = msg[:300]
            C.warn(msg)
            if isinstance(e, C.NotExpectedContent) or (isinstance(e, C.HttpStatus) and e.status in (403, 429, 503)):
                C.warn("serwer zwraca nietypowe odpowiedzi - przerywam przebieg, sprobuj pozniej")
                unavailable = True
                break
            continue
        digest = C.sha256_hex("\n".join(r["text"] for r in rows))
        prev = docs_state.get(c, {})
        doc_id = f"CELEX/{c}"
        if doc_id in existing and prev.get("sha256") == digest:
            unchanged += 1
        else:
            writer.add(rows)
            (changed if doc_id in existing else added).append(doc_id)
        docs_state[c] = {"sha256": digest, "fetched": today.isoformat(), "format": fmt, "chunks": len(rows),
                         "title": info["title"], "date": info["date"]}
        if info["date"] and (newest is None or info["date"] > newest):
            newest = info["date"]
        C.log(f"[{k}/{len(todo)}] {c} ({fmt}): {info['articles']} art., {len(rows)} fragm., {info['chars']} zn. - {info['title'][:70]}")
    writer.flush_to_out()
    ids = C.read_doc_ids(out)
    state.update({"last_run": C.now_iso(), "count": len(ids), "newest_date": newest, "docs": docs_state,
                  "errors": failed})
    C.save_state(SOURCE_ID, state, stan_dir)
    C.write_changes(SOURCE_ID, added, changed, stan_dir)
    C.log(f"Gotowe: nowych {len(added)}, zmienionych {len(changed)}, bez zmian {unchanged}, bledow {len(failed)}. "
          f"Plik: {out} ({len(ids)} aktow).")
    if failed:
        return C.EXIT_UNAVAILABLE if unavailable else C.EXIT_ERROR
    return C.EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
