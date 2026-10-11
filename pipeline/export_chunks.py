#!/usr/bin/env python
"""Eksport dane/ (HTML + PDF) -> pipeline/out/chunks.jsonl (format: docs/SPEC.md).

Ekstraktor PDF: PyMuPDF (pymupdf) - poprawne polskie znaki, ~15x szybszy od pypdf.
Użycie:
  python pipeline/export_chunks.py [--resume] [--kategorie ujednolicone,jednolite,...]
                                   [--limit N] [--workers N] [--out PLIK] [--doc DU/1964/93#U,...]
  python pipeline/export_chunks.py --changed stan/zmiany.json [--out PLIK] [--dane DIR]
      tryb przyrostowy: usuwa z --out wiersze changed+removed, eksportuje added+changed, dopisuje atomowo
      (plik tymczasowy + os.replace) i zapisuje chunks_delta.jsonl (tylko nowe wiersze) obok --out.
"""
import argparse
import html as htmlmod
import json
import multiprocessing as mp
import os
import re
import sys
import time
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DANE = ROOT / "dane"
OUT = Path(__file__).resolve().parent / "out"
MAX_CHUNK = 6000
TARGET = 2000
FFFD = "�"
MIN_TEXT = 150  # mniej znaków po czyszczeniu = brak warstwy tekstowej (skan)
ELI_API = "https://api.sejm.gov.pl/eli/acts"

# ----------------------------------------------------------------- metadane


def load_meta(dane=None):
    dane = Path(dane) if dane else DANE
    meta = {}  # (eli, wariant) -> rekord
    for fn in ("indeks_obowiazujacych.json", "indeks_mp.json", "indeks_ujednolicone.json"):
        p = dane / fn
        if not p.exists():
            continue
        for a in json.loads(p.read_text(encoding="utf-8")):
            eli = a.get("ELI") or f"{a.get('publisher')}/{a.get('year')}/{a.get('pos')}"
            uj = fn == "indeks_ujednolicone.json"
            meta[(eli, "U" if uj else "")] = a
    return meta


def file_key(name):
    m = re.match(r"^(U-)?(DU|MP)_(\d{4})_(\d+)\.(html|pdf)$", name)
    if not m:
        return None
    u, pub, y, pos, ext = m.groups()
    return (f"{pub}/{y}/{pos}", "U" if u else "", ext)


def list_docs(meta, kategorie, dane=None):
    """-> lista (doc_id, eli, wariant, sciezka, kategoria, rekord). Jedna pozycja na doc_id (HTML przed PDF).
    Katalogi zaczynajace sie od '_' (np. _wycofane) sa pomijane - to nie sa akty obowiazujace."""
    best = {}
    dane = Path(dane) if dane else DANE
    for d in sorted(p for p in dane.iterdir() if p.is_dir() and not p.name.startswith("_")):
        for f in d.iterdir():
            k = file_key(f.name)
            if not k:
                continue
            eli, var, ext = k
            rec = meta.get((eli, var))
            if rec is None and var == "":
                continue  # brak w indeksach - pomijamy
            if rec is None:
                continue
            kat = "ujednolicone" if var == "U" else rec.get("kategoria") or d.name
            if kategorie and kat not in kategorie:
                continue
            doc_id = eli + ("#U" if var else "")
            prev = best.get(doc_id)
            if prev is None or (ext == "html" and prev[3].suffix == ".pdf"):
                best[doc_id] = (doc_id, eli, var, f, kat, rec)
    return sorted(best.values(), key=lambda x: (x[4], x[0]))


# ----------------------------------------------------------------- ekstrakcja tekstu


class _H2T(HTMLParser):
    BLOCK = {"div", "p", "h1", "h2", "h3", "h4", "h5", "li", "ul", "ol", "tr", "table", "br", "section"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.skip = 0
        self.stack = []  # (tag, flags)
        self.cite = 0
        self.in_arti_h = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = (a.get("class") or "").lower()
        if tag in ("script", "style", "head"):
            self.skip += 1
            self.stack.append((tag, "skip"))
            return
        fl = ""
        if tag == "div":
            if a.get("id") == "toc" or "gloss-section" in cls:
                self.skip += 1
                fl = "skip"
            elif "cite-box" in cls:
                self.cite += 1
                fl = "cite"
            elif "unit_arti" in cls:
                fl = "arti"
            elif cls.startswith("unit "):
                fl = "unit"
            elif cls == "unit-inner":
                fl = "inner"
        if tag == "h3" and self.stack and self.stack[-1][1] == "arti" and self.cite == 0:
            self.in_arti_h += 1
            fl = "artih"
        if tag in ("void",):
            pass
        if tag not in ("br", "img", "meta", "link", "hr"):
            self.stack.append((tag, fl))
        if tag == "span" and (a.get("class") or "").startswith("head-"):
            self.out.append("\n")
        if tag == "sup":
            self.out.append("[" if self.in_arti_h else "\x02")
        elif tag == "h3" and self.stack[:-1] and self.stack[-2][1] in ("arti", "unit"):
            pass  # numer jednostki w tej samej linii co tresc
        elif tag == "div" and fl == "inner":
            pass
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in ("br", "img", "meta", "link", "hr"):
            return
        # znajdz odpowiadajacy start
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                fl = self.stack[i][1]
                del self.stack[i:]
                if fl == "skip":
                    self.skip -= 1
                elif fl == "cite":
                    self.cite -= 1
                elif fl == "artih":
                    self.in_arti_h -= 1
                break
        if tag == "sup":
            self.out.append("]" if self.in_arti_h else "\x03")
        elif tag == "h3":
            self.out.append(" ")
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if self.skip:
            return
        if self.cite and data.strip().startswith("Art."):
            data = "„" + data.lstrip()
        self.out.append(data)


def html_to_text(b):
    try:
        s = b.decode("utf-8")
    except UnicodeDecodeError:
        s = b.decode("cp1250", errors="replace")
    p = _H2T()
    p.feed(s)
    t = "".join(p.out)
    t = t.replace("\xa0", " ")
    # przypisy typu <sup>1)</sup> -> usun; inne <sup>x</sup> -> [x] jak w ISAP PDF
    t = re.sub(r"\x02\s*\d+\)\s*\x03", "", t)
    t = re.sub(r"\x02\s*([^\x02\x03]{1,6}?)\s*\x03", r"[\1]", t)
    t = t.replace("\x02", "").replace("\x03", "")
    lines = [re.sub(r"[ \t]+", " ", l).strip() for l in t.split("\n")]
    # "Art. 46 [1]." -> "Art. 46[1]."
    lines = [re.sub(r"^(Art\. \d+[a-z]*) ?\[(\d+)\]", r"\1[\2]", l) for l in lines]
    res = []
    tok = r"(?:Art\. \d+[a-z]{0,3}(?:\[\d+\])?[a-z]{0,2}\.|\d+[a-z]{0,3}(?:\[\d+\])?[.)]|[a-ząćęłńóśźż]{1,2}\)|[-–—])"
    lab = re.compile(r"^(?:" + tok + r" ?)+$")
    for l in lines:
        if not l:
            continue
        if res and lab.match(res[-1]):
            res[-1] = res[-1] + " " + l  # numer jednostki w tej samej linii co treść
        else:
            res.append(l)
    return "\n".join(res)


_FOOT = re.compile(r"^(©\s*Kancelaria Sejmu|s\. \d+/\d+|\d{4}-\d{2}-\d{2})\s*$")


def pdf_to_text(path):
    import pymupdf
    doc = pymupdf.open(str(path))
    parts = []
    for page in doc:
        t = page.get_text()
        lines = [l.strip() for l in t.split("\n")]
        lines = [l for l in lines if not _FOOT.match(l)]
        parts.append("\n".join(lines))
    doc.close()
    t = "\n".join(parts).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", l).strip() for l in t.split("\n")]
    lines = [l for l in lines if l]
    return join_lines(lines)


_NEWPAR = re.compile(
    r"^(Art\.\s|§\s?\d|\d+[a-z]?\)\s|\d+[a-z]?\.\s|[a-ząćęłńóśźż]{1,2}\)\s|[-–—]\s|"
    r"(KSIĘGA|CZĘŚĆ|TYTUŁ|DZIAŁ|ROZDZIAŁ|Rozdział|Dział|Oddział|ODDZIAŁ|Tytuł|Księga|Część)\s+[IVXLCDM\d]+[a-z]?\s*$|"
    r"(Dz\.\s?U\.|M\.\s?P\.)|\d+\)\s)"
)


def join_lines(lines):
    """Skleja łamane wiersze PDF w akapity (nowy akapit przy Art./§/pkt/ust.)."""
    out = []
    for l in lines:
        if not out:
            out.append(l)
        elif _HEAD.match(out[-1]) or _HEAD.match(l) or _NEWPAR.match(l) or re.match(r"^[A-ZĄĆĘŁŃÓŚŹŻ0-9 ,.\-–„”()]{6,}$", l) or out[-1].endswith(("\x00",)):
            out.append(l)
        elif re.match(r"^(?:Art\. \d+|§ \d+)", out[-1]) and False:
            out.append(l)
        else:
            if out[-1].endswith("-") and l[:1].islower():
                out[-1] = out[-1][:-1] + l
            else:
                out[-1] += " " + l
    return "\n".join(out)


# ----------------------------------------------------------------- dzielenie

_HEAD = re.compile(
    r"^(KSIĘGA|CZĘŚĆ|TYTUŁ|DZIAŁ|ROZDZIAŁ|ODDZIAŁ|Księga|Część|Tytuł|Dział|Rozdział|Oddział)\s+"
    r"([IVXLCDM]+[a-z]?|\d+[a-z]?|[A-ZĄĆĘŁŃÓŚŹŻ]{3,}(?: [A-ZĄĆĘŁŃÓŚŹŻ]{3,})?|[a-ząćęłńóśźż]{4,12})\s*$"
)
_LEVEL = {"KSIĘGA": 1, "CZĘŚĆ": 1.5, "TYTUŁ": 2, "DZIAŁ": 3, "ROZDZIAŁ": 4, "ODDZIAŁ": 5}
_ART = re.compile(r"^Art\.\s(\d+[a-z]{0,3}(?:\[\d+\])?[a-z]{0,2})\.(?=\s|$)")


def split_long(text, limit=MAX_CHUNK, target=None):
    """Dzieli tekst na kawałki <= limit, preferując granice § / linii / zdań."""
    target = target or limit
    if len(text) <= limit:
        return [text]
    out, cur = [], ""
    pieces = re.split(r"(?=\n§ ?\d)", text) if target == limit else text.split("\n")
    pieces2 = []
    for p in pieces:  # zbyt długie kawałki tnij dalej
        while len(p) > limit:
            cut = max(p.rfind("\n", 0, limit), p.rfind(". ", 0, limit) + 1, p.rfind("; ", 0, limit) + 1)
            if cut < limit // 3:
                cut = p.rfind(" ", 0, limit)
            if cut <= 0:
                cut = limit
            pieces2.append(p[:cut])
            p = p[cut:].lstrip()
        pieces2.append(p)
    for p in pieces2:
        sep = "" if target == limit and p.startswith("\n") else "\n"
        if cur and len(cur) + len(p) + 1 > target:
            out.append(cur.strip())
            cur = p.lstrip("\n")
        else:
            cur = cur + (sep if cur else "") + p if cur else p.lstrip("\n")
    if cur.strip():
        out.append(cur.strip())
    return out


def chunk_text(text):
    """-> lista (article|None, heading, text)."""
    lines = text.split("\n")
    levels = {}
    heading = ""
    blocks = []  # [article, heading, [lines]]
    cur = [None, "", []]
    i = 0
    n = len(lines)
    has_art = False
    while i < n:
        l = lines[i]
        m = _HEAD.match(l)
        if m and has_art or (m and i + 1 < n and not _ART.match(lines[i + 1])):
            lvl = _LEVEL[m.group(1).upper()]
            lab = l
            if i + 1 < n and not _HEAD.match(lines[i + 1]) and not _ART.match(lines[i + 1]) and len(lines[i + 1]) < 160:
                lab = f"{l} {lines[i + 1]}"
                i += 1
            for k in [k for k in levels if k >= lvl]:
                del levels[k]
            levels[lvl] = lab
            heading = " > ".join(levels[k] for k in sorted(levels))
            i += 1
            continue
        am = _ART.match(l)
        if am:
            if cur[2]:
                blocks.append(cur)
            cur = [am.group(1), heading, [l]]
            has_art = True
        else:
            if not cur[2] and cur[0] is None:
                cur[1] = heading
            cur[2].append(l)
        i += 1
    if cur[2]:
        blocks.append(cur)
    res = []
    if not has_art:
        full = "\n".join("\n".join(b[2]) for b in blocks)
        for part in split_long(full, MAX_CHUNK, TARGET):
            res.append((None, "", part))
        return res
    for art, head, ls in blocks:
        t = "\n".join(ls).strip()
        if not t:
            continue
        if art is None:  # część wstępna
            for part in split_long(t, MAX_CHUNK, TARGET):
                res.append((None, head, part))
        else:
            for part in split_long(t, MAX_CHUNK):
                res.append((art, head, part))
    return res


# ----------------------------------------------------------------- przetwarzanie dokumentu


def source_url(eli, var, ext, year, pos):
    if var == "U":
        pub = eli.split("/")[0]
        return f"{ELI_API}/{eli}/text/U/D{year}{int(pos):04d}Lj.pdf"
    return f"{ELI_API}/{eli}/text.{ext}"


def process(task):
    doc_id, eli, var, path, kat, rec = task
    t0 = time.time()
    try:
        path = Path(path)
        if path.suffix == ".html":
            text = html_to_text(path.read_bytes())
        else:
            text = pdf_to_text(path)
    except Exception as e:  # uszkodzony plik
        return doc_id, "error", f"{type(e).__name__}: {e}", [], 0, 0
    nf = text.count(FFFD)
    if nf:
        text = text.replace(FFFD, "")
    if len(re.sub(r"\W", "", text)) < MIN_TEXT:
        return doc_id, "notext", str(path), [], nf, time.time() - t0
    pub = rec.get("publisher") or eli.split("/")[0]
    year = rec.get("year") or int(eli.split("/")[1])
    pos = rec.get("pos") or int(eli.split("/")[2])
    status = rec.get("status")
    if var == "U":
        status = "obowiązujący"
    base = {
        "doc_id": doc_id, "eli": eli, "kategoria": kat, "publisher": pub, "year": year, "pos": pos,
        "title": rec.get("title", "").strip(), "display_address": rec.get("displayAddress"),
        "announcement_date": rec.get("announcementDate"), "status": status,
        "is_consolidated": var == "U", "source_url": source_url(eli, var, path.suffix[1:], year, pos),
    }
    lines = []
    for ord_, (art, head, t) in enumerate(chunk_text(text), 1):
        d = dict(base)
        d.update({"ord": ord_, "article": art, "heading": head, "text": t})
        lines.append(json.dumps(d, ensure_ascii=False))
    return doc_id, "ok", "", lines, nf, time.time() - t0


# ----------------------------------------------------------------- main


def done_ids(path):
    """Ucina niepełną ostatnią linię i zwraca zbiór doc_id już zapisanych."""
    ids = set()
    if not path.exists():
        return ids
    good = 0
    with open(path, "rb") as f:
        for raw in f:
            if not raw.endswith(b"\n"):
                break
            m = re.match(rb'\{"doc_id": ?"([^"]+)"', raw)
            if m:
                ids.add(m.group(1).decode("utf-8"))
            good += len(raw)
    if good != path.stat().st_size:
        with open(path, "r+b") as f:
            f.truncate(good)
    return ids


def final_scan(path):
    docs, chunks, fffd, size = set(), 0, 0, path.stat().st_size if path.exists() else 0
    per_kat = Counter()
    if path.exists():
        with open(path, "rb") as f:
            for raw in f:
                chunks += 1
                fffd += raw.count(b"\xef\xbf\xbd")
                m = re.match(rb'\{"doc_id": ?"([^"]+)"', raw)
                if m and m.group(1) not in docs:
                    docs.add(m.group(1))
                    k = re.search(rb'"kategoria": ?"([^"]+)"', raw)
                    per_kat[k.group(1).decode() if k else "?"] += 1
    return len(docs), chunks, fffd, size, per_kat


def pick_sample(docs, limit, must):
    byid = {d[0]: d for d in docs}
    sel = [byid[m] for m in must if m in byid]
    chosen = {d[0] for d in sel}
    cats = {}
    for d in docs:
        cats.setdefault(d[4], []).append(d)
    # rozkładaj równomiernie: co k-ty dokument z każdej kategorii (mix HTML/PDF)
    i = 0
    while len(sel) < limit and any(cats.values()):
        for k in list(cats):
            if len(sel) >= limit:
                break
            lst = cats[k]
            if not lst:
                continue
            step = max(1, len(lst) // 7)
            d = lst.pop(min(len(lst) - 1, (i * step) % len(lst)))
            if d[0] not in chosen:
                sel.append(d)
                chosen.add(d[0])
        i += 1
    return sel


# ----------------------------------------------------------------- tryb przyrostowy (--changed)

_DOCID_RE = re.compile(rb'\{"doc_id": ?"([^"]+)"')


def load_changes(path):
    """Czyta stan/zmiany.json -> (added, changed, removed) jako listy doc_id (bez duplikatow, kolejnosc zachowana)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: oczekiwano obiektu JSON z kluczami added/changed/removed")

    def lst(k):
        v = data.get(k) or []
        if not isinstance(v, list):
            raise ValueError(f"{path}: pole '{k}' musi byc lista")
        return list(dict.fromkeys(str(x) for x in v))

    return lst("added"), lst("changed"), lst("removed")


def _line_doc_id(raw):
    m = _DOCID_RE.match(raw)
    if m:
        return m.group(1).decode("utf-8")
    try:  # inna kolejnosc kluczy / spacje - pelny parse
        return json.loads(raw.decode("utf-8")).get("doc_id")
    except Exception:
        return None


def rewrite_chunks(out, drop_ids, delta_path):
    """Atomowo: out := out bez wierszy doc_id z drop_ids + zawartosc delta_path.
    Zapis do pliku tymczasowego obok, fsync, os.replace. Zwraca (usuniete_wiersze, dopisane_wiersze, ucieta_niepelna_linia)."""
    out = Path(out)
    tmp = out.with_name(out.name + ".tmp")
    removed = added = 0
    truncated = False
    try:
        with open(tmp, "wb") as fo:
            if out.exists():
                with open(out, "rb") as fi:
                    for raw in fi:
                        if not raw.endswith(b"\n"):
                            truncated = True  # niepelna ostatnia linia (przerwany zapis) - odrzucamy
                            break
                        if drop_ids and _line_doc_id(raw) in drop_ids:
                            removed += 1
                            continue
                        fo.write(raw)
            if delta_path and Path(delta_path).exists():
                with open(delta_path, "rb") as fd:
                    for raw in fd:
                        if not raw.endswith(b"\n"):
                            raw += b"\n"
                        fo.write(raw)
                        added += 1
            fo.flush()
            os.fsync(fo.fileno())
        os.replace(tmp, out)
    except BaseException:
        if tmp.exists():
            tmp.unlink()
        raise
    return removed, added, truncated


def _update_list_file(path, drop_ids, new_entries):
    """Plik 'doc_id<TAB>info' (bez_tekstu.txt / bledy.txt): zwraca wpisy bez drop_ids plus new_entries."""
    path = Path(path)
    old = []
    if path.exists():
        old = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    keep = [l for l in old if l.split("\t")[0] not in drop_ids]
    return keep + list(new_entries)


def main_changed(a):
    t0 = time.time()
    out = Path(a.out)
    outdir = out.parent
    outdir.mkdir(parents=True, exist_ok=True)
    dane = Path(a.dane) if a.dane else DANE
    added, changed, removed = load_changes(a.changed)
    to_export = list(dict.fromkeys(added + changed))
    print(f"zmiany: added={len(added)} changed={len(changed)} removed={len(removed)}", flush=True)
    kat = {k.strip() for k in a.kategorie.split(",") if k.strip()}
    meta = load_meta(dane)
    avail = {d[0]: d for d in list_docs(meta, kat, dane)} if to_export else {}
    missing = [i for i in to_export if i not in avail]
    for i in missing:
        print(f"! OSTRZEZENIE: brak pliku/metadanych dla {i} (wycofany lub spoza indeksow) - pomijam", file=sys.stderr, flush=True)
    todo = [avail[i] for i in to_export if i in avail]
    tasks = [(d[0], d[1], d[2], str(d[3]), d[4], d[5]) for d in todo]

    delta = outdir / "chunks_delta.jsonl"
    delta_tmp = delta.with_name(delta.name + ".tmp")
    ok_ids, notext_ids, notext_new, errors = [], [], [], []
    nd = nc = nf = 0
    fffd_docs = []
    try:
        with open(delta_tmp, "wb") as fo:
            if tasks:
                workers = max(1, min(a.workers, len(tasks)))
                with mp.Pool(workers) as pool:
                    for doc_id, st, info, lines, fcount, dt in pool.imap_unordered(process, tasks, 1):
                        if st == "ok":
                            fo.write(("\n".join(lines) + "\n").encode("utf-8"))
                            ok_ids.append(doc_id)
                            nd += 1
                            nc += len(lines)
                        elif st == "notext":
                            notext_ids.append(doc_id)
                            notext_new.append(f"{doc_id}\t{info}")
                        else:
                            errors.append(f"{doc_id}\t{info}")
                        if fcount:
                            nf += fcount
                            fffd_docs.append(doc_id)
            fo.flush()
            os.fsync(fo.fileno())
        os.replace(delta_tmp, delta)
    except BaseException:
        if delta_tmp.exists():
            delta_tmp.unlink()
        raise

    # Co usunac ze starego chunks.jsonl: removed + dokumenty, ktorych nowy stan znamy (ok / brak warstwy tekstowej).
    # Dokumenty z bledem ekstrakcji lub bez pliku zachowuja stare wiersze (lepsze stare niz brak).
    drop = set(removed) | set(ok_ids) | set(notext_ids)
    n_rm, n_add, trunc = rewrite_chunks(out, drop, delta)
    if trunc:
        print("! OSTRZEZENIE: ucieto niepelna ostatnia linie w chunks.jsonl", file=sys.stderr)

    nt_f = outdir / "bez_tekstu.txt"
    notext_all = _update_list_file(nt_f, drop, notext_new)
    nt_f.write_text("\n".join(notext_all) + ("\n" if notext_all else ""), encoding="utf-8")
    er_f = outdir / "bledy.txt"
    err_all = _update_list_file(er_f, drop | {e.split("\t")[0] for e in errors}, errors)
    if err_all:
        er_f.write_text("\n".join(err_all) + "\n", encoding="utf-8")
    elif er_f.exists():
        er_f.unlink()

    tot_d, tot_c, tot_f, size, per_kat = final_scan(out)
    rep = [
        f"Raport eksportu (--changed) {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Zmiany wejsciowe: added={len(added)}, changed={len(changed)}, removed={len(removed)}; czas {time.time() - t0:.1f} s",
        f"Usunieto wierszy ze starego pliku: {n_rm}; dopisano wierszy: {n_add} (dokumentow {nd}, fragmentow {nc}) -> {delta.name}",
        f"Pominiete (brak pliku/metadanych, stare wiersze zachowane): {len(missing)}" + (f" ({', '.join(missing[:20])})" if missing else ""),
        f"Bez warstwy tekstowej w tym przebiegu: {len(notext_new)}; bledow ekstrakcji (stare wiersze zachowane): {len(errors)}",
        f"U+FFFD usunięte z tekstu źródłowego w tym przebiegu: {nf}" + (f" (doc: {', '.join(fffd_docs[:20])})" if fffd_docs else ""),
        f"RAZEM w {out.name}: dokumentów {tot_d}, fragmentów {tot_c}, U+FFFD w pliku {tot_f}, rozmiar {size / 1e6:.1f} MB",
        "Dokumenty wg kategorii: " + ", ".join(f"{k}={v}" for k, v in sorted(per_kat.items())),
    ]
    (outdir / "raport.txt").write_text("\n".join(rep) + "\n", encoding="utf-8")
    print("\n".join(rep))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--kategorie", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) // 2))
    ap.add_argument("--out", default=str(OUT / "chunks.jsonl"))
    ap.add_argument("--doc", default="", help="lista doc_id po przecinku (tylko te)")
    ap.add_argument("--changed", metavar="ZMIANY_JSON",
                    help="tryb przyrostowy: stan/zmiany.json - usun changed+removed z --out, wyeksportuj added+changed i dopisz")
    ap.add_argument("--dane", default="", help="katalog z danymi (domyslnie dane/ w korzeniu repo)")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if a.changed:
        if a.resume or a.doc or a.limit:
            sys.exit("--changed nie laczy sie z --resume/--doc/--limit")
        try:
            return main_changed(a)
        except (OSError, ValueError) as e:
            sys.exit(f"Blad trybu --changed: {e}")
    out = Path(a.out)
    outdir = out.parent  # raporty obok pliku wyjsciowego (domyslnie pipeline/out)
    outdir.mkdir(parents=True, exist_ok=True)
    notext_f = outdir / "bez_tekstu.txt"
    kat = {k.strip() for k in a.kategorie.split(",") if k.strip()}
    t0 = time.time()
    meta = load_meta(a.dane or None)
    docs = list_docs(meta, kat, a.dane or None)
    print(f"dokumentów w dane/: {len(docs)}", flush=True)
    if a.doc:
        want = {x.strip() for x in a.doc.split(",")}
        docs = [d for d in docs if d[0] in want]
    elif a.limit:
        docs = pick_sample(docs, a.limit, ["DU/1964/93#U", "DU/1974/141#U", "DU/1974/141"])
    skip = set()
    notext_old = []
    if a.resume:
        skip = done_ids(out)
        if notext_f.exists():
            notext_old = [l for l in notext_f.read_text(encoding="utf-8").splitlines() if l.strip()]
            skip |= {l.split("\t")[0] for l in notext_old}
    elif out.exists():
        out.unlink()
    todo = [d for d in docs if d[0] not in skip]
    print(f"do przetworzenia: {len(todo)} (pominięte: {len(docs) - len(todo)})", flush=True)
    # duże PDF-y najpierw nie są potrzebne; tasks idą w kolejności, chunksize 1
    tasks = [(d[0], d[1], d[2], str(d[3]), d[4], d[5]) for d in todo]
    notext = list(notext_old) if a.resume else []
    errors, fffd_docs = [], []
    nd = nc = nf = 0
    mode = "ab" if a.resume else "wb"
    with open(out, mode) as fo:
        with mp.Pool(a.workers) as pool:
            for k, (doc_id, st, info, lines, fcount, dt) in enumerate(pool.imap_unordered(process, tasks, 1), 1):
                if st == "ok":
                    fo.write(("\n".join(lines) + "\n").encode("utf-8"))
                    nd += 1
                    nc += len(lines)
                elif st == "notext":
                    notext.append(f"{doc_id}\t{info}")
                else:
                    errors.append(f"{doc_id}\t{info}")
                if fcount:
                    nf += fcount
                    fffd_docs.append(doc_id)
                if k % 200 == 0:
                    fo.flush()
                    print(f"  {k}/{len(tasks)} {time.time() - t0:.0f}s", flush=True)
    notext_f.write_text("\n".join(notext) + ("\n" if notext else ""), encoding="utf-8")
    if errors:
        (outdir / "bledy.txt").write_text("\n".join(errors) + "\n", encoding="utf-8")
    tot_d, tot_c, tot_f, size, per_kat = final_scan(out)
    rep = [
        f"Raport eksportu {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Ekstraktor PDF: PyMuPDF; workerów: {a.workers}; czas tego przebiegu: {time.time() - t0:.1f} s",
        f"Ten przebieg: dokumentów {nd}, fragmentów {nc}, bez tekstu {len(notext) - len(notext_old)}, błędów {len(errors)}",
        f"U+FFFD usunięte z tekstu źródłowego w tym przebiegu: {nf}" + (f" (doc: {', '.join(fffd_docs[:20])})" if fffd_docs else ""),
        f"RAZEM w {out.name}: dokumentów {tot_d}, fragmentów {tot_c}, U+FFFD w pliku {tot_f}, rozmiar {size / 1e6:.1f} MB",
        "Dokumenty wg kategorii: " + ", ".join(f"{k}={v}" for k, v in sorted(per_kat.items())),
        f"Pliki bez warstwy tekstowej (skany) łącznie: {len(notext)} -> {notext_f.name}",
    ]
    (outdir / "raport.txt").write_text("\n".join(rep) + "\n", encoding="utf-8")
    print("\n".join(rep))
    return 0


if __name__ == "__main__":
    mp.freeze_support()
    sys.exit(main() or 0)
