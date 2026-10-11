#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
lookup_article.py - strumieniowe (tylko do odczytu) wyszukiwanie artykulow w
pipeline/out/chunks.jsonl (~1 GB; NIE wczytuje pliku do pamieci).

Sluzy do weryfikacji twierdzen w bazie wiedzy (vercel/public/wiedza/*.md):
kazdy odnosnik w formie [DU/1964/93#U art. 118] ma byc sprawdzony tym narzedziem.

Tryb 1 - wypisz tresc artykulow:
  python pipeline/tools/lookup_article.py "DU/1964/93#U" 118 123
  python pipeline/tools/lookup_article.py --query "DU/1964/93#U:118" --query "DU/1964/93#U:123"
  python pipeline/tools/lookup_article.py "DU/1964/93#U" --list-articles
  python pipeline/tools/lookup_article.py "DU/1964/93#U" --grep "przedawni" --max-chars 400
  python pipeline/tools/lookup_article.py --out wynik.txt "DU/1997/483#U" 1 2
  python pipeline/tools/lookup_article.py "DU/2026/300" "§158"      # paragraf rozporzadzenia (ZTP)

Tryb 2 - zweryfikuj odnosniki w plikach markdown (uzywane po kazdej aktualizacji danych):
  python pipeline/tools/lookup_article.py --verify-md vercel/public/wiedza/*.md
  Sprawdza, ze (a) kazdy odnosnik [DOC art. N] / [DOC art. N, M] / [DOC § N] / [DOC ord N]
  (ord = fragment wstepny bez numeru artykulu) wskazuje istniejacy fragment w chunks.jsonl,
  (b) kazdy cytat w "..." (polskie cudzyslowy) stojacy w linii z odnosnikiem jest doslowna podlancuchowa (po normalizacji bialych znakow) tresci wskazanych artykulow;
  cytat z wielokropkiem (... albo [...]) jest sprawdzany czesciami. Kod wyjscia 3, gdy cos sie nie zgadza.
  Blad po aktualizacji danych oznacza, ze przepis zmienil brzmienie albo zniknal - trzeba poprawic wpis.

Tryb 3 - adnotacje o zapowiedzianych zmianach (przyszle brzmienia w tekstach ujednoliconych):
  python pipeline/tools/lookup_article.py --upcoming [--from 2026-10-12] [DOC_ID ...] [--out PLIK]
  Wypisuje fragmenty zawierajace adnotacje ISAP typu "Nowe brzmienie art. X wejdzie w zycie z dn. D"
  (data D >= --from; domyslnie dzisiaj). Bez DOC_ID przeszukuje cala baze. Wynik: data | doc_id | art. | Dz.U. | kontekst.
  Uzywane do odswiezania pliku wiedza/nadchodzace-zmiany.md. Daty z adnotacji wyciaga regexem - sprawdz kontekst.

Zasady:
  - Jeden przebieg po pliku obsluguje wiele dokumentow/artykulow naraz.
  - Wyjscie zawsze UTF-8 (stdout przestawiany na UTF-8; mozna tez uzyc --out PLIK,
    bo konsola Windows psuje wyswietlanie polskich znakow mimo poprawnych danych).
  - Nic nie zapisuje poza opcjonalnym plikiem --out. Nie modyfikuje chunks.jsonl.
  - Kod wyjscia 0 gdy znaleziono wszystko, 3 gdy czegos zabraklo, 2 gdy brak pliku chunks.

Normalizacja numeru artykulu: "46[1]", "46(1)", "46^1" i "46¹" oznaczaja to samo.
UWAGA: w niektorych tekstach ujednoliconych indeks gorny jest "splaszczony" (np. art. 29¹ k.p.
wystepuje jako "291") - to cecha danych zrodlowych, nie blad tego narzedzia.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FILE = ROOT / "pipeline" / "out" / "chunks.jsonl"

_SUP = {"¹": "1", "²": "2", "³": "3", "⁰": "0", "⁴": "4",
        "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9"}
_PREFIXES = (b'{"doc_id": "', b'{"doc_id":"')  # json.dumps domyslnie daje spacje po ':'


def norm_art(a: str | None) -> str | None:
    """Sprowadza zapis numeru artykulu do postaci z chunks.jsonl (np. 46[1])."""
    if a is None:
        return None
    a = str(a).strip().lower()
    if a.startswith("§"):  # paragraf aktu bez struktury "Art." (np. rozporzadzenia): "§ 158" -> "§158"
        return "§" + re.sub(r"\s+", "", a[1:])
    a = re.sub(r"^art\.?\s*", "", a)
    sup = "".join(_SUP[ch] for ch in a if ch in _SUP)
    if sup:
        a = "".join(ch for ch in a if ch not in _SUP) + "[" + sup + "]"
    a = re.sub(r"\((\w+)\)$", r"[\1]", a)
    a = re.sub(r"\^(\w+)$", r"[\1]", a)
    return a


def doc_id_of(line: bytes) -> str | None:
    """Szybko wyciaga doc_id z poczatku linii (bez parsowania JSON)."""
    for pre in _PREFIXES:
        if line.startswith(pre):
            end = line.find(b'"', len(pre))
            if end < 0:
                return None
            return line[len(pre):end].decode("utf-8", "replace")
    return None


def par_piece(text: str, want: str, is_open: bool) -> tuple[str | None, bool]:
    """Wycina tekst paragrafu '§ N.' z fragmentu. Paragraf moze siegac na kolejne fragmenty:
    zwraca (kawalek|None, czy_paragraf_nadal_otwarty). Kawalek konczy sie przed nastepnym '§ M' na poczatku linii."""
    if is_open:
        nxt = re.search(r"(?m)^§ \d", text)
        return (text[: nxt.start()], False) if nxt else (text, True)
    m = re.search(r"(?m)^§ " + re.escape(want[1:]) + r"\.", text)
    if not m:
        return None, False
    nxt = re.search(r"(?m)^§ \d", text[m.end():])
    if nxt:
        return text[m.start(): m.end() + nxt.start()], False
    return text[m.start():], True


def _ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


# --------------------------------------------------------------------------- tryb 2
REF_RX = re.compile(r"\[((?:DU|MP)/\d{4}/\d+(?:#U)?)\s+(art\.|§|ord)\s*([^\]]+)\]")
QUOTE_RX = re.compile(r"„([^”]+)”")


def verify_md(paths: list[str], chunks_file: Path) -> int:
    refs_by_line: list[tuple[str, int, str, list[tuple[str, str]]]] = []  # (plik, nr_linii, linia, [(doc, klucz)])
    need: dict[str, set[str]] = {}
    for p in paths:
        pth = Path(p)
        for i, line in enumerate(pth.read_text(encoding="utf-8").splitlines(), 1):
            found = []
            for m in REF_RX.finditer(line):
                doc, kind, rest = m.group(1), m.group(2), m.group(3)
                for part in [x.strip() for x in re.split(r"[;,]", rest) if x.strip()]:
                    if kind == "§":
                        key = norm_art("§ " + part.split()[0])
                    elif kind == "ord":
                        key = "ord:" + part.split()[0]  # fragment wstepny (article=null) wskazany numerem ord
                    else:
                        key = norm_art(part.split()[0])  # "4 ust. 1" -> sam numer artykulu
                    found.append((doc, key))
                    need.setdefault(doc, set()).add(key)
            if found:
                refs_by_line.append((pth.name, i, line, found))
    if not need:
        print("Brak odnosnikow [DOC art. N] w podanych plikach.")
        return 0
    texts: dict[tuple[str, str], list[str]] = {}
    seen_docs: set[str] = set()
    par_open: dict[tuple[str, str], bool] = {}
    with open(chunks_file, "rb") as f:
        for line in f:
            did = doc_id_of(line)
            if did is None or did not in need:
                continue
            seen_docs.add(did)
            row = json.loads(line)
            art = norm_art(row.get("article")) if row.get("article") is not None else None
            for key in need[did]:
                if key.startswith("ord:"):
                    if str(row.get("ord")) == key[4:]:
                        texts.setdefault((did, key), []).append(row.get("text", ""))
                elif key.startswith("§"):
                    seg, par_open[(did, key)] = par_piece(row.get("text", ""), key, par_open.get((did, key), False))
                    if seg is not None:
                        texts.setdefault((did, key), []).append(seg)
                elif art == key:
                    texts.setdefault((did, key), []).append(row.get("text", ""))
    bad = 0
    total_refs = 0
    total_quotes = 0
    for fname, nr, line, found in refs_by_line:
        pool = []
        for doc, key in found:
            total_refs += 1
            t = texts.get((doc, key))
            if not t:
                bad += 1
                reason = "brak dokumentu w chunks" if doc not in seen_docs else "brak takiego artykulu"
                print(f"BLAD {fname}:{nr}: [{doc} {key}] - {reason}")
            else:
                pool.append(_ws(" ".join(t)))
        if not pool:
            continue
        blob = " ".join(pool)
        for q in QUOTE_RX.findall(line):
            total_quotes += 1
            for part in re.split(r"…|\[\.\.\.\]|\.\.\.", q):
                part = _ws(part).strip(" ,;")
                if len(part) < 4:
                    continue
                if part not in blob:
                    bad += 1
                    print(f"BLAD {fname}:{nr}: cytat nie wystepuje w zrodle: „{part[:90]}”")
    print(f"Sprawdzono odnosnikow: {total_refs}, cytatow: {total_quotes}, bledow: {bad}")
    return 3 if bad else 0


# --------------------------------------------------------------------------- tryb 3
UP_RX = re.compile(r"wej(?:dzie|dą) w życie\s+z\s+dn\.\s*(\d{1,2})\.(\d{1,2})\.(\d{4})", re.S)
UP_POZ = re.compile(r"\(Dz\.\s*U\.\s*z\s*(\d{4})\s*r\.\s*poz\.\s*([\d,\si]+)", re.S)


def upcoming(chunks_file: Path, only: set[str], from_date: str | None, out_path: str | None) -> int:
    import datetime
    start = datetime.date.fromisoformat(from_date) if from_date else datetime.date.today()
    rows = []
    with open(chunks_file, "rb") as f:
        for line in f:
            if b"wejdzie w" not in line and "wejdą w".encode("utf-8") not in line and rb"wejd\u0105 w" not in line:
                continue
            did = doc_id_of(line)
            if did is None or (only and did not in only):
                continue
            row = json.loads(line)
            t = row.get("text", "")
            for m in UP_RX.finditer(t):
                d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                try:
                    dt = datetime.date(y, mo, d)
                except ValueError:
                    continue
                if dt < start:
                    continue
                tail = t[m.end(): m.end() + 60]
                pz = UP_POZ.search(tail)
                poz = f"Dz.U. {pz.group(1)} poz. {_ws(pz.group(2))}" if pz else "-"
                ctx = _ws(t[max(0, m.start() - 110): m.end() + 40])
                rows.append((dt.isoformat(), did, row.get("article"), poz, ctx))
    rows = sorted(set(rows))
    lines = [f"{d} | {did} | art. {a} | {poz} | {ctx}" for d, did, a, poz, ctx in rows]
    lines.append(f"# razem {len(rows)} adnotacji z data wejscia w zycie >= {start.isoformat()}")
    text = "\n".join(lines)
    if out_path:
        Path(out_path).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


# --------------------------------------------------------------------------- tryb 1
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("doc_id", nargs="?", help="np. DU/1964/93#U (pomin przy uzyciu --query)")
    ap.add_argument("articles", nargs="*", help="numery artykulow, np. 118 46[1] albo paragrafy §158")
    ap.add_argument("--query", action="append", default=[], metavar="DOC_ID:ART",
                    help="powtarzalne; DOC_ID:ART (ART moze byc puste = caly dokument)")
    ap.add_argument("--file", default=str(DEFAULT_FILE), help="plik chunks.jsonl (domyslnie pipeline/out/chunks.jsonl)")
    ap.add_argument("--list-articles", action="store_true", help="wypisz tylko liste numerow artykulow dokumentu")
    ap.add_argument("--grep", help="wyrazenie regularne (bez rozrozniania wielkosci liter) - tylko fragmenty pasujace")
    ap.add_argument("--max-chars", type=int, default=0, help="obetnij tekst fragmentu do N znakow (0 = bez ciecia)")
    ap.add_argument("--max-hits", type=int, default=200, help="limit wypisanych fragmentow na zapytanie")
    ap.add_argument("--meta", action="store_true", help="wypisz tez metadane dokumentu (tytul, adres, status, source_url)")
    ap.add_argument("--json", action="store_true", help="wyjscie jako JSON Lines")
    ap.add_argument("--out", help="zapisz wynik do pliku UTF-8 zamiast na stdout")
    ap.add_argument("--upcoming", action="store_true",
                    help="wypisz adnotacje o zapowiedzianych zmianach (wejdzie w zycie z dn. ...); opcjonalnie DOC_ID jako filtr")
    ap.add_argument("--from", dest="from_date", default=None, metavar="RRRR-MM-DD",
                    help="dla --upcoming: najwczesniejsza data wejscia w zycie (domyslnie dzisiaj)")
    ap.add_argument("--verify-md", nargs="+", metavar="PLIK.md",
                    help="zweryfikuj odnosniki [DOC art. N] i cytaty w cudzyslowach polskich w plikach markdown")
    args = ap.parse_args(argv)

    path = Path(args.file)
    if not path.exists():
        print(f"BLAD: brak pliku {path}", file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if args.verify_md:
        return verify_md(args.verify_md, path)

    if args.upcoming:
        only = set([args.doc_id] + list(args.articles)) if args.doc_id else set()
        only |= {q.rpartition(":")[0] if ":" in q else q for q in args.query}
        return upcoming(path, only, args.from_date, args.out)

    # zapytania: (doc_id, art|None)
    queries: list[tuple[str, str | None]] = []
    if args.doc_id:
        if args.articles:
            queries += [(args.doc_id, norm_art(a)) for a in args.articles]
        else:
            queries.append((args.doc_id, None))
    for q in args.query:
        # DOC_ID moze zawierac '#', ale nie ':' - rozdzielamy po ostatnim ':'
        if ":" in q:
            d, _, a = q.rpartition(":")
        else:
            d, a = q, ""
        queries.append((d, norm_art(a) if a else None))
    if not queries:
        ap.error("podaj doc_id [art ...], --query DOC_ID:ART albo --verify-md PLIK.md")

    rx = re.compile(args.grep, re.I) if args.grep else None
    wanted_docs = {d for d, _ in queries}
    by_doc: dict[str, list[str | None]] = {}
    for d, a in queries:
        by_doc.setdefault(d, []).append(a)

    out = open(args.out, "w", encoding="utf-8", newline="\n") if args.out else None

    def emit(s: str):
        if out:
            out.write(s + "\n")
        else:
            print(s)

    hits: dict[tuple[str, str | None], int] = {}
    arts_of: dict[str, list[str]] = {d: [] for d in wanted_docs}
    meta_done: set[str] = set()
    seen_docs: set[str] = set()
    par_open: dict[tuple[str, str], bool] = {}

    with open(path, "rb") as f:
        for line in f:
            did = doc_id_of(line)
            if did is None or did not in wanted_docs:
                continue
            seen_docs.add(did)
            try:
                row = json.loads(line)
            except Exception:
                continue
            art = row.get("article")
            if args.list_articles:
                if art is not None and art not in arts_of[did]:
                    arts_of[did].append(art)
                if args.meta and did not in meta_done:
                    meta_done.add(did)
                    emit(f"## {did} | {row.get('display_address')} | {row.get('title')} | status={row.get('status')} | {row.get('kategoria')}")
                continue
            for want in by_doc[did]:
                text = row.get("text", "")
                if want is not None and want.startswith("§"):
                    seg, par_open[(did, want)] = par_piece(text, want, par_open.get((did, want), False))
                    if seg is None:
                        continue
                    text = seg
                elif want is not None and norm_art(art) != want:
                    continue
                key = (did, want)
                if hits.get(key, 0) >= args.max_hits:
                    continue
                if rx and not rx.search(text):
                    continue
                hits[key] = hits.get(key, 0) + 1
                if args.max_chars and len(text) > args.max_chars:
                    text = text[: args.max_chars] + " [...]"
                if args.json:
                    r = dict(row)
                    r["text"] = text
                    emit(json.dumps(r, ensure_ascii=False))
                else:
                    if args.meta and did not in meta_done:
                        meta_done.add(did)
                        emit(f"## {did} | {row.get('display_address')} | {row.get('title')} | status={row.get('status')} | {row.get('kategoria')} | {row.get('source_url')}")
                    emit(f"--- [{did} art. {art}] ord={row.get('ord')} heading={row.get('heading')}")
                    emit(text)

    missing = 0
    if args.list_articles:
        for d in sorted(wanted_docs):
            if d not in seen_docs:
                emit(f"BRAK DOKUMENTU: {d}")
                missing += 1
            else:
                emit(f"{d}: {len(arts_of[d])} artykulow: " + ", ".join(arts_of[d]))
    else:
        for d, a in queries:
            if d not in seen_docs:
                emit(f"BRAK DOKUMENTU: {d}")
                missing += 1
            elif hits.get((d, a), 0) == 0:
                emit(f"BRAK TRAFIEN: {d} art. {a if a else '(caly dokument)'}" + (f" grep={args.grep}" if rx else ""))
                missing += 1
    if out:
        out.close()
    return 3 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
