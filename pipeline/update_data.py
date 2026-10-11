#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Przyrostowy aktualizator danych (Dz.U., M.P., teksty ujednolicone) z API ELI Sejmu.

Kontrakt: docs/UPDATE_SPEC.md, sekcja "Kontrakt pipeline/update_data.py".

    python pipeline/update_data.py [--dry-run] [--bootstrap] [--full]
        [--dane DIR] [--stan DIR] [--lata 2025,2026] [--workers N]
        [--max-akty N] [--force-removals] [--hash]

Co robi:
  * pobiera swieze metadane DU i MP (wszystkie lata, wszystkie statusy),
  * porownuje je z manifestem (stan/manifest.json) i planuje: nowe, zmienione
    (changeDate + sha256 tresci), wycofane (-> dane/_wycofane/), zmiany kategorii,
  * pobiera tylko to, co trzeba; kazdy zapis jest atomowy (plik tymczasowy + rename),
  * odswieza dane/indeks_obowiazujacych.json, indeks_mp.json, indeks_ujednolicone.json,
  * zapisuje stan/zmiany.json (wejscie dla export_chunks.py --changed i load_to_postgres.py --sync).

Kody wyjscia: 0 = ok (takze gdy brak zmian lub sa ostrzezenia), 2 = blad krytyczny,
3 = przerwano ze wzgledow bezpieczenstwa (plan wycofania > 3% aktow; uzyj --force-removals
dopiero po sprawdzeniu przyczyny), 130 = przerwane przez uzytkownika (stan zachowany, mozna wznowic).

Bezpieczenstwo danych:
  (a) blad pobrania metadanych jakiegokolwiek roku => faza wycofywania jest pomijana,
  (b) plan wycofania > 3% obowiazujacych aktow => przerwanie bez zmian (--force-removals wylacza),
  (c) wycofane pliki sa PRZENOSZONE do dane/_wycofane/<kategoria>/, nigdy kasowane,
  (d) zapisy atomowe, checkpointy manifestu + dziennik stan/biezacy_przebieg.json (wznawialnosc),
  (e) --dry-run nie zapisuje niczego poza stdout i stan/plan_dry_run.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from kategorie import kategoria as klasyfikuj  # noqa: E402  (legacy, wolno importowac)

API = "https://api.sejm.gov.pl/eli"
USER_AGENT = ("PrawoAPI-update_data/1.0 (otwarty projekt: przyrostowa aktualizacja "
              "tekstow polskiego prawa z API ELI Sejmu dla modeli AI; klient python-requests)")
MAX_WORKERS = 12
REMOVAL_LIMIT = 0.03  # 3%

ST_OBOW = "obowiązujący"
ST_TJ = "akt posiada tekst jednolity"
ST_U = (ST_OBOW, ST_TJ)

INDEKSY = {
    "obow": "indeks_obowiazujacych.json",
    "mp": "indeks_mp.json",
    "uj": "indeks_ujednolicone.json",
}
KATEGORIE_DIRS = ("ujednolicone", "jednolite", "podstawowe", "zmieniajace", "mp",
                  "orzeczenie", "umowa", "inne")
WYCOFANE = "_wycofane"
KEY_RE = re.compile(r"^(DU|MP)/(\d+)/(\d+)(#U)?$")


# --------------------------------------------------------------------------- wyjatki

class Fatal(Exception):
    """Blad krytyczny (kod wyjscia 2)."""


class Blocked(Exception):
    """Przerwanie ze wzgledow bezpieczenstwa (kod wyjscia 3)."""


class HttpError(Exception):
    """Blad HTTP/sieci po wyczerpaniu prob."""


# --------------------------------------------------------------------------- narzedzia

def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def _replace(src: Path, dst: Path) -> None:
    last = None
    for i in range(6):  # Windows: antywirus/indeksator potrafi chwilowo trzymac plik
        try:
            os.replace(src, dst)
            return
        except PermissionError as e:
            last = e
            time.sleep(0.2 * (i + 1))
    raise last  # type: ignore[misc]


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.part")
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        _replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def json_bytes(obj, indent=1) -> bytes:
    return json.dumps(obj, ensure_ascii=False, indent=indent).encode("utf-8")


def atomic_write_json(path: Path, obj, indent=1) -> None:
    atomic_write_bytes(path, json_bytes(obj, indent))


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def safe_move(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    _replace(src, dst)


def unique_path(p: Path) -> Path:
    if not p.exists():
        return p
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    for i in range(1000):
        cand = p.with_name(f"{p.stem}.{stamp}{'' if i == 0 else '-' + str(i)}{p.suffix}")
        if not cand.exists():
            return cand
    raise Fatal(f"Nie mozna znalezc wolnej nazwy dla {p}")


def parse_key(key: str):
    m = KEY_RE.match(key)
    if not m:
        raise ValueError(key)
    return m.group(1), int(m.group(2)), int(m.group(3)), bool(m.group(4))


def file_stem(key: str) -> str:
    pub, y, p, isu = parse_key(key)
    return f"U-DU_{y}_{p}" if isu else f"{pub}_{y}_{p}"


def sort_pos(key: str):
    pub, y, p, _ = parse_key(key)
    return (-y, -p)


def parse_lata(s: str | None):
    if not s:
        return None
    out = set()
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out or None


# --------------------------------------------------------------------------- klient HTTP

class Client:
    """requests + retry z backoffem + timeouty. get() -> (status, bytes) dla 200/404,
    w pozostalych przypadkach HttpError po wyczerpaniu prob."""

    RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}

    def __init__(self, workers=8, timeout=(15, 90), retries=5, backoff=1.0):
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.workers = max(workers, 1)
        self._local = threading.local()
        self._lock = threading.Lock()
        self.n_requests = 0
        self.n_retries = 0

    def _session(self):
        import requests
        from requests.adapters import HTTPAdapter
        s = getattr(self._local, "s", None)
        if s is None:
            s = requests.Session()
            s.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})
            s.mount("https://", HTTPAdapter(pool_maxsize=self.workers + 2, max_retries=0))
            self._local.s = s
        return s

    def get(self, url: str):
        import requests
        last = "?"
        for attempt in range(self.retries):
            with self._lock:
                self.n_requests += 1
                if attempt:
                    self.n_retries += 1
            wait_s = None
            try:
                r = self._session().get(url, timeout=self.timeout)
                code = r.status_code
                if code in (200, 404):
                    return code, r.content
                last = f"HTTP {code}"
                if code not in self.RETRY_STATUS:
                    raise HttpError(f"{last} dla {url}")
                ra = r.headers.get("Retry-After")
                if ra and ra.isdigit():
                    wait_s = min(int(ra), 120)
            except HttpError:
                raise
            except requests.RequestException as e:
                last = f"{type(e).__name__}"
            if attempt < self.retries - 1:
                time.sleep(wait_s if wait_s is not None
                           else min(60.0, self.backoff * (2 ** attempt)) + random.uniform(0, 0.5))
        raise HttpError(f"{last} dla {url} (po {self.retries} probach)")


def get_json(client, url: str):
    """Zwraca obiekt JSON albo None dla 404. Bledny JSON => HttpError."""
    st, body = client.get(url)
    if st == 404:
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        raise HttpError(f"niepoprawny JSON z {url}: {e}")


# --------------------------------------------------------------------------- metadane

class Meta:
    def __init__(self):
        self.targets: dict[str, dict] = {}     # klucz -> {key,pub,year,pos,item,kategoria,kind,status,changeDate}
        self.status_by_key: dict[str, str] = {}  # "DU/2024/1" -> status API (wszystkie akty)
        self.ok_years: set[tuple[str, int]] = set()
        self.failed: dict[str, str] = {}       # "DU/2024" lub "DU" -> powod
        self.latest: dict[str, dict] = {}      # pub -> {year,pos,address,date}
        self.max_year: dict[str, int] = {}     # pub -> najnowszy rok z API
        self.years_fetched: dict[str, int] = {}
        self.n_items = 0


def digest_year(pub: str, year: int, items: list):
    targets, statuses = {}, {}
    latest = None
    for it in items:
        pos = it.get("pos")
        if not isinstance(pos, int):
            raise HttpError(f"akt bez pozycji w {pub}/{year}")
        base = f"{pub}/{year}/{pos}"
        status = it.get("status", "")
        statuses[base] = status
        if latest is None or pos > latest[0]:
            latest = (pos, it.get("displayAddress") or f"{pub} {year} poz. {pos}",
                      it.get("announcementDate"))
        if pub == "DU":
            if status == ST_OBOW:
                targets[base] = dict(key=base, pub=pub, year=year, pos=pos, item=it,
                                     kategoria=klasyfikuj(it), kind="main",
                                     status=status, changeDate=it.get("changeDate"))
            if status in ST_U:
                k = base + "#U"
                targets[k] = dict(key=k, pub=pub, year=year, pos=pos, item=it,
                                  kategoria="ujednolicone", kind="U",
                                  status=status, changeDate=it.get("changeDate"))
        elif pub == "MP" and status == ST_OBOW:
            targets[base] = dict(key=base, pub=pub, year=year, pos=pos, item=it,
                                 kategoria="mp", kind="main",
                                 status=status, changeDate=it.get("changeDate"))
    return targets, statuses, latest


def fetch_year(client, pub: str, year: int):
    last = None
    for _ in range(2):  # dodatkowa proba na poziomie roku (niepelna/uszkodzona odpowiedz)
        try:
            d = get_json(client, f"{API}/acts/{pub}/{year}")
            if d is None:
                raise HttpError("404 dla roku")
            items = d.get("items")
            if not isinstance(items, list):
                raise HttpError("brak listy items")
            cnt = d.get("count")
            if isinstance(cnt, int) and cnt != len(items):
                raise HttpError(f"niepelna lista: count={cnt}, items={len(items)}")
            return digest_year(pub, year, items), len(items)
        except HttpError as e:
            last = e
            time.sleep(1.0)
    raise last  # type: ignore[misc]


def fetch_metadata(client, pubs, lata, workers) -> Meta:
    meta = Meta()
    # lista lat dla kazdego wydawcy
    years_by_pub: dict[str, list[int]] = {}
    for pub in pubs:
        try:
            d = get_json(client, f"{API}/acts/{pub}")
            ys = sorted(int(y) for y in (d or {}).get("years", []))
            if not ys:
                raise HttpError("pusta lista lat")
        except (HttpError, ValueError, TypeError) as e:
            meta.failed[pub] = f"lista lat: {e}"
            continue
        meta.max_year[pub] = ys[-1]
        if lata:
            missing = sorted(y for y in lata if y not in ys)
            for y in missing:
                log(f"  uwaga: rok {y} nie istnieje w API {pub} - pomijam")
            ys = [y for y in ys if y in lata]
        years_by_pub[pub] = ys

    tasks = [(pub, y) for pub, ys in years_by_pub.items() for y in ys]
    log(f"Pobieram metadane: {len(tasks)} par wydawca/rok ...")
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(fetch_year, client, pub, y): (pub, y) for pub, y in tasks}
        pending = set(futs)
        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for f in done:
                pub, y = futs[f]
                try:
                    (targets, statuses, latest), n = f.result()
                except Exception as e:  # noqa: BLE001
                    meta.failed[f"{pub}/{y}"] = str(e)
                    continue
                meta.targets.update(targets)
                meta.status_by_key.update(statuses)
                meta.ok_years.add((pub, y))
                meta.n_items += n
                if latest:
                    cur = meta.latest.get(pub)
                    if cur is None or (y, latest[0]) > (cur["year"], cur["pos"]):
                        meta.latest[pub] = dict(year=y, pos=latest[0], address=latest[1],
                                                date=latest[2])
    meta.years_fetched = {pub: sum(1 for (p, _) in meta.ok_years if p == pub) for pub in pubs}
    return meta


# --------------------------------------------------------------------------- manifest / dziennik

class Store:
    """Manifest + dziennik biezacego przebiegu (zapisywane atomowo, tylko poza dry-run)."""

    def __init__(self, stan: Path, dry: bool):
        self.stan = stan
        self.dry = dry
        self.manifest_path = stan / "manifest.json"
        self.journal_path = stan / "biezacy_przebieg.json"
        self.manifest: dict[str, dict] = {}
        self.ops: dict[str, str] = {}
        self.failed: dict[str, str] = {}
        self._backed_up = False
        self.started = now_iso()

    def load_manifest(self):
        if not self.manifest_path.exists():
            return None
        try:
            m = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as e:
            raise Fatal(f"Manifest {self.manifest_path} jest uszkodzony ({e}). Nie nadpisuje go. "
                        f"Przywroc stan/manifest.json.bak albo uruchom --bootstrap po usunieciu pliku.")
        if not isinstance(m, dict):
            raise Fatal(f"Manifest {self.manifest_path} ma zly format.")
        return m

    def load_journal(self):
        j = None
        try:
            j = read_json(self.journal_path)
        except (ValueError, OSError):
            log("  uwaga: dziennik przebiegu uszkodzony - ignoruje")
        if isinstance(j, dict) and isinstance(j.get("ops"), dict):
            self.ops = dict(j["ops"])
            self.started = j.get("started", self.started)
            return len(self.ops)
        return 0

    def note(self, key: str, op: str):
        self.ops[key] = merge_op(self.ops.get(key), op)

    def checkpoint(self):
        if self.dry:
            return
        self.stan.mkdir(parents=True, exist_ok=True)
        if not self._backed_up and self.manifest_path.exists():
            try:
                shutil.copy2(self.manifest_path, self.manifest_path.with_suffix(".json.bak"))
            except OSError:
                pass
            self._backed_up = True
        # dziennik pierwszy: gdyby przerwanie nastapilo miedzy zapisami, nastepny przebieg
        # najwyzej pobierze cos ponownie, ale nie zgubi zmiany z pola widzenia export_chunks.
        if self.ops:
            atomic_write_json(self.journal_path, {"started": self.started, "ops": self.ops}, indent=0)
        atomic_write_json(self.manifest_path, self.manifest, indent=0)

    def clear_journal(self):
        if self.dry:
            return
        try:
            self.journal_path.unlink()
        except FileNotFoundError:
            pass


def merge_op(prev, new):
    if prev is None or prev == new:
        return new
    if new == "removed":
        return "removed"
    if prev == "removed":
        return "changed"           # byl usuniety z bazy, wraca => usun+zaladuj
    if prev == "added" and new == "changed":
        return "added"
    return "changed"


# --------------------------------------------------------------------------- bootstrap

def scan_dane(dane: Path):
    """basename -> [rel, ...] dla plikow w dane/<kategoria>/ (bez _wycofane)."""
    found: dict[str, list[str]] = {}
    for kat in KATEGORIE_DIRS:
        d = dane / kat
        if not d.is_dir():
            continue
        with os.scandir(d) as it:
            for e in it:
                if e.is_file() and not e.name.endswith(".part"):
                    found.setdefault(e.name, []).append(f"{kat}/{e.name}")
    return found


def bootstrap_manifest(dane: Path, do_hash: bool, workers: int, old: dict | None = None):
    """Buduje manifest z istniejacych dane/ i indeksow BEZ pobierania tresci."""
    found = scan_dane(dane)
    manifest: dict[str, dict] = {}
    used: set[str] = set()
    warns = []
    spec = (("obow", "DU", False), ("mp", "MP", False), ("uj", "DU", True))
    n_idx = 0
    done_names = set()
    for name, pub, isu in spec:
        items = read_json(dane / INDEKSY[name], default=None)
        if items is None:
            warns.append(f"brak {INDEKSY[name]} - pomijam")
            continue
        n_idx += 1
        done_names.add(name)
        for a in items:
            key = f"{pub}/{a['year']}/{a['pos']}" + ("#U" if isu else "")
            kat = a.get("kategoria") or ("ujednolicone" if isu else "mp" if pub == "MP" else None)
            if kat is None:
                kat = klasyfikuj(a)
            stem = file_stem(key)
            cands = [f"{stem}.pdf"] if isu else [f"{stem}.html", f"{stem}.pdf"]
            rel = None
            for c in cands:
                locs = found.get(c, [])
                pref = [r for r in locs if r.startswith(kat + "/")]
                if pref or locs:
                    rel = (pref or locs)[0]
                    break
            e = {"status": a.get("status"), "changeDate": a.get("changeDate"),
                 "kategoria": kat, "files": [rel] if rel else [], "sha256": None}
            if rel:
                used.add(rel)
                e["size"] = (dane / rel).stat().st_size
            elif not isu and not (a.get("textHTML") or a.get("textPDF")):
                e["no_text"] = True
            manifest[key] = e
    # kandydaci na tekst U, ktorych poprzednie pobranie nie znalazlo (nie ma ich w indeksie
    # ujednoliconych): oznacz jako "sprawdzone, brak U" - inaczej pierwszy przebieg zrobilby
    # ~16 tys. zbednych zapytan o szczegoly. Zostana sprawdzone ponownie przy zmianie changeDate.
    if "uj" in done_names and "obow" in done_names:
        for key in [k for k in manifest if not k.endswith("#U") and k.startswith("DU/")]:
            uk = key + "#U"
            if uk not in manifest:
                b = manifest[key]
                manifest[uk] = {"status": b["status"], "changeDate": b["changeDate"],
                                "kategoria": "ujednolicone", "files": [], "sha256": None,
                                "no_text": True,
                                "no_text_powod": "bootstrap: brak U w indeksie ujednolicone"}
    if n_idx == 0:
        raise Fatal(f"Brak indeksow w {dane} - nie ma z czego zbudowac manifestu.")
    # zachowaj historie wycofan z poprzedniego manifestu
    if old:
        for k, e in old.items():
            if e.get("wycofany") and k not in manifest:
                manifest[k] = e
    orphans = sum(len(v) for v in found.values()) - len(used)
    if orphans:
        warns.append(f"{orphans} plikow w dane/ nie ma w zadnym indeksie (zostawiam bez zmian)")
    if do_hash:
        log(f"Liczę sha256 dla {len(used)} plikow ...")
        rels = [e["files"][0] for e in manifest.values() if e["files"] and not e.get("wycofany")]
        res = {}
        with ThreadPoolExecutor(workers) as ex:
            for r, h in zip(rels, ex.map(lambda r: sha256_file(dane / r), rels)):
                res[r] = h
        for e in manifest.values():
            if e["files"] and not e.get("wycofany") and e["files"][0] in res:
                e["sha256"] = res[e["files"][0]]
    return manifest, warns


# --------------------------------------------------------------------------- plan

def existing_files(dane: Path, entry: dict, key: str, kat: str):
    have = [f for f in entry.get("files", []) if (dane / f).is_file()]
    if have:
        return have
    stem = file_stem(key)
    exts = ("pdf",) if key.endswith("#U") else ("html", "pdf")
    return [f"{kat}/{stem}.{x}" for x in exts if (dane / kat / f"{stem}.{x}").is_file()]


def has_text_flags(t: dict) -> bool:
    return t["kind"] == "U" or bool(t["item"].get("textHTML") or t["item"].get("textPDF"))


def make_plan(manifest: dict, meta: Meta, dane: Path, full: bool):
    plan = {"add": [], "check": [], "repair": [], "move": [], "remove": [],
            "unchanged": 0, "restore": []}
    live = meta.targets
    for key, t in live.items():
        e = manifest.get(key)
        if e is None:
            plan["add"].append(key)
            continue
        if e.get("wycofany"):
            plan["add"].append(key)
            plan["restore"].append(key)
            continue
        if e.get("kategoria") != t["kategoria"] and t["kind"] == "main":
            plan["move"].append(key)
        if e.get("no_text"):
            if (full or e.get("changeDate") != t["changeDate"]) and has_text_flags(t):
                plan["add"].append(key)
            else:
                plan["unchanged"] += 1
            continue
        have = existing_files(dane, e, key, t["kategoria"])
        if not have:
            plan["repair"].append(key)
        elif full or e.get("changeDate") != t["changeDate"]:
            plan["check"].append(key)
        else:
            plan["unchanged"] += 1
    # wycofania liczymy osobno (wymagaja bezpiecznej fazy)
    for key, e in manifest.items():
        if e.get("wycofany") or key in live:
            continue
        pub, y, p, _ = parse_key(key)
        if (pub, y) not in meta.ok_years:
            continue
        base = f"{pub}/{y}/{p}"
        st = meta.status_by_key.get(base)
        reason = f"status: {st}" if st is not None else "brak w API"
        plan["remove"].append((key, reason, st or "brak w API"))
    for k in ("add", "check", "repair", "move"):
        plan[k].sort(key=sort_pos)
    plan["remove"].sort(key=lambda r: sort_pos(r[0]))
    return plan


def removal_guard(plan, meta: Meta, manifest: dict, only_years, force: bool):
    """Zwraca (plan_wycofan, ostrzezenia). Rzuca Blocked przy > 3%."""
    warns = []
    if meta.failed:
        if plan["remove"]:
            warns.append(f"POMINIETO faze wycofywania: nie udalo sie pobrac metadanych "
                         f"({len(meta.failed)} bledow: {', '.join(sorted(meta.failed)[:8])}); "
                         f"{len(plan['remove'])} aktow potencjalnie do wycofania zostaje bez zmian.")
        else:
            warns.append("Faza wycofywania pominieta (bledy pobierania metadanych).")
        plan["remove_skipped"] = plan["remove"]
        plan["remove"] = []
        return warns
    # liczymy akty z plikami (wpisy "brak tekstu" to tylko ksiegowosc i nie liczą sie do progu)
    active = sum(1 for k, e in manifest.items()
                 if not e.get("wycofany") and e.get("files")
                 and (parse_key(k)[0], parse_key(k)[1]) in meta.ok_years)
    n = sum(1 for k, _, _ in plan["remove"] if manifest[k].get("files"))
    if n and active:
        ratio = n / active
        if ratio > REMOVAL_LIMIT and not force:
            raise Blocked(
                f"Plan wycofania obejmuje {n} z {active} aktow ({ratio:.1%} > {REMOVAL_LIMIT:.0%}). "
                f"To wyglada na awarie API, nie na prawdziwe uchylenia. Nic nie zmieniono. "
                f"Sprawdz przyczyne (np. python pipeline/update_data.py --dry-run); "
                f"jesli to prawidlowe uzyj --force-removals.")
        if ratio > REMOVAL_LIMIT and force:
            warns.append(f"--force-removals: wycofuje {n} z {active} aktow ({ratio:.1%}).")
    return warns


# --------------------------------------------------------------------------- zadania pobierania

def valid_body(body: bytes, ext: str) -> bool:
    if not body:
        return False
    if ext == "pdf":
        return body[:5] == b"%PDF-"
    return True


def run_job(client, dane: Path, job: dict):
    """Wykonywane w watku. Zwraca slownik wyniku; nie dotyka manifestu."""
    key, mode, t, entry = job["key"], job["mode"], job["target"], job.get("entry") or {}
    pub, y, p, isu = parse_key(key)
    kat = t["kategoria"]
    stem = file_stem(key)
    res = {"key": key, "mode": mode}
    try:
        have_old = existing_files(dane, entry, key, kat) if entry else []
        # przyjecie pliku z przerwanego przebiegu (brak wpisu w manifescie, plik jest)
        if mode == "add" and not entry:
            canon = [f"{kat}/{stem}.{x}" for x in (("pdf",) if isu else ("html", "pdf"))]
            ex = [c for c in canon if (dane / c).is_file() and (dane / c).stat().st_size > 0]
            if ex:
                rel = ex[0]
                res.update(outcome="added", files=[rel], sha256=sha256_file(dane / rel),
                           size=(dane / rel).stat().st_size, adopted=True)
                return res

        ufile = None
        if isu:
            det = get_json(client, f"{API}/acts/DU/{y}/{p}")
            fn = None
            if det:
                for tx in det.get("texts") or []:
                    if tx.get("type") == "U" and tx.get("fileName"):
                        fn = tx["fileName"]
                        break
            if not fn:
                res.update(outcome="no_text", reason="brak tekstu U w szczegolach aktu")
                return res
            ufile = fn
            cands = [("pdf", f"{API}/acts/DU/{y}/{p}/text/U/{quote(fn)}")]
        else:
            cands = []
            for ext, flag in (("html", "textHTML"), ("pdf", "textPDF")):
                if t["item"].get(flag):
                    cands.append((ext, f"{API}/acts/{pub}/{y}/{p}/text.{ext}"))
            if not cands:
                res.update(outcome="no_text", reason="API: brak tekstu (textHTML/textPDF=false)")
                return res

        body, ext, errs = None, None, []
        for e_, url in cands:
            try:
                st, b = client.get(url)
            except HttpError as ex_:
                errs.append(str(ex_))
                continue
            if st == 404:
                continue
            if not valid_body(b, e_):
                errs.append(f"pusta lub niepoprawna odpowiedz ({e_})")
                continue
            body, ext = b, e_
            break
        if body is None:
            if errs:
                res.update(outcome="failed", error="; ".join(errs)[:300])
            else:
                res.update(outcome="no_text", reason="404 dla plikow tekstu")
            return res

        sha = sha256_bytes(body)
        rel = f"{kat}/{stem}.{ext}"
        dst = dane / rel
        if mode == "check" and have_old:
            old_sha = entry.get("sha256")
            if not old_sha:
                try:
                    old_sha = sha256_file(dane / have_old[0])
                except OSError:
                    old_sha = None
            if old_sha == sha and have_old[0] == rel:
                res.update(outcome="same", files=[rel], sha256=sha, size=len(body), ufile=ufile)
                return res
        atomic_write_bytes(dst, body)
        # stary plik pod inna nazwa/rozszerzeniem -> do _wycofane (nie kasujemy)
        for old in have_old:
            if old != rel and (dane / old).is_file():
                target = unique_path(dane / WYCOFANE / old)
                safe_move(dane / old, target)
        outcome = "added" if mode == "add" else "changed"
        res.update(outcome=outcome, files=[rel], sha256=sha, size=len(body), ufile=ufile)
        return res
    except HttpError as e:
        res.update(outcome="failed", error=str(e)[:300])
        return res
    except Exception as e:  # noqa: BLE001
        res.update(outcome="failed", error=f"{type(e).__name__}: {e}"[:300])
        return res


# --------------------------------------------------------------------------- wykonanie

def do_remove(store: Store, dane: Path, key: str, reason: str, status: str):
    e = store.manifest[key]
    had_files = bool(e.get("files"))
    new_files = []
    for rel in e.get("files", []):
        src = dane / rel
        dst_rel = f"{WYCOFANE}/{rel}"
        dst = dane / dst_rel
        if src.is_file():
            dst = unique_path(dst)
            safe_move(src, dst)
            new_files.append(dst.relative_to(dane).as_posix())
        elif dst.is_file():          # odzyskiwanie po przerwaniu: juz przeniesiony
            new_files.append(dst_rel)
    e.update(wycofany=True, wycofany_data=now_iso(), wycofany_powod=reason,
             status=status, files=new_files)
    if had_files:               # wpisy bez plikow (brak tekstu) nigdy nie trafily do bazy
        store.note(key, "removed")
    return had_files


def do_restore(store: Store, dane: Path, key: str, t: dict) -> bool:
    """Przywraca plik z _wycofane (gdy akt znow jest obowiazujacy). True jesli przywrocono."""
    e = store.manifest.get(key)
    if not e:
        return False
    new_files = []
    for rel in e.get("files", []):
        src = dane / rel
        if src.is_file():
            name = Path(rel).name
            dst = dane / t["kategoria"] / name
            if dst.exists():
                continue
            safe_move(src, dst)
            new_files.append(dst.relative_to(dane).as_posix())
    if not new_files:
        store.manifest.pop(key, None)
        return False
    for k in ("wycofany", "wycofany_data", "wycofany_powod", "no_text"):
        e.pop(k, None)
    e.update(files=new_files, kategoria=t["kategoria"])
    return True


def do_move(store: Store, dane: Path, key: str, t: dict):
    e = store.manifest[key]
    new_files = []
    for rel in e.get("files", []):
        name = Path(rel).name
        dst = dane / t["kategoria"] / name
        src = dane / rel
        if src.is_file() and src != dst:
            safe_move(src, dst)
        if dst.is_file():
            new_files.append(dst.relative_to(dane).as_posix())
        elif src.is_file():
            new_files.append(rel)
    e["files"] = new_files
    e["kategoria"] = t["kategoria"]
    store.note(key, "changed")


def apply_result(store: Store, r: dict, t: dict, counters: dict):
    key, oc = r["key"], r["outcome"]
    e = store.manifest.get(key)
    if oc == "failed":
        store.failed[key] = r.get("error", "?")
        counters["failed"] += 1
        return
    base = {"status": t["status"], "changeDate": t["changeDate"], "kategoria": t["kategoria"],
            "checked": now_iso()}
    if oc == "no_text" and e and e.get("files") and not e.get("wycofany"):
        # API nie wskazuje juz tekstu, ale mamy plik: nie tracimy referencji, odnotowujemy changeDate
        e.update(status=t["status"], changeDate=t["changeDate"], checked=now_iso())
        counters["same"] += 1
        return
    if oc == "no_text":
        ne = dict(base, files=[], sha256=None, no_text=True, no_text_powod=r.get("reason"))
        store.manifest[key] = ne
        counters["no_text"] += 1
        return
    ne = dict(base, files=r["files"], sha256=r["sha256"], size=r["size"])
    if r.get("ufile"):
        ne["ufile"] = r["ufile"]
    store.manifest[key] = ne
    if oc == "same":
        counters["same"] += 1
        return
    store.note(key, "added" if oc == "added" else "changed")
    counters["added" if oc == "added" else "changed"] += 1


def execute(store: Store, client, dane: Path, meta: Meta, plan: dict, args, interrupted):
    counters = {"added": 0, "changed": 0, "same": 0, "failed": 0, "no_text": 0,
                "removed": 0, "moved": 0}
    live = meta.targets
    # 1. wycofania
    for key, reason, st in plan["remove"]:
        if do_remove(store, dane, key, reason, st):
            counters["removed"] += 1
    # 2. zmiany kategorii
    for key in plan["move"]:
        do_move(store, dane, key, live[key])
        counters["moved"] += 1
    # 3. przywrocenia z _wycofane
    jobs = []
    restored = set()
    for key in plan["restore"]:
        if do_restore(store, dane, key, live[key]):
            restored.add(key)
    if plan["remove"] or plan["move"] or restored:
        store.checkpoint()
    # 4. pobierania: najpierw nowe, potem naprawy, potem sprawdzenia; najnowsze najpierw
    for mode, keys in (("add", plan["add"]), ("repair", plan["repair"]), ("check", plan["check"])):
        for key in keys:
            if mode == "add" and key in restored:
                jobs.append(dict(key=key, mode="check", target=live[key],
                                 entry=store.manifest.get(key), reactivated=True))
            else:
                jobs.append(dict(key=key, mode=mode, target=live[key],
                                 entry=store.manifest.get(key)))
    if args.max_akty is not None:
        jobs = jobs[:args.max_akty]
    total = len(jobs)
    if not total:
        return counters, 0
    log(f"Pobieram/weryfikuje {total} aktow (wspolbieznosc {args.workers}) ...")
    window = args.workers * 3
    it = iter(jobs)
    inflight: dict = {}
    done_n, last_ck, consec_fail = 0, time.time(), 0
    aborted = None
    ex = ThreadPoolExecutor(args.workers)
    try:
        while True:
            while len(inflight) < window and aborted is None:
                j = next(it, None)
                if j is None:
                    break
                inflight[ex.submit(run_job, client, dane, j)] = j
            if not inflight:
                break
            done, _ = wait(set(inflight), return_when=FIRST_COMPLETED)
            for f in done:
                j = inflight.pop(f)
                r = f.result()
                apply_result(store, r, j["target"], counters)
                if j.get("reactivated") and r["outcome"] in ("same", "changed"):
                    # akt wrocil po wycofaniu => dla bazy: usun+zaladuj
                    store.ops[j["key"]] = "changed"
                if r["outcome"] == "failed":
                    consec_fail += 1
                else:
                    consec_fail = 0
                done_n += 1
                if done_n % 200 == 0:
                    log(f"  {done_n}/{total} | nowe {counters['added']} zmienione {counters['changed']} "
                        f"bez zmian {counters['same']} bledy {counters['failed']}")
                if consec_fail >= 40 and aborted is None:
                    aborted = "40 kolejnych bledow pobierania (siec/API niedostepne?)"
            if time.time() - last_ck > 30 or done_n % 250 == 0:
                store.checkpoint()
                last_ck = time.time()
    except KeyboardInterrupt:
        for f in inflight:
            f.cancel()
        ex.shutdown(wait=True, cancel_futures=True)
        for f, j in list(inflight.items()):
            if f.done() and not f.cancelled():
                try:
                    apply_result(store, f.result(), j["target"], counters)
                except Exception:  # noqa: BLE001
                    pass
        store.checkpoint()
        interrupted.append(True)
        raise
    ex.shutdown(wait=True)
    store.checkpoint()
    if aborted:
        raise Fatal(aborted + ". Stan zapisany - uruchom ponownie, aby wznowic.")
    return counters, total


# --------------------------------------------------------------------------- indeksy

def idx_key(name: str, a: dict) -> str:
    pub = a.get("publisher") or ("MP" if name == "mp" else "DU")
    return f"{pub}/{a['year']}/{a['pos']}" + ("#U" if name == "uj" else "")


def index_name(key: str) -> str:
    pub, _, _, isu = parse_key(key)
    return "uj" if isu else ("mp" if pub == "MP" else "obow")


def build_indexes(manifest: dict, live: dict, old: dict):
    out = {n: [] for n in INDEKSY}
    warns = []
    oldmap = {n: {idx_key(n, a): a for a in old.get(n) or []} for n in INDEKSY}
    for key, e in manifest.items():
        if e.get("wycofany"):
            continue
        n = index_name(key)
        if n == "uj" and not e.get("files"):
            continue
        t = live.get(key)
        item = dict(t["item"]) if t else dict(oldmap[n].get(key) or {})
        if not item:
            warns.append(f"brak metadanych dla {key} - pominieto w indeksie")
            continue
        item["kategoria"] = e["kategoria"]
        out[n].append(item)
    for n in out:
        out[n].sort(key=lambda a: (a["year"], -a["pos"]))
    return out, warns


def write_indexes(dane: Path, new: dict, old: dict) -> list[str]:
    written = []
    for n, fname in INDEKSY.items():
        if old.get(n) is not None and old[n] == new[n]:
            continue
        atomic_write_json(dane / fname, new[n], indent=1)
        written.append(fname)
    return written


def load_old_indexes(dane: Path):
    old = {}
    for n, fname in INDEKSY.items():
        try:
            old[n] = read_json(dane / fname)
        except (ValueError, OSError):
            old[n] = None
    return old


# --------------------------------------------------------------------------- glowna logika

def acquire_lock(stan: Path):
    stan.mkdir(parents=True, exist_ok=True)
    lock = stan / "update.lock"
    if lock.exists() and time.time() - lock.stat().st_mtime > 3 * 3600:
        lock.unlink()  # przeterminowana (przerwany proces)
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise Fatal(f"Inna aktualizacja trwa albo zostala przerwana awaryjnie. Jesli na pewno nie "
                    f"dziala, usun plik {lock} i uruchom ponownie.")
    os.write(fd, f"{os.getpid()} {now_iso()}\n".encode())
    os.close(fd)
    return lock


def clean_part_files(dane: Path):
    n = 0
    if dane.is_dir():
        for sub in dane.iterdir():
            if sub.is_dir():
                for p in sub.glob("*.part"):
                    try:
                        p.unlink()
                        n += 1
                    except OSError:
                        pass
    return n


def summarize_plan(plan, meta: Meta, manifest: dict) -> dict:
    return {
        "dodac": len(plan["add"]),
        "do_sprawdzenia_changeDate": len(plan["check"]),
        "do_naprawy_brak_pliku": len(plan["repair"]),
        "zmiana_kategorii": len(plan["move"]),
        "do_wycofania": sum(1 for k, _, _ in plan["remove"] if manifest[k].get("files")),
        "wycofanie_wpisow_bez_plikow": sum(1 for k, _, _ in plan["remove"] if not manifest[k].get("files")),
        "bez_zmian": plan["unchanged"],
    }


def run(args, client=None) -> int:
    dane = Path(args.dane).resolve()
    stan = Path(args.stan).resolve()
    dry = args.dry_run
    args.workers = max(1, min(int(args.workers), MAX_WORKERS))
    lata = parse_lata(args.lata)
    client = client or Client(workers=args.workers)
    t0 = time.time()

    if not dane.is_dir() and not dry:
        dane.mkdir(parents=True, exist_ok=True)
    lock = None
    if not dry:
        lock = acquire_lock(stan)
    interrupted: list = []
    try:
        return _run(args, client, dane, stan, dry, lata, t0, interrupted)
    finally:
        if lock is not None:
            try:
                lock.unlink()
            except OSError:
                pass


def _run(args, client, dane, stan, dry, lata, t0, interrupted) -> int:
    store = Store(stan, dry)
    warnings: list[str] = []
    if not dry:
        n = clean_part_files(dane)
        if n:
            log(f"Usunieto {n} resztek plikow tymczasowych (*.part) po przerwanym przebiegu.")

    manifest = store.load_manifest()
    old_for_hist = manifest
    # ---- bootstrap (jawny)
    if args.bootstrap:
        log("Bootstrap: buduje manifest z istniejacych dane/ i indeksow (bez pobierania tresci) ...")
        m, w = bootstrap_manifest(dane, args.hash, args.workers, old_for_hist)
        for x in w:
            log(f"  uwaga: {x}")
        act = sum(1 for e in m.values() if not e.get("wycofany"))
        nf = sum(1 for e in m.values() if e.get("files"))
        log(f"Bootstrap: {act} aktywnych wpisow, {nf} z plikami "
            f"({sum(1 for e in m.values() if e.get('no_text'))} wpisow bez pliku: brak tekstu w API lub brak wariantu U).")
        if dry:
            log("--dry-run: manifest nie zostal zapisany.")
            return 0
        store.manifest = m
        store.checkpoint()
        atomic_write_json(stan / "zmiany.json", {
            "run_at": now_iso(), "added": [], "changed": [], "removed": [], "unchanged": act,
            "latest": {}, "bootstrap": True}, indent=2)
        log(f"Zapisano {store.manifest_path}")
        return 0

    # ---- brak manifestu => niejawny bootstrap, jesli sa indeksy
    if manifest is None:
        if any((dane / f).exists() for f in INDEKSY.values()):
            log("Brak stan/manifest.json, ale sa indeksy w dane/ - wykonuje bootstrap (bez pobierania).")
            manifest, w = bootstrap_manifest(dane, args.hash, args.workers)
            for x in w:
                log(f"  uwaga: {x}")
        else:
            log("Brak manifestu i indeksow - zaczynam od pustego stanu (pelne pobranie).")
            manifest = {}
        store.manifest = manifest
        if not dry:
            store.checkpoint()
    else:
        store.manifest = manifest

    prev = store.load_journal()
    if prev:
        log(f"Wznawiam po przerwanym przebiegu ({prev} zmian z poprzedniego przebiegu zachowane).")

    # ---- metadane
    meta = fetch_metadata(client, ("DU", "MP"), lata, args.workers)
    if not meta.ok_years and meta.failed:
        raise Fatal("Nie udalo sie pobrac metadanych z API ELI: " + "; ".join(
            f"{k}: {v}" for k, v in list(meta.failed.items())[:5]))
    # rok z manifestu, ktorego API w ogole nie zwraca na liscie lat (bez --lata) => niepewne
    if not lata:
        for key, e in store.manifest.items():
            if e.get("wycofany"):
                continue
            pub, y, _, _ = parse_key(key)
            if (pub, y) not in meta.ok_years and f"{pub}/{y}" not in meta.failed \
                    and pub not in meta.failed:
                meta.failed[f"{pub}/{y}"] = "rok z manifestu nieobecny na liscie lat API"
    # pusty rok, w ktorym manifest ma aktywne akty => podejrzane (API zwraca 200 dla pustych lat)
    active_by_year: dict[tuple, int] = {}
    for key, e in store.manifest.items():
        if not e.get("wycofany"):
            pub, y, _, _ = parse_key(key)
            active_by_year[(pub, y)] = active_by_year.get((pub, y), 0) + 1
    seen_by_year: dict[tuple, int] = {}
    for base in meta.status_by_key:
        pub, y, _ = base.split("/")
        seen_by_year[(pub, int(y))] = seen_by_year.get((pub, int(y)), 0) + 1
    for (pub, y) in list(meta.ok_years):
        if active_by_year.get((pub, y)) and not seen_by_year.get((pub, y)):
            meta.ok_years.discard((pub, y))
            meta.failed[f"{pub}/{y}"] = "API zwrocilo pusta liste dla roku, w ktorym mamy akty"

    for k, v in sorted(meta.failed.items()):
        warnings.append(f"Metadane {k}: nie pobrano ({v})")
    log(f"Metadane: {meta.n_items} aktow, docelowych {len(meta.targets)}, bledow lat: {len(meta.failed)}")

    # ---- plan
    plan = make_plan(store.manifest, meta, dane, args.full)
    warnings += removal_guard(plan, meta, store.manifest, lata, args.force_removals)
    summ = summarize_plan(plan, meta, store.manifest)
    log("Plan: " + ", ".join(f"{k}={v}" for k, v in summ.items()))

    if dry:
        _print_plan(plan, lambda k: store.manifest[k].get("files"))
        out = {"run_at": now_iso(), "dry_run": True, "podsumowanie": summ,
               "dodac": plan["add"], "do_sprawdzenia": plan["check"], "naprawa": plan["repair"],
               "zmiana_kategorii": plan["move"],
               "do_wycofania": [{"klucz": k, "powod": r} for k, r, _ in plan["remove"]
                                if store.manifest[k].get("files")],
               "ostrzezenia": warnings,
               "latest": {p: v["address"] for p, v in meta.latest.items()}}
        stan.mkdir(parents=True, exist_ok=True)
        atomic_write_json(stan / "plan_dry_run.json", out, indent=1)
        for w in warnings:
            log(f"UWAGA: {w}")
        log(f"--dry-run: zapisano tylko {stan / 'plan_dry_run.json'}")
        return 0

    # ---- wykonanie
    old_idx = load_old_indexes(dane)
    try:
        counters, total = execute(store, client, dane, meta, plan, args, interrupted)
    except KeyboardInterrupt:
        log("Przerwano (Ctrl+C). Stan zapisany - uruchom ponownie, aby wznowic.")
        return 130
    except Fatal:
        # indeksy odswiez tak czy tak (manifest jest spojny), potem blad
        _finish_indexes(store, dane, meta, old_idx)
        raise

    # zaktualizuj status/changeDate dla wpisow aktywnych bez zmian tresci (metadane)
    for key, t in meta.targets.items():
        e = store.manifest.get(key)
        if e and not e.get("wycofany") and key not in store.failed:
            e["status"] = t["status"]
    idx_written, idx_warn = _finish_indexes(store, dane, meta, old_idx)
    warnings += idx_warn

    ops = store.ops
    added = sorted(k for k, o in ops.items() if o == "added")
    changed = sorted(k for k, o in ops.items() if o == "changed")
    removed = sorted(k for k, o in ops.items() if o == "removed")
    # uwaga: wpisy bez plikow (no_text) nie maja czego eksportowac - nie ma ich w ops
    deferred = max(0, (len(plan["add"]) + len(plan["repair"]) + len(plan["check"])) - total)
    n_unchanged = plan["unchanged"] + counters["same"]
    zm = {
        "run_at": now_iso(), "added": added, "changed": changed, "removed": removed,
        "unchanged": n_unchanged,
        "latest": {p: v["address"] for p, v in meta.latest.items() if v["year"] == meta.max_year.get(p)},
        "latest_date": {p: v["date"] for p, v in meta.latest.items() if v["year"] == meta.max_year.get(p)},
        "moved": sorted(plan["move"]),
        "failed": [{"klucz": k, "blad": v} for k, v in sorted(store.failed.items())],
        "odlozone": deferred,
        "partial": bool(store.failed or meta.failed or deferred or (lata is not None)),
        "warnings": warnings, "dry_run": False, "indeksy_zapisane": idx_written,
        "czas_s": round(time.time() - t0, 1),
    }
    stan.mkdir(parents=True, exist_ok=True)
    store.checkpoint()                       # manifest (i dziennik) najpierw
    atomic_write_json(stan / "zmiany.json", zm, indent=2)
    store.clear_journal()   # zmiany.json zapisany = dziennik skonsumowany
    _print_final(zm, counters)
    nreq = getattr(client, "n_requests", None)
    if nreq is not None:
        log(f"Zapytan HTTP: {nreq}, ponowien: {getattr(client, 'n_retries', 0)}")
    if total >= 5 and counters["failed"] == total:
        raise Fatal("Wszystkie proby pobrania zakonczyly sie bledem.")
    return 0


def _finish_indexes(store: Store, dane: Path, meta: Meta, old_idx: dict):
    new_idx, warns = build_indexes(store.manifest, meta.targets, old_idx)
    written = write_indexes(dane, new_idx, old_idx)
    return written, warns


def _print_plan(plan, files_of):
    def show(title, keys, n=12):
        if keys:
            log(f"  {title} ({len(keys)}): " + ", ".join(keys[:n]) + (" ..." if len(keys) > n else ""))
    show("do dodania", plan["add"])
    show("do sprawdzenia (changeDate)", plan["check"])
    show("do naprawy (brak pliku)", plan["repair"])
    show("zmiana kategorii", plan["move"])
    rem = [x for x in plan["remove"] if files_of(x[0])]
    if rem:
        log(f"  do wycofania ({len(rem)}): " + ", ".join(f"{k} [{r}]" for k, r, _ in rem[:8])
            + (" ..." if len(rem) > 8 else ""))


def _print_final(zm, c):
    log("=== PODSUMOWANIE ===")
    log(f"Nowe: {len(zm['added'])}, zmienione: {len(zm['changed'])}, wycofane: {len(zm['removed'])}, "
        f"bez zmian: {zm['unchanged']}, bledy: {len(zm['failed'])}, odlozone: {zm['odlozone']}")
    if zm["latest"]:
        log("Najnowsze: " + "; ".join(f"{p}: {a}" for p, a in zm["latest"].items()))
    for w in zm["warnings"]:
        log(f"UWAGA: {w}")
    for f in zm["failed"][:10]:
        log(f"BLAD: {f['klucz']}: {f['blad']}")


# --------------------------------------------------------------------------- CLI

def build_parser():
    ap = argparse.ArgumentParser(
        description="Przyrostowa aktualizacja danych (Dz.U., M.P., teksty ujednolicone) z API ELI Sejmu.")
    ap.add_argument("--dry-run", action="store_true", help="tylko plan; zapis wylacznie stan/plan_dry_run.json")
    ap.add_argument("--bootstrap", action="store_true",
                    help="zbuduj manifest z istniejacych dane/ i indeksow bez pobierania tresci")
    ap.add_argument("--full", action="store_true", help="pobierz i zweryfikuj wszystko od nowa (sha256)")
    ap.add_argument("--dane", default=str(ROOT / "dane"))
    ap.add_argument("--stan", default=str(ROOT / "stan"))
    ap.add_argument("--lata", default=None, help="np. 2025,2026 albo 2020-2026")
    ap.add_argument("--workers", type=int, default=8, help=f"wspolbieznosc (max {MAX_WORKERS})")
    ap.add_argument("--max-akty", type=int, default=None, help="limit pobran w tym przebiegu (testy)")
    ap.add_argument("--force-removals", action="store_true",
                    help="pozwol na wycofanie > 3%% aktow (po recznym sprawdzeniu przyczyny)")
    ap.add_argument("--hash", action="store_true",
                    help="bootstrap: policz sha256 wszystkich plikow (domyslnie leniwie przy zmianie)")
    return ap


def main(argv=None, client=None) -> int:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            try:
                s.reconfigure(encoding="utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                pass
    args = build_parser().parse_args(argv)
    try:
        return run(args, client)
    except Blocked as e:
        log(f"PRZERWANO (bezpieczenstwo danych): {e}")
        return 3
    except Fatal as e:
        log(f"BLAD KRYTYCZNY: {e}")
        return 2
    except KeyboardInterrupt:
        log("Przerwano.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
