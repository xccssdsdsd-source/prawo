"""Wspolna biblioteka fetcherow zrodel dodatkowych (zrodla/saos, zrodla/eurlex, ...).

Zawiera: HTTP z retry/backoffem/limitem tempa i walidacja Content-Type, konwersje HTML -> tekst,
dzielenie tekstu na fragmenty, walidacje wiersza chunks.jsonl wg docs/SPEC.md, zapis atomowy JSONL,
stan przyrostowy w stan/zrodlo_<id>.json oraz wspolne argumenty wiersza polecen.

Tylko biblioteka standardowa (urllib) - bez dodatkowych zaleznosci. Pliki zapisywane jako UTF-8.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html as htmlmod
import json
import os
import re
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZRODLA_DIR = ROOT / "zrodla"
DEFAULT_STAN_DIR = ROOT / "stan"
DEFAULT_OUT_DIR = ROOT / "pipeline" / "out"

USER_AGENT = os.environ.get(
    "PRAWO_USER_AGENT",
    "prawo-fetcher/1.0 (otwarty projekt: wyszukiwarka prawa polskiego dla modeli AI; "
    "przyrostowe, grzeczne pobieranie; kontakt: wlasciciel repozytorium)",
)

KATEGORIE = {"ujednolicone", "jednolite", "podstawowe", "zmieniajace", "mp", "orzeczenie",
             "umowa", "inne", "wyrok", "ue"}
MAX_CHUNK = 6000          # twardy limit wg docs/SPEC.md
EXIT_OK, EXIT_ERROR, EXIT_UNAVAILABLE = 0, 1, 3  # 3 = zrodlo niedostepne (przerwa techniczna / blokada)

FFFD = chr(0xFFFD)


def log(msg: str) -> None:
    print(msg, flush=True)


def warn(msg: str) -> None:
    print("! " + msg, file=sys.stderr, flush=True)


def setup_console() -> None:
    """Konsola Windows (cp1250/cp852) potrafi wywrocic print() na polskich znakach - nie wywracaj fetchera."""
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(errors="replace")
        except Exception:
            pass


def now_iso() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat()


# ------------------------------------------------------------------ HTTP

class FetchError(Exception):
    """Blad pobierania (po wyczerpaniu ponowien)."""


class HttpStatus(FetchError):
    def __init__(self, status: int, url: str, body: bytes = b""):
        super().__init__(f"HTTP {status} dla {url}")
        self.status = status
        self.url = url
        self.body = body


class NotExpectedContent(FetchError):
    """Serwer odpowiedzial 200, ale innym typem tresci niz oczekiwany (np. strona 'Przerwa techniczna' zamiast JSON)."""


class Response:
    def __init__(self, status: int, headers: dict, body: bytes, url: str):
        self.status = status
        self.headers = headers
        self.body = body
        self.url = url

    @property
    def content_type(self) -> str:
        return (self.headers.get("content-type") or "").lower()

    def text(self) -> str:
        return decode_body(self.body, self.content_type)[0]

    def json(self):
        return json.loads(self.body.decode("utf-8"))


# punkty wstrzykiwania dla testow (mock bez sieci)
urlopen = urllib.request.urlopen
sleep = time.sleep
monotonic = time.monotonic


class RateLimiter:
    """Minimalny odstep miedzy kolejnymi zapytaniami (jedno zrodlo = jeden limiter, brak rownoleglosci)."""

    def __init__(self, min_interval: float = 1.0):
        self.min_interval = float(min_interval)
        self._last = None

    def wait(self) -> None:
        if self._last is not None and self.min_interval > 0:
            left = self.min_interval - (monotonic() - self._last)
            if left > 0:
                sleep(left)
        self._last = monotonic()


def _kind_ok(kind: str, ctype: str, body: bytes) -> bool:
    if kind == "json":
        return "json" in ctype
    if kind == "xml":
        return "xml" in ctype
    if kind == "pdf":
        return "pdf" in ctype or body[:5] == b"%PDF-"
    if kind == "html":
        return "html" in ctype or "xml" in ctype
    return True  # "any"


def http_get(url: str, *, headers: dict | None = None, expect: str = "any", timeout: float = 120,
             retries: int = 3, backoff: float = 5.0, limiter: RateLimiter | None = None,
             retry_unexpected: int | None = None, max_bytes: int = 64 * 1024 * 1024) -> Response:
    """GET z ponowieniami. expect: json | xml | html | pdf | any.

    Ponawia (z narastajacym opoznieniem): bledy sieci/timeouty, 429, 5xx (z Retry-After) - do `retries` razy;
    niezgodny Content-Type (np. HTML 'Przerwa techniczna' zamiast JSON) - do `retry_unexpected` razy
    (domyslnie tyle co `retries`). Pozostale 4xx -> HttpStatus od razu. Po wyczerpaniu: FetchError /
    NotExpectedContent / HttpStatus.
    """
    hdr = {"User-Agent": USER_AGENT, "Accept-Encoding": "identity"}
    hdr.update(headers or {})
    max_unexp = retries if retry_unexpected is None else retry_unexpected
    n_err = n_unexp = 0
    while True:
        if limiter:
            limiter.wait()
        failure: Exception
        wait_s = backoff * (2 ** max(n_err, n_unexp))
        try:
            req = urllib.request.Request(url, headers=hdr)
            with urlopen(req, timeout=timeout) as r:
                body = r.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise FetchError(f"odpowiedz wieksza niz {max_bytes} B: {url}")
                resp = Response(getattr(r, "status", 200),
                                {k.lower(): v for k, v in r.headers.items()}, body, r.geturl() or url)
            if _kind_ok(expect, resp.content_type, body):
                return resp
            failure = NotExpectedContent(
                f"oczekiwano {expect}, serwer zwrocil Content-Type '{resp.content_type}' "
                f"({len(body)} B) dla {url} - zrodlo moze byc w przerwie technicznej")
            n_unexp += 1
            if n_unexp > max_unexp:
                raise failure
        except urllib.error.HTTPError as e:
            body = b""
            try:
                body = e.read(4096)
            except Exception:
                pass
            if not (e.code == 429 or e.code >= 500):
                raise HttpStatus(e.code, url, body)
            ra = e.headers.get("Retry-After") if e.headers else None
            if ra and ra.isdigit():
                wait_s = max(wait_s, min(int(ra), 300))
            failure = HttpStatus(e.code, url, body)
            n_err += 1
            if n_err > retries:
                raise failure
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            failure = FetchError(f"blad sieci ({type(e).__name__}: {e}) dla {url}")
            n_err += 1
            if n_err > retries:
                raise failure
        warn(f"ponowienie za {wait_s:.0f}s: {failure}")
        sleep(wait_s)


def decode_body(body: bytes, content_type: str = "") -> tuple[str, int]:
    """bajty -> str. Charset z Content-Type, domyslnie UTF-8; przy bledzie dekodowania cp1250 (+licznik znakow zastepczych)."""
    m = re.search(r"charset=([\w\-]+)", content_type or "", re.I)
    enc = (m.group(1) if m else "utf-8").lower()
    try:
        s = body.decode(enc)
    except (UnicodeDecodeError, LookupError):
        try:
            s = body.decode("utf-8")
        except UnicodeDecodeError:
            s = body.decode("cp1250", errors="replace")
    if s.startswith(chr(0xFEFF)):
        s = s[1:]
    return s, s.count(FFFD)


# ------------------------------------------------------------------ tekst / HTML

_WS = re.compile(r"[ \t\r\n\f\v\u00a0\u2000-\u200b\u202f\u205f\u3000]+")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text(s: str) -> tuple[str, int]:
    """Usuwa U+FFFD i znaki sterujace, normalizuje do NFC. Zwraca (tekst, liczba_usunietych_U+FFFD)."""
    n = s.count(FFFD)
    if n:
        s = s.replace(FFFD, "")
    s = _CTRL.sub("", s)
    return unicodedata.normalize("NFC", s), n


def normalize_line(s: str) -> str:
    return _WS.sub(" ", s).strip()


_BLOCK = {"p", "div", "br", "li", "tr", "table", "tbody", "thead", "tfoot", "hr", "blockquote", "ul", "ol",
          "section", "article", "center", "pre", "dd", "dt", "dl", "h1", "h2", "h3", "h4", "h5", "h6", "body",
          "html", "form", "fieldset", "caption", "header", "footer"}
_SKIP = {"script", "style", "head", "noscript", "template"}
_CELL = {"td", "th"}


class _Blocks(HTMLParser):
    """HTML -> lista blokow (klasa_css, tekst). Granice: znaczniki blokowe; komorki tabel rozdzielone spacja."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: list[tuple[str, str]] = []
        self._buf: list[str] = []
        self._cls = ""
        self._skip = 0
        self._skip_a = False
        self._row = 0  # wewnatrz <tr> akapity w komorkach nie lamia linii (numer + tresc punktu = jedna linia)

    def _flush(self):
        t = normalize_line("".join(self._buf))
        self._buf = []
        if t:
            self.blocks.append((self._cls, t))

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in _SKIP:
            self._skip += 1
            return
        if tag == "a" and (a.get("href") or "").startswith("#ntr"):
            self._skip_a = True  # odnosnik do przypisu "(1)"
            return
        if tag == "tr":
            self._flush()
            self._row += 1
            self._cls = (a.get("class") or "").strip()
        elif tag in _BLOCK:
            if self._row and tag in ("p", "div", "br", "li"):
                self._buf.append(" ")
            else:
                self._flush()
                self._cls = (a.get("class") or "").strip()
        elif tag in _CELL:
            self._buf.append(" ")

    def handle_endtag(self, tag):
        if tag in _SKIP:
            self._skip = max(0, self._skip - 1)
            return
        if tag == "a":
            self._skip_a = False
            return
        if tag == "tr":
            self._row = max(0, self._row - 1)
            self._flush()
        elif tag in _BLOCK:
            if self._row and tag in ("p", "div", "li"):
                self._buf.append(" ")
            else:
                self._flush()
        elif tag in _CELL:
            self._buf.append(" ")

    def handle_data(self, data):
        if self._skip or self._skip_a:
            return
        self._buf.append(data)

    def close(self):
        super().close()
        self._flush()


def html_blocks(html_text: str) -> list[tuple[str, str]]:
    p = _Blocks()
    p.feed(html_text)
    p.close()
    return p.blocks


def html_to_lines(html_text: str) -> list[str]:
    return [t for _, t in html_blocks(html_text)]


def html_to_text(html_text: str) -> str:
    return "\n".join(html_to_lines(html_text))


# ------------------------------------------------------------------ dzielenie na fragmenty

_SENT = re.compile(r"(?<=[.!?;:])\s+(?=[\"„(\[A-ZĄĆĘŁŃÓŚŹŻ0-9§])")


def _hard_cut(s: str, limit: int) -> list[str]:
    out = []
    while len(s) > limit:
        cut = s.rfind(" ", int(limit * 0.5), limit)
        if cut <= 0:
            cut = limit
        out.append(s[:cut].rstrip())
        s = s[cut:].lstrip()
    if s:
        out.append(s)
    return out


def split_text(text: str, target: int = 2000) -> list[str]:
    """Dzieli tekst (akapity rozdzielone '\\n') na fragmenty o dlugosci <= target.

    Najpierw laczy calosc akapitow, a akapit dluzszy niz target tnie po zdaniach, a w ostatecznosci po spacji."""
    if target < 200:
        raise ValueError("target za maly")
    segs: list[str] = []
    for para in text.split("\n"):
        para = para.strip()
        if not para:
            continue
        if len(para) <= target:
            segs.append(para)
            continue
        cur = ""
        for sent in _SENT.split(para):
            if len(sent) > target:
                if cur:
                    segs.append(cur)
                    cur = ""
                segs.extend(_hard_cut(sent, target))
            elif cur and len(cur) + 1 + len(sent) > target:
                segs.append(cur)
                cur = sent
            else:
                cur = f"{cur} {sent}".strip() if cur else sent
        if cur:
            segs.append(cur)
    out, cur = [], ""
    for sg in segs:
        if cur and len(cur) + 1 + len(sg) > target:
            out.append(cur)
            cur = sg
        else:
            cur = f"{cur}\n{sg}" if cur else sg
    if cur:
        out.append(cur)
    return out


# ------------------------------------------------------------------ wiersz chunk

CHUNK_KEYS = ["doc_id", "eli", "kategoria", "publisher", "year", "pos", "title", "display_address",
              "announcement_date", "status", "is_consolidated", "source_url", "ord", "article", "heading", "text"]
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def make_row(meta: dict, ord_: int, article, heading: str, text: str) -> dict:
    """Sklada wiersz chunku w kolejnosci kluczy z docs/SPEC.md (doc_id MUSI byc pierwszy - loader czyta go regexem)."""
    row = {k: meta.get(k) for k in CHUNK_KEYS[:12]}
    row["ord"] = ord_
    row["article"] = article
    row["heading"] = heading or ""
    row["text"] = text
    return row


def validate_chunk(row: dict) -> list[str]:
    """Lista bledow wiersza wzgledem docs/SPEC.md (pusta = poprawny)."""
    err = []
    if list(row.keys())[:1] != ["doc_id"]:
        err.append("doc_id musi byc pierwszym kluczem")
    for k in CHUNK_KEYS:
        if k not in row:
            err.append(f"brak pola {k}")
    if err:
        return err
    for k in ("doc_id", "eli", "kategoria", "title", "text"):
        if not isinstance(row[k], str) or not row[k].strip():
            err.append(f"{k}: pusty lub nie-string")
    if row["kategoria"] not in KATEGORIE:
        err.append(f"kategoria spoza listy: {row['kategoria']!r}")
    for k in ("year", "pos"):
        if row[k] is not None and not isinstance(row[k], int):
            err.append(f"{k}: nie int")
    if not isinstance(row["ord"], int) or isinstance(row["ord"], bool) or row["ord"] < 1:
        err.append("ord: oczekiwano int >= 1")
    if row["article"] is not None and not isinstance(row["article"], str):
        err.append("article: string lub null")
    if row["announcement_date"] is not None and not (isinstance(row["announcement_date"], str)
                                                   and _DATE.match(row["announcement_date"])):
        err.append("announcement_date: oczekiwano YYYY-MM-DD lub null")
    if not isinstance(row["is_consolidated"], bool):
        err.append("is_consolidated: oczekiwano bool")
    if not isinstance(row["heading"], str):
        err.append("heading: string")
    for k in ("title", "heading", "text", "display_address", "source_url", "status"):
        v = row.get(k)
        if isinstance(v, str) and (FFFD in v or "\x00" in v):
            err.append(f"{k}: znak zastepczy U+FFFD lub NUL")
    if isinstance(row["text"], str) and len(row["text"]) > MAX_CHUNK:
        err.append(f"text dluzszy niz {MAX_CHUNK} znakow ({len(row['text'])})")
    if isinstance(row["source_url"], str) and row["source_url"] and not row["source_url"].startswith(("http://", "https://")):
        err.append("source_url: oczekiwano http(s)")
    return err


def validate_rows(rows: list[dict]) -> list[str]:
    """Walidacja calego dokumentu: pola kazdego wiersza + spojnosc (jedno doc_id, ord 1..n rosnaco, te same metadane)."""
    errs = []
    if not rows:
        return ["brak wierszy"]
    for i, r in enumerate(rows):
        for e in validate_chunk(r):
            errs.append(f"wiersz {i + 1}: {e}")
    if len({r["doc_id"] for r in rows}) != 1:
        errs.append("rozne doc_id w jednym dokumencie")
    if [r["ord"] for r in rows] != list(range(1, len(rows) + 1)):
        errs.append("ord nie jest ciagiem 1..n")
    for k in ("eli", "kategoria", "title", "source_url", "year", "pos"):
        if len({json.dumps(r[k]) for r in rows}) != 1:
            errs.append(f"niespojne pole {k} miedzy fragmentami")
    return errs


# ------------------------------------------------------------------ zapis atomowy / JSONL / stan

def atomic_write_bytes(path: Path, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def atomic_write_json(path: Path, obj) -> None:
    atomic_write_bytes(path, (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def dumps_row(row: dict) -> str:
    return json.dumps(row, ensure_ascii=False, separators=(",", ":"))


_DOCID_RE = re.compile(rb'^\{"doc_id": ?"([^"]+)"')


def line_doc_id(raw: bytes) -> str | None:
    m = _DOCID_RE.match(raw)
    return m.group(1).decode("utf-8") if m else None


def read_doc_ids(path: Path) -> set[str]:
    """Zbior doc_id obecnych w pliku JSONL (szybkie skanowanie, bez parsowania calego JSON)."""
    ids: set[str] = set()
    p = Path(path)
    if not p.is_file():
        return ids
    with open(p, "rb") as f:
        for raw in f:
            d = line_doc_id(raw)
            if d:
                ids.add(d)
    return ids


def read_part_docs(path: Path) -> dict[str, list[dict]]:
    """Plik .part (wiersze dopisywane na biezaco): doc_id -> wiersze. Ten sam doc_id zapisany ponownie
    (nowy blok zaczynajacy sie od ord=1) zastepuje poprzedni - wygrywa ostatni."""
    docs: dict[str, list[dict]] = {}
    p = Path(path)
    if not p.is_file():
        return docs
    with open(p, "rb") as f:
        for raw in f:
            if not raw.strip():
                continue
            try:
                r = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue  # ucieta ostatnia linia po przerwaniu
            d = r.get("doc_id")
            if not d:
                continue
            if r.get("ord") == 1 or d not in docs:
                docs[d] = []
            docs[d].append(r)
    return docs


def merge_into_jsonl(out: Path, new_docs: dict[str, list[dict]]) -> None:
    """Atomowo: przepisz `out` bez dokumentow z new_docs i dopisz je na koncu (kazdy dokument ciagiem)."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=out.name + ".", suffix=".tmp", dir=str(out.parent))
    try:
        with os.fdopen(fd, "wb") as w:
            if out.is_file():
                with open(out, "rb") as f:
                    for raw in f:
                        if not raw.strip():
                            continue
                        d = line_doc_id(raw)
                        if d is not None and d in new_docs:
                            continue
                        w.write(raw if raw.endswith(b"\n") else raw + b"\n")
            for rows in new_docs.values():
                for r in rows:
                    w.write((dumps_row(r) + "\n").encode("utf-8"))
            w.flush()
            os.fsync(w.fileno())
        os.replace(tmp, out)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class PartWriter:
    """Dopisuje dokumenty do pliku <out>.part, zeby przerwany dlugi przebieg nie tracil pracy.
    flush_to(out) scala .part z plikiem docelowym (atomowo) i usuwa .part."""

    def __init__(self, out: Path):
        self.out = Path(out)
        self.part = self.out.with_name(self.out.name + ".part")
        self._f = None

    def recover(self) -> int:
        """Dokoncz scalanie po poprzednim, przerwanym przebiegu. Zwraca liczbe odzyskanych dokumentow."""
        docs = read_part_docs(self.part)
        if docs:
            merge_into_jsonl(self.out, docs)
        if self.part.exists():
            self.part.unlink()
        return len(docs)

    def add(self, rows: list[dict]) -> None:
        if self._f is None:
            self.part.parent.mkdir(parents=True, exist_ok=True)
            self._f = open(self.part, "ab")
        for r in rows:
            self._f.write((dumps_row(r) + "\n").encode("utf-8"))
        self._f.flush()

    def flush_to_out(self) -> int:
        if self._f is not None:
            self._f.close()
            self._f = None
        return self.recover()

    def discard(self) -> None:
        if self._f is not None:
            self._f.close()
            self._f = None
        if self.part.exists():
            self.part.unlink()


def state_path(source_id: str, stan_dir: Path | None = None) -> Path:
    return Path(stan_dir or DEFAULT_STAN_DIR) / f"zrodlo_{source_id}.json"


def load_state(source_id: str, stan_dir: Path | None = None) -> dict:
    p = state_path(source_id, stan_dir)
    if p.is_file():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                return d
        except (OSError, json.JSONDecodeError):
            warn(f"uszkodzony plik stanu {p} - zaczynam od zera")
    return {}


def save_state(source_id: str, state: dict, stan_dir: Path | None = None) -> None:
    atomic_write_json(state_path(source_id, stan_dir), state)


def write_changes(source_id: str, added, changed, stan_dir: Path | None = None, removed=()) -> Path:
    """stan/zmiany_<id>.json w formacie jak stan/zmiany.json (do `load_to_postgres.py --sync`)."""
    p = Path(stan_dir or DEFAULT_STAN_DIR) / f"zmiany_{source_id}.json"
    atomic_write_json(p, {"run_at": now_iso(), "added": sorted(added), "changed": sorted(changed),
                          "removed": sorted(removed)})
    return p


# ------------------------------------------------------------------ rejestr zrodel

def load_sources(path: Path | None = None) -> list[dict]:
    p = Path(path or ZRODLA_DIR / "sources.json")
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("zrodla", [])
    return data


def source_config(source_id: str, path: Path | None = None) -> dict:
    for s in load_sources(path):
        if s.get("id") == source_id:
            return s
    raise KeyError(f"brak zrodla {source_id!r} w sources.json")


# ------------------------------------------------------------------ CLI

def base_parser(description: str, source_id: str) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--limit", type=int, default=None, metavar="N",
                    help="maks. liczba dokumentow zapisanych w tym przebiegu (do testow: 5-25)")
    ap.add_argument("--since", default=None, metavar="YYYY-MM-DD",
                    help="pobierz tylko to, co nowsze/zmienione od daty (domyslnie: od ostatniego udanego przebiegu)")
    ap.add_argument("--out", default=None, metavar="PLIK",
                    help=f"plik wyjsciowy JSONL (domyslnie pipeline/out/chunks_{source_id}.jsonl)")
    ap.add_argument("--stan-dir", default=None, metavar="DIR",
                    help="katalog stanu (domyslnie stan/); do testow podaj katalog tymczasowy")
    ap.add_argument("--dry-run", action="store_true",
                    help="tylko pokaz, co zostaloby zrobione (bez zapisu plikow i stanu)")
    ap.add_argument("--force", action="store_true",
                    help="uruchom mimo enabled:false w sources.json (reczny test); w orkiestratorze niepotrzebne")
    return ap


def check_enabled(source_id: str, force: bool, dry_run: bool = False) -> bool:
    """Fetcher dziala tylko gdy zrodlo jest wlaczone w sources.json (albo --force / --dry-run)."""
    try:
        cfg = source_config(source_id)
    except (OSError, KeyError, json.JSONDecodeError) as e:
        warn(f"nie moge odczytac zrodla {source_id} z sources.json: {e}")
        return force
    if cfg.get("enabled") or force or dry_run:
        return True
    log(f"Zrodlo '{source_id}' jest uspione (enabled:false w zrodla/sources.json) - nic nie robie. "
        f"Aby wlaczyc: ustaw enabled:true (patrz zrodla/README.md) albo uruchom reczny test z --force.")
    return False


def parse_date(s: str) -> dt.date:
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        raise SystemExit(f"Zla data '{s}' - oczekiwano YYYY-MM-DD")


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def unescape(s: str) -> str:
    return htmlmod.unescape(s)
