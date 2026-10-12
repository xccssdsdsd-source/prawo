#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""aktualizuj.py - orkiestrator "Uaktualnij to wszystko".

Jedna komenda odswieza przyrostowo: dane (Dz.U., M.P., teksty ujednolicone), zrodla dodatkowe,
fragmenty (chunks), data-info + strone, baze Postgres, a na koncu (zgodnie z konfiguracja)
robi commit, push i wdrozenie. Na koncu daje raport po polsku.

Kroki (w kolejnosci): kopia -> dane -> zrodla -> eksport -> info -> testy -> baza -> commit -> wdrozenie

Uzycie:
    python aktualizuj.py --dry-run          # NAJPIERW: pokazuje plan, niczego nie zmienia
    python aktualizuj.py                    # wlasciwa aktualizacja
    python aktualizuj.py --tylko baza       # jeden krok
    python aktualizuj.py --pierwszy-raz     # tylko zbuduj manifest z istniejacych danych (bez pobierania)

Zasady:
  * Python uruchamiany jest przez sys.executable - nie trzeba aktywowac zadnego srodowiska wirtualnego.
  * Sekrety (DATABASE_URL, API_KEY) sa czytane ze zmiennych srodowiskowych i z .env.local,
    NIGDY nie sa wypisywane (wyjscie podprocesow jest filtrowane).
  * commit / push / wdrozenie / zaladowanie bazy tylko wg .claude/uaktualnij.config.json
    albo za jawna zgoda w tym uruchomieniu (--zgoda push wdrozenie ...).
  * Przerwany przebieg mozna po prostu uruchomic ponownie (kolejka zmian w stan/kolejka.json
    pamieta, co jeszcze nie trafilo do eksportu i bazy).

Kody wyjscia: 0 ok (takze z ostrzezeniami), 1 blad kroku, 2 blad uzycia/konfiguracji,
3 zabezpieczenie danych (update_data odmowil masowego wycofania aktow), 130 przerwano (Ctrl+C).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent

KROKI = ["kopia", "dane", "zrodla", "eksport", "info", "testy", "baza", "commit", "wdrozenie"]
OPISY = {
    "kopia": "kopia zapasowa malych plikow stanu i indeksow",
    "dane": "przyrostowa aktualizacja danych (Dz.U., M.P., teksty ujednolicone)",
    "zrodla": "zrodla dodatkowe wlaczone w zrodla/sources.json",
    "eksport": "eksport zmienionych aktow do fragmentow (chunks)",
    "info": "data-info.json i fallbacki stron (data stanu danych)",
    "testy": "testy strony/API (tsc + vitest)",
    "baza": "synchronizacja bazy Postgres",
    "commit": "commit (i ewentualnie push) zmian strony",
    "wdrozenie": "wdrozenie na Vercel",
}
KRYTYCZNE = {"kopia", "dane", "eksport", "info", "testy", "baza"}

OK, OSTRZ, POMIN, BLAD, ZABL, PRZER, PLAN, NIEWYK = (
    "ok", "ostrzezenie", "pominiety", "blad", "zablokowany", "przerwany", "plan", "niewykonany")
STATUS_PL = {OK: "OK", OSTRZ: "OK (ostrzeżenia)", POMIN: "pominięty", BLAD: "BŁĄD", ZABL: "ZABLOKOWANY",
             PRZER: "PRZERWANY", PLAN: "plan", NIEWYK: "niewykonany"}

DEFAULT_CONFIG = {
    "auto_load_db": True,
    "auto_commit": True,
    "auto_push": False,
    "auto_deploy": False,
    "backup_before_update": True,
    "baza_max_mb": 450,          # None = bez limitu (plan platny); 450 = darmowy Neon (~0,5 GB)
    "kopie_zachowaj": 5,
    "commit_trailer": "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>",
}
BOOL_KEYS = ("auto_load_db", "auto_commit", "auto_push", "auto_deploy", "backup_before_update")
STRONA_PLIKI = ["vercel/public/data-info.json", "vercel/public/index.html", "vercel/public/podlacz.html"]
INDEKSY = ["indeks_obowiazujacych.json", "indeks_mp.json", "indeks_ujednolicone.json"]
OPS = ("added", "changed", "removed")
MAX_KOPIA_PLIK = 50 * 1024 * 1024


# ---------------------------------------------------------------------------------- narzedzia

def teraz() -> dt.datetime:
    return dt.datetime.now().astimezone()


def parse_iso(s):
    if not isinstance(s, str) or not s:
        return None
    try:
        d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.astimezone()
    return d


def fmt_data(iso) -> str:
    """2026-10-11 (lub pelny ISO) -> 11.10.2026."""
    if not iso:
        return "brak danych"
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(iso))
    return f"{m.group(3)}.{m.group(2)}.{m.group(1)}" if m else str(iso)


def czytaj_json(path: Path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def zapisz_json(path: Path, obj, indent=2) -> None:
    """Zapis atomowy: plik tymczasowy obok, potem rename."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def sha_pliku(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blok in iter(lambda: f.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()


def hash_zestawu(root: Path, pliki) -> str:
    h = hashlib.sha256()
    for p in sorted(pliki):
        p = Path(p)
        if p.is_file():
            h.update(p.relative_to(root).as_posix().encode())
            h.update(sha_pliku(p).encode())
    return h.hexdigest()


def pliki_strony(root: Path):
    pub = root / "vercel" / "public"
    return [p for p in pub.rglob("*") if p.is_file()] if pub.is_dir() else []


def mb(n) -> str:
    return f"{n / 1048576:.1f} MB"


def wczytaj_env_local(path: Path) -> dict:
    """KEY=VALUE z .env.local (bez wypisywania). Ignoruje komentarze i puste linie."""
    out = {}
    try:
        tekst = Path(path).read_text(encoding="utf-8-sig")
    except OSError:
        return out
    for linia in tekst.splitlines():
        linia = linia.strip()
        if not linia or linia.startswith("#") or "=" not in linia:
            continue
        if linia.lower().startswith("export "):
            linia = linia[7:].lstrip()
        k, v = linia.split("=", 1)
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        if k:
            out[k] = v
    return out


def _url_z_haslem(v) -> bool:
    try:
        return bool(urlsplit(str(v)).password)
    except ValueError:
        return False


def zbierz_sekrety(env_local: dict) -> set:
    """Wartosci, ktore nie moga trafic do logow/raportow."""
    # Sekret = zmienna o nazwie z KEY/PASS/TOKEN/SECRET/PWD, znana nazwa (DATABASE_URL...) albo URL z haslem
    # (user:haslo@host). Publiczne zmienne (NEXT_PUBLIC_*, PUBLIC_*, VITE_*) i zwykle URL-e (np.
    # NEXT_PUBLIC_SITE_URL, adres wdrozenia) nie sa zamazywane w logach i raportach.
    wzor = re.compile(r"(KEY|PASS|TOKEN|SECRET|PWD)", re.I)
    znane = {"DATABASE_URL", "POSTGRES_URL", "API_KEY", "VERCEL_TOKEN"}
    publiczne = ("NEXT_PUBLIC_", "PUBLIC_", "VITE_")
    zrodla = {}
    for k, v in env_local.items():
        if k in znane or _url_z_haslem(v) or (wzor.search(k) and not k.upper().startswith(publiczne)):
            zrodla[k] = v
    for k in ("DATABASE_URL", "API_KEY", "POSTGRES_URL", "VERCEL_TOKEN"):
        if os.environ.get(k):
            zrodla[k] = os.environ[k]
    sekrety = set()
    for v in zrodla.values():
        if not v:
            continue
        sekrety.add(v)
        try:
            u = urlsplit(v)
            if u.password:
                sekrety.add(u.password)
        except ValueError:
            pass
    return {s for s in sekrety if len(s) >= 6}


_URL_CRED = re.compile(r"([A-Za-z][A-Za-z0-9+.\-]*://[^:/\s@]+):[^@\s]+@")


def redaguj(tekst: str, sekrety) -> str:
    for s in sorted(sekrety, key=len, reverse=True):
        tekst = tekst.replace(s, "***")
    return _URL_CRED.sub(r"\1:***@", tekst)


def wczytaj_config(path: Path):
    """(config, ostrzezenia). Brak pliku = domyslne. Wartosci auto_* inne niz bool -> False (bezpiecznie)."""
    cfg = dict(DEFAULT_CONFIG)
    ostrz = []
    if not Path(path).exists():
        ostrz.append(f"Brak {Path(path).name} - uzywam ustawien domyslnych (bez push i wdrozenia).")
        return cfg, ostrz
    dane = czytaj_json(path)
    if not isinstance(dane, dict):
        ostrz.append(f"{Path(path).name}: niepoprawny JSON - uzywam ustawien domyslnych (bez push i wdrozenia).")
        return cfg, ostrz
    for k, v in dane.items():
        if k.startswith("_") or k not in DEFAULT_CONFIG:
            continue
        if k in BOOL_KEYS and not isinstance(v, bool):
            ostrz.append(f"{k}: oczekiwano true/false, jest {v!r} - traktuje jako false.")
            cfg[k] = False
        else:
            cfg[k] = v
    return cfg, ostrz


# ---------------------------------------------------------------------------------- kolejka zmian

def scal_operacje(poprzednie: dict, nowe: dict) -> dict:
    """doc_id -> operacja ('added'/'changed'/'removed'). Zasady laczenia kolejnych przebiegow:
    added+changed=added, added+removed=removed (bezpiecznie: usun z bazy, jesli jest),
    removed+added/changed=changed (podmiana), reszta: nowsza operacja wygrywa."""
    wynik = dict(poprzednie)
    for doc, op in nowe.items():
        stara = wynik.get(doc)
        if stara is None:
            wynik[doc] = op
        elif stara == "added" and op == "changed":
            wynik[doc] = "added"
        elif stara == "removed" and op in ("added", "changed"):
            wynik[doc] = "changed"
        elif stara == "changed" and op == "added":
            wynik[doc] = "changed"
        else:
            wynik[doc] = op
    return wynik


def lista_do_ops(zm: dict) -> dict:
    ops = {}
    for op in OPS:
        for doc in (zm.get(op) or []):
            ops[str(doc)] = op
    return ops


def ops_do_listy(ops: dict) -> dict:
    return {op: sorted(d for d, o in ops.items() if o == op) for op in OPS}


def czy_mp_du(doc_id: str) -> bool:
    return bool(re.match(r"^(DU|MP)/\d+/\d+", doc_id))


# ---------------------------------------------------------------------------------- kontekst

@dataclass
class Krok:
    nazwa: str
    status: str = NIEWYK
    opis: str = ""
    czas: float = 0.0
    ostrzezenia: list = field(default_factory=list)
    dane: dict = field(default_factory=dict)
    ogon: str = ""


class Przerwanie(Exception):
    pass


class Ctx:
    """Stan jednego uruchomienia. `run` mozna podmienic w testach (atrapa podprocesow)."""

    def __init__(self, root: Path, args, cfg: dict, run=None, env_local: dict | None = None):
        self.root = Path(root)
        self.args = args
        self.cfg = cfg
        self.dane = self.root / "dane"
        self.stan = self.root / "stan"
        self.out = self.root / "pipeline" / "out"
        self.vercel = self.root / "vercel"
        self.pub = self.vercel / "public"
        self.dry = bool(args.dry_run)
        self.start = teraz()
        self.t0 = time.time()
        self.kroki: list[Krok] = []
        self.ostrzezenia: list[str] = []
        self.linie_logu: list[str] = []
        self.stan_run: dict = {}          # wspolne dane miedzy krokami
        self.env_local = env_local if env_local is not None else wczytaj_env_local(self.root / ".env.local")
        self.sekrety = zbierz_sekrety(self.env_local)
        self.run = run or self._run_proc
        self.glosno = True
        self.zatrzymano_na: str | None = None
        self.argv: list = []

    # -- wyjscie
    def log(self, msg: str = "") -> None:
        msg = redaguj(str(msg), self.sekrety)
        self.linie_logu.append(msg)
        if self.glosno:
            try:
                print(msg, flush=True)
            except UnicodeEncodeError:
                print(msg.encode("ascii", "replace").decode("ascii"), flush=True)

    def ostrzez(self, msg: str) -> None:
        msg = redaguj(msg, self.sekrety)
        if msg not in self.ostrzezenia:
            self.ostrzezenia.append(msg)

    # -- konfiguracja i zgody
    def zgoda(self, co: str) -> bool:
        """Czy wolno wykonac krok zewnetrzny: wg configu albo jawna zgoda z linii polecen."""
        klucz = {"baza": "auto_load_db", "commit": "auto_commit", "push": "auto_push",
                 "wdrozenie": "auto_deploy"}[co]
        return bool(self.cfg.get(klucz)) or co in (self.args.zgoda or [])

    def database_url(self):
        return os.environ.get("DATABASE_URL") or self.env_local.get("DATABASE_URL") or None

    # -- podprocesy
    def python(self, skrypt: str, *arg) -> list:
        return [sys.executable, str(self.root / skrypt), *arg]

    def _run_proc(self, cmd, cwd=None, env=None, timeout=None, glosno=True):
        """Uruchamia podproces, strumieniuje wyjscie (z redakcja sekretow). Zwraca (kod, tekst)."""
        e = dict(os.environ)
        e["PYTHONUTF8"] = "1"
        e["PYTHONIOENCODING"] = "utf-8"
        url = self.database_url()
        if url and "DATABASE_URL" not in e:
            e["DATABASE_URL"] = url
        if env:
            e.update(env)
        self.log(f"  $ {' '.join(redaguj(str(c), self.sekrety) for c in cmd)}")
        linie = []
        try:
            proc = subprocess.Popen(cmd, cwd=str(cwd or self.root), env=e, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        except OSError as ex:
            return 127, f"Nie mozna uruchomic polecenia: {ex}"
        t_end = time.time() + timeout if timeout else None
        try:
            for surowa in iter(proc.stdout.readline, b""):
                linia = redaguj(surowa.decode("utf-8", "replace").rstrip("\r\n"), self.sekrety)
                linie.append(linia)
                if glosno and self.glosno:
                    self.log("    | " + linia)
                else:
                    self.linie_logu.append("    | " + linia)
                if t_end and time.time() > t_end:
                    proc.kill()
                    linie.append(f"[przekroczono limit czasu {timeout} s]")
                    break
            proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
            raise
        return proc.returncode, "\n".join(linie)

    # -- kolejka zmian
    @property
    def kolejka_path(self) -> Path:
        return self.stan / "kolejka.json"

    def wczytaj_kolejke(self) -> dict:
        k = czytaj_json(self.kolejka_path)
        if not isinstance(k, dict):
            k = {}
        for sekcja in ("eksport", "baza"):
            sk = k.get(sekcja)
            if not isinstance(sk, dict):
                sk = {}
            k[sekcja] = {op: list(sk.get(op) or []) for op in OPS}
        if not isinstance(k.get("ingested"), dict):
            k["ingested"] = {}
        return k

    def zapisz_kolejke(self, k: dict) -> None:
        if not self.dry:
            zapisz_json(self.kolejka_path, k)


def ops_z_sekcji(sekcja: dict) -> dict:
    return lista_do_ops(sekcja)


def wlacz_do_kolejki(ctx: Ctx, nazwa_pliku: str, tylko_baza: bool) -> dict:
    """Wczytuje stan/<nazwa_pliku> do kolejki (idempotentnie, wg run_at). Zwraca licznik nowo dodanych."""
    zm = czytaj_json(ctx.stan / nazwa_pliku)
    wynik = {"added": 0, "changed": 0, "removed": 0, "nowe": False}
    if not isinstance(zm, dict):
        return wynik
    run_at = zm.get("run_at")
    k = ctx.wczytaj_kolejke()
    if not run_at or k["ingested"].get(nazwa_pliku) == run_at:
        return wynik
    nowe = lista_do_ops(zm)
    sekcje = ["baza"] if tylko_baza else ["eksport", "baza"]
    for sek in sekcje:
        ops = scal_operacje(ops_z_sekcji(k[sek]), {d: o for d, o in nowe.items()
                                                   if sek == "baza" or czy_mp_du(d)})
        k[sek] = ops_do_listy(ops)
    k["ingested"][nazwa_pliku] = run_at
    ctx.zapisz_kolejke(k)
    for op in OPS:
        wynik[op] = len(zm.get(op) or [])
    wynik["nowe"] = True
    return wynik


def wlacz_wszystkie_zmiany(ctx: Ctx) -> None:
    """zmiany.json (DU/MP) + zmiany_<id>.json wlaczonych zrodel -> kolejka."""
    if ctx.dry:
        return
    wlacz_do_kolejki(ctx, "zmiany.json", tylko_baza=False)
    for s in zrodla_wlaczone(ctx):
        wlacz_do_kolejki(ctx, f"zmiany_{s['id']}.json", tylko_baza=True)


def zrodla_wlaczone(ctx: Ctx):
    reg = czytaj_json(ctx.root / "zrodla" / "sources.json")
    if isinstance(reg, dict):
        reg = reg.get("zrodla", [])
    if not isinstance(reg, list):
        return []
    return [s for s in reg if isinstance(s, dict) and s.get("enabled") is True and s.get("skrypt")]


def ile_w_sekcji(sekcja: dict) -> int:
    return sum(len(sekcja.get(op) or []) for op in OPS)


# ---------------------------------------------------------------------------------- kroki

def krok_kopia(ctx: Ctx, k: Krok) -> None:
    if not ctx.cfg.get("backup_before_update"):
        k.status, k.opis = POMIN, "wyłączona w konfiguracji (backup_before_update=false)"
        return
    pliki = []
    for p in sorted(ctx.dane.glob("indeks_*.json")) + sorted(ctx.stan.glob("*.json")):
        pliki.append(p)
    for p in (ctx.out / "raport.txt", ctx.pub / "data-info.json"):
        if p.is_file():
            pliki.append(p)
    male, duze = [], []
    for p in pliki:
        (male if p.stat().st_size <= MAX_KOPIA_PLIK else duze).append(p)
    for p in duze:
        k.ostrzezenia.append(f"Pominięto w kopii duży plik {p.name} ({mb(p.stat().st_size)}).")
    rozmiar = sum(p.stat().st_size for p in male)
    if not male:
        k.status, k.opis = POMIN, "brak plików do skopiowania (pierwsze uruchomienie?)"
        return
    nazwa = ctx.start.strftime("%Y-%m-%d_%H%M%S")
    cel = ctx.stan / "kopie" / nazwa
    if ctx.dry:
        k.status = PLAN
        k.opis = f"utworzyłbym kopię {len(male)} plików ({mb(rozmiar)}) w {cel.relative_to(ctx.root).as_posix()}/"
        return
    for p in male:
        rel = p.relative_to(ctx.root)
        d = cel / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, d)
    ctx.stan_run["kopia"] = cel
    # retencja: zostaw N najnowszych kopii (tylko katalogi o nazwie z daty, utworzone przez ten skrypt)
    zachowaj = max(1, int(ctx.cfg.get("kopie_zachowaj") or 5))
    wszystkie = sorted(d for d in (ctx.stan / "kopie").iterdir()
                       if d.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{6}", d.name))
    for stara in wszystkie[:-zachowaj]:
        shutil.rmtree(stara, ignore_errors=True)
    k.status = OK
    k.opis = f"{len(male)} plików ({mb(rozmiar)}) -> {cel.relative_to(ctx.root).as_posix()}/"


def _plan_opis(plan: dict) -> str:
    p = plan.get("podsumowanie") or {}
    czesci = [f"{v} {etyk}" for kl, etyk in (
        ("dodac", "do dodania"), ("do_sprawdzenia_changeDate", "do sprawdzenia (zmiana daty)"),
        ("do_naprawy_brak_pliku", "do naprawy"), ("zmiana_kategorii", "zmiana kategorii"),
        ("do_wycofania", "do wycofania")) if (v := p.get(kl))]
    bz = p.get("bez_zmian")
    opis = ", ".join(czesci) if czesci else "brak zmian do wprowadzenia"
    if bz is not None:
        opis += f"; bez zmian: {bz}"
    return opis


def krok_dane(ctx: Ctx, k: Krok) -> None:
    py = ctx.root / "pipeline" / "update_data.py"
    if not py.is_file():
        k.status, k.opis = BLAD, "brak pipeline/update_data.py"
        return
    manifest = ctx.stan / "manifest.json"
    ma_indeksy = any((ctx.dane / n).exists() for n in INDEKSY)
    pierwszy = ctx.args.pierwszy_raz or not manifest.exists()
    baza_args = ["--dane", str(ctx.dane), "--stan", str(ctx.stan)]

    if pierwszy:
        if not ma_indeksy:
            k.status = BLAD
            k.opis = ("brak manifestu i brak indeksów w dane/ - to byłoby pełne pobranie wszystkiego. "
                      "Uruchom je świadomie ręcznie: python pipeline/update_data.py --full "
                      "(lub najpierw pobierz_prawo.py / pobierz_wiecej.py).")
            return
        if ctx.dry:
            # pusty, tymczasowy stan/: update_data --dry-run zrobi bootstrap w pamieci i pokaże plan
            # NASTEPNEGO przebiegu (nic nie zapisuje w dane/ ani w prawdziwym stan/)
            tmp = Path(tempfile.mkdtemp(prefix="prawo_dryrun_"))
            try:
                cmd = ctx.python("pipeline/update_data.py", "--dry-run", "--dane", str(ctx.dane), "--stan", str(tmp))
                if ctx.args.lata:
                    cmd += ["--lata", ctx.args.lata]
                rc, out = ctx.run(cmd)
                plan = czytaj_json(tmp / "plan_dry_run.json") or {}
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
            k.ogon = out[-3000:]
            if rc != 0:
                k.status, k.opis = (ZABL if rc == 3 else BLAD), f"update_data --dry-run zakończył się kodem {rc}"
                return
            ctx.stan_run["pierwszy_raz"] = True
            ctx.stan_run["plan"] = plan
            for w in plan.get("ostrzezenia") or []:
                k.ostrzezenia.append(str(w))
            k.status = PLAN
            k.opis = ("PIERWSZE URUCHOMIENIE: zbudowałbym manifest z istniejących danych (bez pobierania treści); "
                      "plan następnego przebiegu: " + _plan_opis(plan))
            return
        cmd = ctx.python("pipeline/update_data.py", "--bootstrap", *baza_args)
        rc, out = ctx.run(cmd)
        k.ogon = out[-3000:]
        if rc != 0:
            k.status, k.opis = BLAD, f"update_data --bootstrap zakończył się kodem {rc}"
            return
        ctx.stan_run["pierwszy_raz"] = True
        k.status = OK
        k.opis = ("PIERWSZE URUCHOMIENIE: zbudowano manifest z istniejących danych (bez pobierania). "
                  "Uruchom aktualizację ponownie, aby pobrać nowości.")
        return

    if ctx.dry:
        tmp = Path(tempfile.mkdtemp(prefix="prawo_dryrun_"))
        try:
            shutil.copy2(manifest, tmp / "manifest.json")      # prawdziwy stan/ zostaje nietknięty
            cmd = ctx.python("pipeline/update_data.py", "--dry-run", "--dane", str(ctx.dane), "--stan", str(tmp))
            if ctx.args.lata:
                cmd += ["--lata", ctx.args.lata]
            rc, out = ctx.run(cmd)
            k.ogon = out[-3000:]
            if rc != 0:
                k.status, k.opis = (ZABL if rc == 3 else BLAD), f"update_data --dry-run zakończył się kodem {rc}"
                return
            plan = czytaj_json(tmp / "plan_dry_run.json") or {}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        ctx.stan_run["plan"] = plan
        for w in plan.get("ostrzezenia") or []:
            k.ostrzezenia.append(str(w))
        k.status = PLAN
        k.opis = "plan: " + _plan_opis(plan)
        k.dane = {"latest": plan.get("latest") or {}}
        return

    cmd = ctx.python("pipeline/update_data.py", *baza_args)
    if ctx.args.lata:
        cmd += ["--lata", ctx.args.lata]
    if ctx.args.max_akty:
        cmd += ["--max-akty", str(ctx.args.max_akty)]
    if ctx.args.force_removals:
        cmd.append("--force-removals")
    start = ctx.start
    rc, out = ctx.run(cmd)
    k.ogon = out[-3000:]
    if rc == 3:
        k.status = ZABL
        k.opis = ("update_data odmówił masowego wycofania aktów (> 3%) - NIC nie zmieniono w danych. "
                  "Sprawdź przyczynę (awaria API?). Jeśli wycofania są zasadne: python aktualizuj.py --force-removals")
        return
    if rc == 130:
        k.status, k.opis = PRZER, "przerwano (Ctrl+C) - stan zapisany, uruchom ponownie, aby wznowić"
        return
    if rc != 0:
        k.status = BLAD
        k.opis = f"update_data zakończył się kodem {rc} (po poprawie przyczyny uruchom ponownie - przebieg jest wznawialny)"
        return

    zm = czytaj_json(ctx.stan / "zmiany.json")
    swieze = isinstance(zm, dict) and (parse_iso(zm.get("run_at")) or start) >= start.replace(microsecond=0)
    if not isinstance(zm, dict) or not swieze:
        k.status = OSTRZ
        k.opis = "update_data zakończył się poprawnie, ale nie zapisał świeżego stan/zmiany.json - liczby zmian nieznane"
        return
    ile = {op: len(zm.get(op) or []) for op in OPS}
    ctx.stan_run["zmiany"] = zm
    wlacz_do_kolejki(ctx, "zmiany.json", tylko_baza=False)
    for w in zm.get("warnings") or []:
        k.ostrzezenia.append(str(w))
    for f in (zm.get("failed") or [])[:10]:
        k.ostrzezenia.append(f"Nie pobrano {f.get('klucz')}: {f.get('blad')}")
    if zm.get("odlozone"):
        k.ostrzezenia.append(f"Odłożone na kolejny przebieg: {zm['odlozone']} aktów.")
    # data_as_of w build_data_info = data zapisu indeksow; potwierdzamy swiezosc, gdy przebieg byl pelny i bez bledow
    if not zm.get("partial") and not zm.get("bootstrap"):
        for n in INDEKSY:
            p = ctx.dane / n
            if p.exists():
                os.utime(p, None)
        ctx.stan_run["zweryfikowano"] = True
    k.status = OSTRZ if k.ostrzezenia else OK
    k.opis = (f"nowych {ile['added']}, zmienionych {ile['changed']}, wycofanych {ile['removed']}, "
              f"bez zmian {zm.get('unchanged', '?')}")
    if zm.get("partial"):
        k.opis += " (przebieg częściowy - data stanu nie została potwierdzona)"
    k.dane = {"ile": ile, "latest": zm.get("latest") or {}}


def krok_zrodla(ctx: Ctx, k: Krok) -> None:
    if ctx.args.bez_zrodel:
        k.status, k.opis = POMIN, "wyłączone flagą --bez-zrodel"
        return
    wl = zrodla_wlaczone(ctx)
    if not wl:
        k.status, k.opis = POMIN, "żadne źródło dodatkowe nie jest włączone (zrodla/sources.json: enabled=false)"
        return
    czesci = []
    for s in wl:
        sid = s["id"]
        skrypt = (ctx.root / str(s["skrypt"])).resolve()
        if ctx.root.resolve() not in skrypt.parents or not skrypt.is_file():
            k.ostrzezenia.append(f"Źródło {sid}: nie znaleziono skryptu {s['skrypt']} - pominięte.")
            continue
        cmd = [sys.executable, str(skrypt)]
        if ctx.dry:
            cmd.append("--dry-run")
        rc, out = ctx.run(cmd)
        k.ogon = out[-2000:]
        if rc == 0:
            czesci.append(f"{sid}: ok")
        elif rc == 3:
            k.ostrzezenia.append(f"Źródło {sid}: usługa niedostępna (kod 3) - zostanie dokończone przy kolejnym uruchomieniu.")
            czesci.append(f"{sid}: niedostępne")
        else:
            k.ostrzezenia.append(f"Źródło {sid}: zakończone kodem {rc} (część danych mogła się nie pobrać).")
            czesci.append(f"{sid}: kod {rc}")
        if not ctx.dry:
            w = wlacz_do_kolejki(ctx, f"zmiany_{sid}.json", tylko_baza=True)
            if w["nowe"]:
                czesci[-1] += f" (+{w['added']} ~{w['changed']} -{w['removed']})"
    k.status = PLAN if ctx.dry else (OSTRZ if k.ostrzezenia else OK)
    k.opis = "; ".join(czesci) or "brak"


def krok_eksport(ctx: Ctx, k: Krok) -> None:
    wlacz_wszystkie_zmiany(ctx)
    kol = ctx.wczytaj_kolejke()
    n = ile_w_sekcji(kol["eksport"])
    if ctx.dry:
        plan = ctx.stan_run.get("plan") or {}
        p = plan.get("podsumowanie") or {}
        szac = (p.get("dodac") or 0) + (p.get("do_sprawdzenia_changeDate") or 0) + (p.get("do_naprawy_brak_pliku") or 0)
        k.status = PLAN
        k.opis = (f"w kolejce już {n} dokumentów; z planu: do 'dodac/sprawdzenia' ok. {szac} (górna granica), "
                  f"wycofań {p.get('do_wycofania', 0)}")
        return
    if n == 0:
        k.status, k.opis = POMIN, "brak zmian do wyeksportowania (kolejka pusta)"
        return
    chunks = ctx.out / "chunks.jsonl"
    if not chunks.exists():
        k.status = BLAD
        k.opis = ("brak pipeline/out/chunks.jsonl - tryb przyrostowy potrzebuje pełnego eksportu "
                  "(python pipeline/export_chunks.py, ok. 9 min)")
        return
    plik = ctx.stan / "zmiany_do_eksportu.json"
    zapisz_json(plik, {"run_at": teraz().isoformat(timespec="seconds"), **kol["eksport"]})
    cmd = ctx.python("pipeline/export_chunks.py", "--changed", str(plik), "--dane", str(ctx.dane),
                     "--out", str(chunks))
    rc, out = ctx.run(cmd)
    k.ogon = out[-3000:]
    if rc != 0:
        k.status = BLAD
        k.opis = f"export_chunks --changed zakończył się kodem {rc} (kolejka zachowana - ponów po poprawie)"
        return
    kol = ctx.wczytaj_kolejke()
    kol["eksport"] = {op: [] for op in OPS}
    ctx.zapisz_kolejke(kol)
    ost = [l.strip() for l in out.splitlines() if "OSTRZEZ" in l.upper()]
    for l in ost[:10]:
        k.ostrzezenia.append(l.lstrip("! ").strip())
    if len(ost) > 10:
        k.ostrzezenia.append(f"... i {len(ost) - 10} kolejnych ostrzeżeń eksportu (pełny log: stan/).")
    k.status = OSTRZ if k.ostrzezenia else OK
    k.opis = f"wyeksportowano zmiany dla {n} dokumentów"
    ctx.stan_run["wyeksportowano"] = n


def krok_info(ctx: Ctx, k: Krok) -> None:
    py = ctx.root / "pipeline" / "build_data_info.py"
    if not py.is_file():
        k.status, k.opis = BLAD, "brak pipeline/build_data_info.py"
        return
    przed = hash_zestawu(ctx.root, [ctx.root / p for p in STRONA_PLIKI])
    cmd = ctx.python("pipeline/build_data_info.py", "--dane", str(ctx.dane), "--stan", str(ctx.stan))
    if ctx.dry:
        cmd.append("--dry-run")
    rc, out = ctx.run(cmd)
    k.ogon = out[-2000:]
    if rc != 0:
        k.status, k.opis = BLAD, f"build_data_info zakończył się kodem {rc}"
        return
    for l in out.splitlines():
        if l.upper().startswith("OSTRZE"):
            k.ostrzezenia.append(l.strip())
    po = hash_zestawu(ctx.root, [ctx.root / p for p in STRONA_PLIKI])
    ctx.stan_run["strona_zmieniona"] = przed != po
    info = czytaj_json(ctx.pub / "data-info.json") or {}
    ctx.stan_run["info"] = info
    k.status = PLAN if ctx.dry else (OSTRZ if k.ostrzezenia else OK)
    pierwsza = next((l for l in out.splitlines() if l.startswith("Stan danych")), "")
    if ctx.dry:
        zmieniloby = [l.split(":", 1)[1].strip() for l in out.splitlines() if "zmieniłby się:" in l]
        k.opis = (("zmieniłyby się pliki: " + ", ".join(zmieniloby)) if zmieniloby else "pliki strony bez zmian") + \
                 (f"; {pierwsza}" if pierwsza else "")
    else:
        k.opis = (pierwsza or f"data_as_of = {info.get('data_as_of')}") + \
                 ("; pliki strony zaktualizowane" if przed != po else "; pliki strony bez zmian")


def krok_testy(ctx: Ctx, k: Krok) -> None:
    if ctx.args.bez_testow:
        k.status, k.opis = POMIN, "wyłączone flagą --bez-testow"
        return
    if ctx.dry:
        k.status, k.opis = PLAN, "uruchomiłbym: npm run typecheck, npm test (w vercel/)"
        return
    if not (ctx.vercel / "node_modules").is_dir():
        k.status = OSTRZ
        k.opis = "brak vercel/node_modules - testy pominięte (zainstaluj: cd vercel; npm install)"
        k.ostrzezenia.append("Testy strony/API nie zostały uruchomione (brak zależności npm).")
        return
    npm = shutil.which("npm")
    if not npm:
        k.status, k.opis = OSTRZ, "brak polecenia npm w PATH - testy pominięte"
        k.ostrzezenia.append("Testy strony/API nie zostały uruchomione (brak npm).")
        return
    rc, out = ctx.run([npm, "run", "typecheck"], cwd=ctx.vercel, timeout=900)
    if rc != 0:
        k.status, k.opis, k.ogon = BLAD, f"tsc (typecheck) zakończył się kodem {rc}", out[-3000:]
        return
    rc, out = ctx.run([npm, "test"], cwd=ctx.vercel, timeout=900)
    k.ogon = out[-3000:]
    if rc != 0:
        k.status, k.opis = BLAD, f"vitest zakończył się kodem {rc}"
        return
    m = re.search(r"Tests\s+(\d+) passed", out)
    k.status = OK
    k.opis = "tsc czysto" + (f", vitest: {m.group(1)} testów zielonych" if m else ", vitest zielony")


def dolacz_pominiete_limitem(ctx: Ctx) -> list:
    """Dokumenty odrzucone wczesniej przez limit rozmiaru bazy (stan/pominiete_limit.json, zapisuje je
    load_to_postgres) wracaja do kolejki bazy jako 'added' - pozniejsze operacje z kolejki maja pierwszenstwo
    (np. wycofanie). Dzieki temu baza nie rozjezdza sie po cichu z korpusem."""
    dane = czytaj_json(ctx.stan / "pominiete_limit.json")
    ids = [str(d) for d in (dane.get("doc_ids") if isinstance(dane, dict) else None) or []]
    if not ids or ctx.dry:
        return ids
    kol = ctx.wczytaj_kolejke()
    ops = scal_operacje({d: "added" for d in ids}, ops_z_sekcji(kol["baza"]))
    kol["baza"] = ops_do_listy(ops)
    ctx.zapisz_kolejke(kol)
    return ids


def krok_baza(ctx: Ctx, k: Krok) -> None:
    if ctx.args.bez_bazy:
        k.status, k.opis = POMIN, "wyłączone flagą --bez-bazy"
        ctx.stan_run["baza_pominieta"] = "flaga --bez-bazy"
        return
    wlacz_wszystkie_zmiany(ctx)
    pominiete = dolacz_pominiete_limitem(ctx)
    kol = ctx.wczytaj_kolejke()
    n = ile_w_sekcji(kol["baza"])
    if ctx.dry:
        plan = (ctx.stan_run.get("plan") or {}).get("podsumowanie") or {}
        k.status = PLAN
        k.opis = (f"w kolejce do bazy {n} dokumentów + zmiany z planu danych; "
                  f"DATABASE_URL {'jest' if ctx.database_url() else 'BRAK (krok zostałby pominięty)'}; "
                  f"zgoda na zapis do bazy: {'tak' if ctx.zgoda('baza') else 'NIE (auto_load_db=false)'}")
        return
    if n == 0 and ile_w_sekcji(kol["eksport"]) == 0:
        k.status, k.opis = POMIN, "brak zmian do załadowania (kolejka pusta)"
        return
    if ile_w_sekcji(kol["eksport"]) > 0:
        k.status, k.opis = POMIN, "eksport nie został dokończony - najpierw eksport"
        k.ostrzezenia.append("Baza nie została zsynchronizowana: najpierw dokończ krok eksport.")
        ctx.stan_run["baza_pominieta"] = "eksport niedokończony"
        return
    if not ctx.zgoda("baza"):
        k.status = POMIN
        k.opis = "brak zgody (auto_load_db=false). Zaakceptuj i uruchom: python aktualizuj.py --tylko baza --zgoda baza"
        k.ostrzezenia.append("Baza nie została zsynchronizowana (brak zgody w konfiguracji).")
        ctx.stan_run["baza_pominieta"] = "brak zgody"
        return
    if not ctx.database_url():
        k.status = POMIN
        k.opis = "brak DATABASE_URL (zmienna środowiskowa lub .env.local) - krok pominięty"
        k.ostrzezenia.append("Baza nie została zsynchronizowana: brak DATABASE_URL (patrz .env.example).")
        ctx.stan_run["baza_pominieta"] = "brak DATABASE_URL"
        return
    plik = ctx.stan / "zmiany_do_bazy.json"
    zapisz_json(plik, {"run_at": teraz().isoformat(timespec="seconds"), **kol["baza"]})
    wejscia = [ctx.out / "chunks.jsonl"]
    for s in zrodla_wlaczone(ctx):
        w = s.get("wyjscie")
        if w and (ctx.root / w).is_file():
            wejscia.append(ctx.root / w)
    cmd = ctx.python("pipeline/load_to_postgres.py", "--sync", str(plik),
                     "--input", *[str(p) for p in wejscia])
    if ctx.cfg.get("baza_max_mb"):
        cmd += ["--max-mb", str(ctx.cfg["baza_max_mb"])]
    rc, out = ctx.run(cmd)
    k.ogon = out[-3000:]
    if rc == 2:
        k.status = POMIN
        k.opis = "loader zgłosił brak DATABASE_URL - krok pominięty"
        k.ostrzezenia.append("Baza nie została zsynchronizowana: brak DATABASE_URL.")
        ctx.stan_run["baza_pominieta"] = "brak DATABASE_URL"
        return
    if rc != 0:
        k.status = BLAD
        k.opis = (f"load_to_postgres --sync zakończył się kodem {rc}; transakcja cofnięta, baza bez zmian "
                  "(kolejka zachowana - ponów po poprawie)")
        return
    kol = ctx.wczytaj_kolejke()
    kol["baza"] = {op: [] for op in OPS}
    ctx.zapisz_kolejke(kol)
    syn = next((l for l in out.splitlines() if l.startswith("Sync gotowy")), "")
    stan_b = next((l for l in out.splitlines() if l.startswith("Baza teraz")), "")
    if "przez limit" in syn:
        m = re.search(r"pominieto przez limit (\d+)", syn)
        if m and int(m.group(1)) > 0:
            k.ostrzezenia.append(f"{m.group(1)} nowych dokumentów NIE trafiło do bazy z powodu limitu rozmiaru "
                                 f"(baza_max_mb={ctx.cfg.get('baza_max_mb')}); lista w stan/pominiete_limit.json - "
                                 f"wrócą przy kolejnej synchronizacji, gdy zwolni się miejsce (albo podnieś baza_max_mb).")
    k.status = OSTRZ if k.ostrzezenia else OK
    k.opis = (syn + (" " + stan_b if stan_b else "")).strip() or f"załadowano zmiany dla {n} dokumentów"
    ctx.stan_run["baza_ok"] = True


def baza_zgodna(ctx: Ctx) -> bool:
    kol = ctx.wczytaj_kolejke()
    return ile_w_sekcji(kol["baza"]) == 0 and ile_w_sekcji(kol["eksport"]) == 0


def git_zmienione(ctx: Ctx, sciezki) -> set:
    """Sciezki (wzgledem korzenia repo) z niezatwierdzonymi zmianami; pusty zbior, gdy brak git."""
    git = shutil.which("git")
    if not git or not (ctx.root / ".git").exists():
        return set()
    rc, out = ctx.run([git, "status", "--porcelain", "--", *sciezki], glosno=False)
    if rc != 0:
        return set()
    return {l[3:].strip() for l in out.splitlines() if l.strip()}


def krok_commit(ctx: Ctx, k: Krok) -> None:
    git = shutil.which("git")
    if not git or not (ctx.root / ".git").exists():
        k.status, k.opis = POMIN, "to nie jest repozytorium git (lub brak git w PATH)"
        return
    sciezki = [p for p in STRONA_PLIKI if (ctx.root / p).exists()]
    brudne = ctx.stan_run.get("brudne_na_starcie") or set()
    for p in sorted(brudne & set(sciezki)):
        k.ostrzezenia.append(f"{p} miał Twoje niezatwierdzone zmiany jeszcze przed aktualizacją - nie dodaję go do commita.")
    sciezki = [p for p in sciezki if p not in brudne]
    if not sciezki:
        k.status, k.opis = POMIN, "wszystkie pliki strony miały niezatwierdzone zmiany przed aktualizacją - commit pominięty"
        return
    rc, out = ctx.run([git, "status", "--porcelain", "--", *sciezki], glosno=False)
    if rc != 0:
        k.status, k.opis = OSTRZ, f"git status zakończył się kodem {rc}"
        k.ostrzezenia.append("Nie udało się sprawdzić stanu git.")
        return
    zmienione = [l[3:].strip() for l in out.splitlines() if l.strip()]
    if ctx.dry:
        k.status = PLAN
        k.opis = (f"do zatwierdzenia byłoby {len(zmienione)} plików strony" if zmienione
                  else "brak zmian w plikach strony do zatwierdzenia") + \
                 f"; commit: {'tak' if ctx.zgoda('commit') else 'nie'}, push: {'tak' if ctx.zgoda('push') and not ctx.args.bez_wdrozenia else 'nie'}"
        return
    if not zmienione:
        k.status, k.opis = POMIN, "brak zmian w plikach strony do zatwierdzenia"
        _push_jesli_wolno(ctx, k, git)
        return
    if not ctx.zgoda("commit"):
        k.status = POMIN
        k.opis = ("brak zgody (auto_commit=false). Ręcznie: git add " + " ".join(sciezki) +
                  " && git commit -m \"Aktualizacja danych\"")
        return
    info = ctx.stan_run.get("info") or czytaj_json(ctx.pub / "data-info.json") or {}
    zm = ctx.stan_run.get("zmiany") or {}
    tytul = f"Aktualizacja danych: stan na {fmt_data(info.get('data_as_of'))}"
    tresc = []
    if (info.get("dz_u") or {}).get("latest_act"):
        tresc.append(f"Najnowszy Dz.U.: {info['dz_u']['latest_act']}; najnowszy M.P.: {(info.get('m_p') or {}).get('latest_act')}")
    if zm:
        tresc.append(f"Akty: nowych {len(zm.get('added') or [])}, zmienionych {len(zm.get('changed') or [])}, "
                     f"wycofanych {len(zm.get('removed') or [])}.")
    tresc.append("Wygenerowane przez aktualizuj.py (data-info.json, fallbacki stron).")
    wiad = tytul + "\n\n" + "\n".join(tresc)
    if ctx.cfg.get("commit_trailer"):
        wiad += "\n\n" + str(ctx.cfg["commit_trailer"])
    rc, out = ctx.run([git, "add", "--", *sciezki], glosno=False)
    if rc == 0:
        rc, out = ctx.run([git, "commit", "-m", wiad, "--", *sciezki], glosno=False)
    k.ogon = out[-1500:]
    if rc != 0:
        k.status, k.opis = OSTRZ, f"git commit nie powiódł się (kod {rc}) - patrz log"
        k.ostrzezenia.append("Commit nie został utworzony (np. brak user.name/user.email w git).")
        return
    k.status = OK
    k.opis = f"utworzono commit: {tytul}"
    ctx.stan_run["commit_utworzony"] = True
    _push_jesli_wolno(ctx, k, git)


def _push_jesli_wolno(ctx: Ctx, k: Krok, git: str) -> None:
    if ctx.args.bez_wdrozenia:
        return
    if not ctx.zgoda("push"):
        k.opis += "; push: pominięty (auto_push=false) - wypchnij ręcznie po sprawdzeniu: git push"
        return
    if not baza_zgodna(ctx):
        k.opis += "; push: pominięty (baza nie jest zsynchronizowana z danymi)"
        k.ostrzezenia.append("Push wstrzymany: baza nie zawiera jeszcze wszystkich zmian.")
        return
    rc, out = ctx.run([git, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], glosno=False)
    if rc != 0:
        k.opis += "; push: pominięty (brak skonfigurowanego zdalnego repozytorium/upstream)"
        k.ostrzezenia.append("Push pominięty: brak upstream (git remote / git push -u origin main).")
        return
    # zwykly `git push` wypycha WSZYSTKIE niewypchniete commity galezi, nie tylko aktualizacje:
    # pokaz je w raporcie, zeby wlasciciel widzial, co faktycznie wyszlo
    rc, wychodzace = ctx.run([git, "log", "@{u}..HEAD", "--oneline"], glosno=False)
    lista = [w.strip() for w in wychodzace.splitlines() if w.strip()] if rc == 0 else []
    rc, out = ctx.run([git, "push"], timeout=300)
    if rc != 0:
        k.opis += f"; push NIE powiódł się (kod {rc})"
        k.ostrzezenia.append("Push nie powiódł się - wypchnij ręcznie.")
        k.ogon = out[-1000:]
    else:
        k.opis += "; push wykonany"
        if lista:
            k.opis += f" ({len(lista)} commit(ów) wyszło razem: " + "; ".join(lista[:5]) + (" ..." if len(lista) > 5 else "") + ")"
            if len(lista) > 1:
                k.ostrzezenia.append(f"Push wypchnął {len(lista)} commity, nie tylko commit aktualizacji (zob. opis kroku).")
        if k.status == POMIN:
            k.status = OK
        ctx.stan_run["push_ok"] = True


def krok_wdrozenie(ctx: Ctx, k: Krok) -> None:
    if ctx.args.bez_wdrozenia:
        k.status, k.opis = POMIN, "wyłączone flagą --bez-wdrozenia"
        return
    hash_teraz = hash_zestawu(ctx.root, pliki_strony(ctx.root))
    ostatnie = czytaj_json(ctx.stan / "ostatnie_wdrozenie.json") or {}
    if ostatnie.get("hash") == hash_teraz:
        k.status, k.opis = POMIN, "treść strony bez zmian od ostatniego wdrożenia"
        return
    if not baza_zgodna(ctx) and not ctx.dry:
        k.status = POMIN
        k.opis = "wstrzymane: baza nie jest zsynchronizowana z danymi (strona podałaby datę stanu, której baza nie ma)"
        k.ostrzezenia.append("Wdrożenie wstrzymane: najpierw zsynchronizuj bazę.")
        return
    polecenie = "cd vercel && vercel --prod"
    if ctx.dry:
        k.status = PLAN
        k.opis = f"strona zmieniła się od ostatniego wdrożenia; wdrożenie: {'tak' if ctx.zgoda('wdrozenie') else 'nie (auto_deploy=false)'}"
        return
    if not ctx.zgoda("wdrozenie"):
        k.status = POMIN
        k.opis = f"brak zgody (auto_deploy=false). Po sprawdzeniu: python aktualizuj.py --tylko wdrozenie --zgoda wdrozenie  (lub: {polecenie})"
        return
    vercel = shutil.which("vercel")
    if not vercel:
        k.status = OSTRZ
        k.opis = f"brak polecenia vercel w PATH (npm i -g vercel; vercel login). Ręcznie: {polecenie}"
        k.ostrzezenia.append("Wdrożenie nie zostało wykonane (brak Vercel CLI).")
        return
    rc, out = ctx.run([vercel, "--prod", "--yes"], cwd=ctx.vercel, timeout=900)
    k.ogon = out[-1500:]
    if rc != 0:
        k.status, k.opis = OSTRZ, f"vercel --prod zakończył się kodem {rc}"
        k.ostrzezenia.append("Wdrożenie nie powiodło się.")
        return
    adresy = re.findall(r"https://[A-Za-z0-9.\-]+\.vercel\.app", out)
    zapisz_json(ctx.stan / "ostatnie_wdrozenie.json",
                {"at": teraz().isoformat(timespec="seconds"), "hash": hash_teraz,
                 "url": adresy[-1] if adresy else None})
    k.status = OK
    k.opis = "wdrożono na Vercel" + (f" ({adresy[-1]})" if adresy else "")
    ctx.stan_run["wdrozono"] = True


FUNKCJE = {"kopia": krok_kopia, "dane": krok_dane, "zrodla": krok_zrodla, "eksport": krok_eksport,
           "info": krok_info, "testy": krok_testy, "baza": krok_baza, "commit": krok_commit,
           "wdrozenie": krok_wdrozenie}


# ---------------------------------------------------------------------------------- raport

def wynik_ogolny(ctx: Ctx) -> str:
    if ctx.zatrzymano_na:
        k = next(x for x in ctx.kroki if x.nazwa == ctx.zatrzymano_na)
        if k.status == ZABL:
            return f"ZABLOKOWANO przez zabezpieczenie na kroku „{k.nazwa}” (dane nietknięte)"
        if k.status == PRZER:
            return f"PRZERWANO na kroku „{k.nazwa}” (można wznowić)"
        return f"BŁĄD na kroku „{k.nazwa}” - dalsze kroki wstrzymane"
    if ctx.stan_run.get("pierwszy_raz"):
        if ctx.dry:
            return "PLAN pierwszego uruchomienia (najpierw powstanie manifest, bez pobierania)"
        return "PIERWSZE URUCHOMIENIE zakończone (zbudowano manifest, nic nie pobrano)"
    if ctx.ostrzezenia or any(x.status == OSTRZ for x in ctx.kroki):
        return "OK, z ostrzeżeniami"
    return "OK"


def kod_wyjscia(ctx: Ctx) -> int:
    if ctx.zatrzymano_na:
        k = next(x for x in ctx.kroki if x.nazwa == ctx.zatrzymano_na)
        return {ZABL: 3, PRZER: 130}.get(k.status, 1)
    return 0


def dane_podsumowania(ctx: Ctx) -> dict:
    info = ctx.stan_run.get("info") or czytaj_json(ctx.pub / "data-info.json") or {}
    zm = ctx.stan_run.get("zmiany") or {}
    plan = ctx.stan_run.get("plan") or {}
    latest = dict(zm.get("latest") or plan.get("latest") or {})
    if not latest.get("DU") and (info.get("dz_u") or {}).get("latest_act"):
        latest["DU"] = info["dz_u"]["latest_act"]
    if not latest.get("MP") and (info.get("m_p") or {}).get("latest_act"):
        latest["MP"] = info["m_p"]["latest_act"]
    return {"info": info, "zm": zm, "latest": latest}


def co_pominieto(ctx: Ctx):
    return [(k.nazwa, k.opis) for k in ctx.kroki if k.status in (POMIN, NIEWYK)]


def co_dalej(ctx: Ctx):
    d = []
    if ctx.stan_run.get("pierwszy_raz") and not ctx.dry:
        d.append("Uruchom ponownie `python aktualizuj.py --dry-run`, a po zobaczeniu planu `python aktualizuj.py` "
                 "(pierwszy właściwy przebieg sprawdzi ok. 1,8 tys. kandydatów na tekst ujednolicony - akty ze statusem "
                 "'akt posiada tekst jednolity'; większość nie ma wariantu U, więc realnie przybędzie tylko "
                 "kilkanaście plików. Liczbę kandydatów pokaże plan).")
    if ctx.zatrzymano_na:
        k = next(x for x in ctx.kroki if x.nazwa == ctx.zatrzymano_na)
        if k.status == ZABL:
            d.append("Sprawdź, dlaczego tak wiele aktów zniknęło z API. Jeśli wycofania są zasadne: "
                     "`python aktualizuj.py --force-removals`.")
        else:
            d.append("Usuń przyczynę błędu (patrz sekcja Błędy w raporcie) i uruchom `python aktualizuj.py` ponownie - "
                     "przebieg jest wznawialny, nic nie trzeba cofać.")
    for k in ctx.kroki:
        if k.nazwa == "commit" and "push: pominięty (auto_push=false)" in k.opis:
            d.append("Sprawdź zmiany (`git log -1 --stat`) i wypchnij: `git push`.")
        if k.nazwa == "wdrozenie" and k.status == POMIN and "auto_deploy=false" in k.opis:
            d.append("Wdróż stronę: `python aktualizuj.py --tylko wdrozenie --zgoda wdrozenie` (albo `cd vercel; vercel --prod`).")
        if k.nazwa == "baza" and k.status == POMIN and ctx.stan_run.get("baza_pominieta") in ("brak DATABASE_URL",):
            d.append("Ustaw `DATABASE_URL` w pliku `.env.local` (wzór: `.env.example`) i uruchom `python aktualizuj.py --tylko baza`.")
        if k.nazwa == "baza" and k.status == POMIN and ctx.stan_run.get("baza_pominieta") == "brak zgody":
            d.append("Zsynchronizuj bazę po akceptacji: `python aktualizuj.py --tylko baza --zgoda baza`.")
    return d


def render_podsumowanie(ctx: Ctx) -> str:
    ds = dane_podsumowania(ctx)
    info, zm, latest = ds["info"], ds["zm"], ds["latest"]
    L = []
    tryb = "TRYB PRÓBNY (--dry-run) - nic nie zostało zmienione" if ctx.dry else "PODSUMOWANIE AKTUALIZACJI"
    L.append(f"=== {tryb} ===")
    L.append(f"Wynik: {wynik_ogolny(ctx)}")
    stan_txt = f"Stan danych na dzień: {fmt_data(info.get('data_as_of'))}"
    if not ctx.dry and info.get("data_as_of") and not ctx.stan_run.get("zweryfikowano"):
        stan_txt += " (data zapisu indeksów; ten przebieg nie potwierdził pełnej świeżości)"
    L.append(stan_txt)
    etyk_n = "Najnowszy w API (plan)" if (ctx.dry and not zm) else "Najnowszy"
    L.append(f"{etyk_n} Dz.U.: {latest.get('DU') or 'brak danych'}; M.P.: {latest.get('MP') or 'brak danych'}")
    if zm:
        L.append(f"Akty: nowych {len(zm.get('added') or [])}, zmienionych {len(zm.get('changed') or [])}, "
                 f"wycofanych {len(zm.get('removed') or [])}, bez zmian {zm.get('unchanged', '?')}")
    elif ctx.dry and ctx.stan_run.get("plan"):
        L.append("Plan (dane): " + _plan_opis(ctx.stan_run["plan"]))
    L.append("")
    L.append("Kroki:")
    for k in ctx.kroki:
        L.append(f"  {k.nazwa:<10} {STATUS_PL.get(k.status, k.status):<18} {k.opis}")
    if ctx.ostrzezenia:
        L.append("")
        L.append("Ostrzeżenia:")
        for w in ctx.ostrzezenia:
            L.append(f"  - {w}")
    dalej = co_dalej(ctx)
    if dalej:
        L.append("")
        L.append("Co dalej:")
        for x in dalej:
            L.append(f"  - {x}")
    if not ctx.dry and ctx.stan_run.get("raport"):
        L.append("")
        L.append(f"Raport: {ctx.stan_run['raport']}")
    return "\n".join(L)


def render_raport(ctx: Ctx) -> str:
    ds = dane_podsumowania(ctx)
    info, zm, latest = ds["info"], ds["zm"], ds["latest"]
    koniec = teraz()
    L = [f"# Raport aktualizacji - {ctx.start.strftime('%Y-%m-%d')}", ""]
    L.append(f"- **Wynik:** {wynik_ogolny(ctx)}")
    L.append(f"- **Start:** {ctx.start.strftime('%Y-%m-%d %H:%M:%S')}, **czas:** {time.time() - ctx.t0:.0f} s")
    L.append(f"- **Polecenie:** `{' '.join(['python', 'aktualizuj.py'] + list(ctx.argv))}`")
    L.append(f"- **Stan danych (data_as_of):** {fmt_data(info.get('data_as_of'))}"
             + (" (potwierdzony w tym przebiegu)" if ctx.stan_run.get("zweryfikowano") else ""))
    L.append(f"- **Najnowszy Dz.U.:** {latest.get('DU') or 'brak danych'}")
    L.append(f"- **Najnowszy M.P.:** {latest.get('MP') or 'brak danych'}")
    L.append("")
    L.append("## Zmiany w aktach")
    if zm:
        L.append(f"Nowych: **{len(zm.get('added') or [])}**, zmienionych: **{len(zm.get('changed') or [])}**, "
                 f"wycofanych: **{len(zm.get('removed') or [])}**, bez zmian: {zm.get('unchanged', '?')}.")
        for etyk, kl in (("Nowe", "added"), ("Zmienione", "changed"), ("Wycofane", "removed")):
            lst = zm.get(kl) or []
            if lst:
                L.append(f"- {etyk} (pierwsze {min(len(lst), 25)} z {len(lst)}): " + ", ".join(f"`{x}`" for x in lst[:25]))
        if zm.get("partial"):
            L.append("- Przebieg **częściowy** (błędy pobierania, odłożone akty albo ograniczenie `--lata`/`--max-akty`).")
    else:
        L.append("Brak danych o zmianach z tego przebiegu.")
    L.append("")
    L.append("## Kroki")
    L.append("| Krok | Status | Czas | Szczegóły |")
    L.append("|---|---|---|---|")
    for k in ctx.kroki:
        L.append(f"| {k.nazwa} | {STATUS_PL.get(k.status, k.status)} | {k.czas:.0f} s | {k.opis.replace('|', '/')} |")
    pomin = co_pominieto(ctx)
    if pomin:
        L.append("")
        L.append("## Co pominięto i dlaczego")
        for n, o in pomin:
            L.append(f"- **{n}:** {o}")
    if ctx.ostrzezenia:
        L.append("")
        L.append("## Ostrzeżenia")
        for w in ctx.ostrzezenia:
            L.append(f"- {w}")
    bledy = [k for k in ctx.kroki if k.status in (BLAD, ZABL, PRZER) and k.ogon]
    if bledy:
        L.append("")
        L.append("## Błędy (koniec wyjścia kroku)")
        for k in bledy:
            L.append(f"### {k.nazwa}")
            L.append("```")
            L.append(redaguj(k.ogon, ctx.sekrety)[-2500:])
            L.append("```")
    dalej = co_dalej(ctx)
    if dalej:
        L.append("")
        L.append("## Co dalej")
        for x in dalej:
            L.append(f"- {x}")
    if ctx.stan_run.get("kopia"):
        L.append("")
        L.append(f"Kopia zapasowa przed zmianami: `{Path(ctx.stan_run['kopia']).relative_to(ctx.root).as_posix()}/` "
                 "(jak cofnąć: docs/AKTUALIZACJA.md).")
    L.append("")
    L.append(f"_Raport wygenerowany {koniec.strftime('%Y-%m-%d %H:%M:%S')} przez aktualizuj.py. Nie zawiera sekretów._")
    return redaguj("\n".join(L) + "\n", ctx.sekrety)


def zapisz_raporty(ctx: Ctx) -> None:
    ctx.stan.mkdir(parents=True, exist_ok=True)
    dzien = ctx.start.strftime("%Y-%m-%d")
    rap = ctx.stan / f"raport_{dzien}.md"
    if rap.exists():     # drugi przebieg tego samego dnia: poprzedni raport zachowaj pod nazwa z godzina
        stary = ctx.stan / f"raport_{dzien}_{dt.datetime.fromtimestamp(rap.stat().st_mtime).strftime('%H%M%S')}.md"
        if not stary.exists():
            os.replace(rap, stary)
    ctx.stan_run["raport"] = rap.relative_to(ctx.root).as_posix()
    rap.write_text(render_raport(ctx), encoding="utf-8")
    ds = dane_podsumowania(ctx)
    zm = ds["zm"]
    zapisz_json(ctx.stan / "ostatnia_aktualizacja.json", {
        "run_at": ctx.start.isoformat(timespec="seconds"),
        "wynik": wynik_ogolny(ctx),
        "kod_wyjscia": kod_wyjscia(ctx),
        "data_as_of": ds["info"].get("data_as_of"),
        "najnowsze": ds["latest"],
        "akty": {"nowe": len(zm.get("added") or []), "zmienione": len(zm.get("changed") or []),
                 "wycofane": len(zm.get("removed") or []), "bez_zmian": zm.get("unchanged")},
        "kroki": {k.nazwa: k.status for k in ctx.kroki},
        "ostrzezenia": ctx.ostrzezenia,
        "raport": ctx.stan_run["raport"],
    })
    # pelny log (bez sekretow); zostaje 10 ostatnich
    log = ctx.stan / f"log_{ctx.start.strftime('%Y-%m-%d_%H%M%S')}.txt"
    log.write_text(redaguj("\n".join(ctx.linie_logu) + "\n", ctx.sekrety), encoding="utf-8")
    logi = sorted(ctx.stan.glob("log_????-??-??_??????.txt"))
    for stary in logi[:-10]:
        try:
            stary.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------------------------- blokada

def zajmij_blokade(ctx: Ctx):
    ctx.stan.mkdir(parents=True, exist_ok=True)
    lock = ctx.stan / "aktualizuj.lock"
    if lock.exists() and time.time() - lock.stat().st_mtime > 6 * 3600:
        lock.unlink()
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise SystemExit(f"Inna aktualizacja trwa albo została przerwana awaryjnie. Jeśli na pewno nie działa, "
                         f"usuń plik {lock} i uruchom ponownie.")
    os.write(fd, f"{os.getpid()} {teraz().isoformat(timespec='seconds')}\n".encode())
    os.close(fd)
    return lock


# ---------------------------------------------------------------------------------- glowna petla

def wykonaj(ctx: Ctx, kroki) -> None:
    for nazwa in kroki:
        k = Krok(nazwa=nazwa)
        ctx.kroki.append(k)
        if ctx.zatrzymano_na:
            k.status, k.opis = NIEWYK, f"nie wykonano (przerwano na kroku {ctx.zatrzymano_na})"
            continue
        ctx.log("")
        ctx.log(f"--- [{nazwa}] {OPISY[nazwa]} ---")
        t = time.time()
        try:
            FUNKCJE[nazwa](ctx, k)
        except KeyboardInterrupt:
            k.status, k.opis = PRZER, "przerwano (Ctrl+C) - uruchom ponownie, aby wznowić"
            k.czas = time.time() - t
            ctx.zatrzymano_na = nazwa
            raise Przerwanie()
        except SystemExit:
            raise
        except Exception as e:  # noqa: BLE001 - nieoczekiwany blad kroku
            k.status = BLAD
            k.opis = f"nieoczekiwany błąd: {type(e).__name__}: {redaguj(str(e), ctx.sekrety)}"
            k.ogon = redaguj(traceback.format_exc()[-2000:], ctx.sekrety)
        k.czas = time.time() - t
        if k.status == NIEWYK:
            k.status = OK
        for w in k.ostrzezenia:
            ctx.ostrzez(f"[{nazwa}] {w}")
        ctx.log(f"[{nazwa}] {STATUS_PL.get(k.status, k.status)} ({k.czas:.0f} s): {k.opis}")
        if k.status in (BLAD, ZABL, PRZER):
            if nazwa in KRYTYCZNE:
                ctx.zatrzymano_na = nazwa
            else:
                ctx.ostrzez(f"[{nazwa}] {k.opis}")
        if nazwa == "dane" and ctx.stan_run.get("pierwszy_raz"):
            ctx.stan_run["koniec_wczesnie"] = True
            for pozostale in [x for x in kroki if x not in {kk.nazwa for kk in ctx.kroki}]:
                kk = Krok(nazwa=pozostale, status=POMIN,
                          opis="pierwsze uruchomienie kończy się na budowie manifestu - kolejne kroki przy następnym uruchomieniu")
                ctx.kroki.append(kk)
            return


def zbuduj_parser():
    ap = argparse.ArgumentParser(
        prog="aktualizuj.py",
        description="Uaktualnij to wszystko: przyrostowa aktualizacja danych, bazy i strony prawa polskiego.",
        epilog="Kroki: " + " -> ".join(KROKI) + ". Zacznij od: python aktualizuj.py --dry-run",
    )
    ap.add_argument("--dry-run", action="store_true",
                    help="pokaż plan; niczego nie zmienia (ani danych, ani bazy, ani plików stanu)")
    ap.add_argument("--bez-bazy", action="store_true", help="pomiń synchronizację bazy Postgres")
    ap.add_argument("--bez-wdrozenia", action="store_true", help="pomiń push i wdrożenie na Vercel")
    ap.add_argument("--bez-zrodel", action="store_true", help="pomiń źródła dodatkowe (SAOS, EUR-Lex...)")
    ap.add_argument("--bez-testow", action="store_true", help="pomiń testy tsc + vitest")
    ap.add_argument("--tylko", choices=KROKI, metavar="KROK", help="wykonaj tylko jeden krok: " + ", ".join(KROKI))
    ap.add_argument("--pierwszy-raz", action="store_true",
                    help="zbuduj manifest z istniejących danych (bootstrap, bez pobierania) i zakończ")
    ap.add_argument("--zgoda", nargs="+", choices=["baza", "commit", "push", "wdrozenie"], default=[],
                    metavar="CO", help="jednorazowa zgoda właściciela na krok zewnętrzny: baza commit push wdrozenie")
    ap.add_argument("--lata", help="ogranicz do lat, np. 2025,2026 lub 2020-2026 (przebieg częściowy)")
    ap.add_argument("--max-akty", type=int, help="limit pobrań w tym przebiegu (do ostrożnych prób)")
    ap.add_argument("--force-removals", action="store_true",
                    help="zezwól na wycofanie > 3%% aktów (tylko po sprawdzeniu przyczyny!)")
    ap.add_argument("--config", help="inny plik konfiguracji (domyślnie .claude/uaktualnij.config.json)")
    return ap


def main(argv=None, root: Path | None = None, run=None, env_local: dict | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            try:
                s.reconfigure(encoding="utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                pass
    args = zbuduj_parser().parse_args(argv)
    root = Path(root or ROOT)
    cfg_path = Path(args.config) if args.config else root / ".claude" / "uaktualnij.config.json"
    cfg, ostrz_cfg = wczytaj_config(cfg_path)
    ctx = Ctx(root, args, cfg, run=run, env_local=env_local)
    ctx.argv = list(argv) if argv is not None else sys.argv[1:]
    for o in ostrz_cfg:
        ctx.ostrzez(o)
    kroki = [args.tylko] if args.tylko else list(KROKI)
    ctx.log(f"aktualizuj.py - {'TRYB PRÓBNY (dry-run)' if ctx.dry else 'aktualizacja'} - {ctx.start.strftime('%Y-%m-%d %H:%M')}")
    ctx.log(f"Kroki: {', '.join(kroki)}")
    ctx.log("Konfiguracja: " + ", ".join(f"{k}={cfg[k]}" for k in BOOL_KEYS)
            + (f", zgoda tym razem: {', '.join(args.zgoda)}" if args.zgoda else ""))
    ctx.log("Sekrety (DATABASE_URL, API_KEY) są czytane, ale nigdy wypisywane.")
    lock = None
    przerwano = False
    try:
        if not ctx.dry:
            lock = zajmij_blokade(ctx)
            if "info" in kroki and "commit" in kroki:
                ctx.stan_run["brudne_na_starcie"] = git_zmienione(ctx, STRONA_PLIKI)
        wykonaj(ctx, kroki)
    except Przerwanie:
        przerwano = True
        ctx.log("")
        ctx.log("Przerwano (Ctrl+C). Dane i kolejka zmian są spójne - uruchom aktualizację ponownie, aby wznowić.")
    finally:
        if lock is not None:
            try:
                lock.unlink()
            except OSError:
                pass
    if przerwano:
        for pozostale in kroki:
            if pozostale not in {k.nazwa for k in ctx.kroki}:
                ctx.kroki.append(Krok(nazwa=pozostale, status=NIEWYK, opis="nie wykonano (przerwano)"))
    if not ctx.dry:
        try:
            zapisz_raporty(ctx)
        except OSError as e:
            ctx.ostrzez(f"Nie udało się zapisać raportu: {e}")
    ctx.log("")
    ctx.log(render_podsumowanie(ctx))
    return 130 if przerwano else kod_wyjscia(ctx)


if __name__ == "__main__":
    sys.exit(main())
