# -*- coding: utf-8 -*-
"""Testy jednostkowe orkiestratora aktualizuj.py - z atrapa podprocesow (bez sieci, bez bazy, bez git/npm).

Uruchomienie:  python -m unittest discover -s tests -v
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import aktualizuj as A  # noqa: E402

SEKRET = "TajneHaslo123XYZ"
DB_URL = f"postgresql://uzytkownik:{SEKRET}@ep-test.eu-central-1.aws.neon.tech/neondb?sslmode=require"


def zapisz(p: Path, tekst="", binarnie=False):
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(tekst, (dict, list)):
        tekst = json.dumps(tekst, ensure_ascii=False)
    p.write_text(tekst, encoding="utf-8")


def teraz_iso(offset_s=0):
    return (A.teraz() + A.dt.timedelta(seconds=offset_s)).isoformat(timespec="seconds")


class Atrapa:
    """Podmienia ctx.run: rozpoznaje skrypt po nazwie i zachowuje sie jak prawdziwy."""

    def __init__(self, root: Path):
        self.root = root
        self.wywolania = []
        self.kody = {}                  # nazwa skryptu -> kod wyjscia
        self.zmiany = {"added": [], "changed": [], "removed": []}
        self.partial = False
        self.git_zmienione = " M vercel/public/data-info.json"
        self.upstream = True
        self.rzuc_przerwanie_w = None
        self.brudne_na_starcie = ""

    def nazwy(self):
        return [Path(c[1]).name if "python" in Path(c[0]).name.lower() or c[0] == sys.executable else Path(c[0]).name
                for c, _ in self.wywolania]

    def wywolania_skryptu(self, nazwa):
        return [c for c, _ in self.wywolania if len(c) > 1 and Path(c[1]).name == nazwa]

    def __call__(self, cmd, cwd=None, env=None, timeout=None, glosno=True):
        self.wywolania.append((list(cmd), cwd))
        exe = Path(cmd[0]).name.lower()
        if exe.startswith("python") or cmd[0] == sys.executable:
            nazwa = Path(cmd[1]).name
            if nazwa == self.rzuc_przerwanie_w:
                raise KeyboardInterrupt()
            kod = self.kody.get(nazwa, 0)
            if nazwa == "update_data.py":
                return self._update_data(cmd, kod)
            if nazwa == "build_data_info.py":
                if "--dry-run" not in cmd:
                    p = self.root / "vercel" / "public" / "data-info.json"
                    info = json.loads(p.read_text(encoding="utf-8"))
                    info["last_update_run"] = teraz_iso()
                    zapisz(p, info)
                return kod, "Stan danych na dzień 12.10.2026; Dz.U.: Dz.U. 2026 poz. 1317 (10.10.2026)"
            if nazwa == "export_chunks.py":
                return kod, "zmiany: ok\n! OSTRZEZENIE: brak pliku/metadanych dla DU/2020/1 - pomijam" if kod == 0 else "blad"
            if nazwa == "load_to_postgres.py":
                if kod == 0:
                    return 0, "Sync gotowy: usunieto 1 dok., zaladowano 3 dok. / 30 fragm., pominieto przez limit 0, brak w plikach 0.\nBaza teraz: dokumentow 100, fragmentow 900, rozmiar 300 MB, czas 3s"
                return kod, "Nie mozna polaczyc z baza"
            return kod, ""
        if exe.startswith("git"):
            if cmd[1] == "status":
                self.status_wywolania = getattr(self, "status_wywolania", 0) + 1
                if self.status_wywolania == 1 and not self.brudne_na_starcie:
                    return 0, ""          # pierwsze wywolanie = stan sprzed aktualizacji
                if self.status_wywolania == 1:
                    return 0, self.brudne_na_starcie
                return 0, self.git_zmienione
            if cmd[1] == "rev-parse":
                return (0, "origin/main") if self.upstream else (128, "no upstream")
            return self.kody.get("git-" + cmd[1], 0), ""
        if exe.startswith("npm"):
            return self.kody.get("npm-" + cmd[1], 0), "Tests  46 passed (46)"
        if exe.startswith("vercel"):
            return self.kody.get("vercel", 0), "Production: https://prawo-test.vercel.app [3s]"
        return 0, ""

    def _update_data(self, cmd, kod):
        stan = Path(cmd[cmd.index("--stan") + 1])
        if "--dry-run" in cmd:
            zapisz(stan / "plan_dry_run.json", {
                "podsumowanie": {"dodac": 5, "do_sprawdzenia_changeDate": 2, "do_naprawy_brak_pliku": 0,
                                 "zmiana_kategorii": 0, "do_wycofania": 1, "bez_zmian": 100},
                "ostrzezenia": [], "latest": {"DU": "Dz.U. 2026 poz. 1317", "MP": "M.P. 2026 poz. 990"}})
            return 0, "plan"
        if kod != 0:
            return kod, "BLAD"
        if "--bootstrap" in cmd:
            zapisz(stan / "manifest.json", {"DU/2026/1": {}})
            zapisz(stan / "zmiany.json", {"run_at": teraz_iso(), "added": [], "changed": [], "removed": [],
                                         "unchanged": 3, "latest": {}, "bootstrap": True})
            return 0, "Bootstrap"
        zapisz(stan / "zmiany.json", {
            "run_at": teraz_iso(), **self.zmiany, "unchanged": 100,
            "latest": {"DU": "Dz.U. 2026 poz. 1317", "MP": "M.P. 2026 poz. 990"},
            "partial": self.partial, "warnings": [], "failed": [], "odlozone": 0})
        return 0, "Nowe: ..."


class BazaTestu(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        for n in A.INDEKSY:
            zapisz(self.root / "dane" / n, [])
        zapisz(self.root / "pipeline" / "out" / "chunks.jsonl", '{"doc_id": "DU/1/1"}\n')
        zapisz(self.root / "pipeline" / "out" / "raport.txt", "raport\n")
        for s in ("update_data.py", "export_chunks.py", "load_to_postgres.py", "build_data_info.py"):
            zapisz(self.root / "pipeline" / s, "")
        zapisz(self.root / "vercel" / "public" / "data-info.json",
               {"data_as_of": "2026-10-11", "dz_u": {"latest_act": "Dz.U. 2026 poz. 1307"},
                "m_p": {"latest_act": "M.P. 2026 poz. 977"}})
        zapisz(self.root / "vercel" / "public" / "index.html", "<html></html>")
        zapisz(self.root / "vercel" / "public" / "podlacz.html", "<html></html>")
        (self.root / "vercel" / "node_modules").mkdir(parents=True)
        zapisz(self.root / "zrodla" / "sources.json", [
            {"id": "eli-du", "enabled": True, "skrypt": None},
            {"id": "saos", "enabled": False, "skrypt": "zrodla/saos/fetch.py"}])
        zapisz(self.root / "stan" / "manifest.json", {"DU/2026/1": {}})
        zapisz(self.root / ".claude" / "uaktualnij.config.json", {
            "auto_load_db": True, "auto_commit": True, "auto_push": False, "auto_deploy": False,
            "backup_before_update": True, "baza_max_mb": 450, "kopie_zachowaj": 5})
        self.atrapa = Atrapa(self.root)

    def uruchom(self, *argv, env_local=None, which=True):
        wyj = io.StringIO()
        (self.root / ".git").mkdir(exist_ok=True)
        with contextlib.redirect_stdout(wyj), mock.patch.dict(os.environ),                 mock.patch.object(A.shutil, "which", (lambda n: n) if which else (lambda n: None)):
            os.environ.pop("DATABASE_URL", None)
            os.environ.pop("API_KEY", None)
            kod = A.main(list(argv), root=self.root, run=self.atrapa, env_local=env_local or {})
        return kod, wyj.getvalue()

    def drzewo(self):
        return {str(p.relative_to(self.root)): (p.stat().st_mtime_ns, p.stat().st_size)
                for p in self.root.rglob("*") if p.is_file()}


class TestDryRun(BazaTestu):
    def test_dry_run_niczego_nie_zmienia(self):
        przed = self.drzewo()
        kod, wyj = self.uruchom("--dry-run")
        self.assertEqual(kod, 0)
        self.assertEqual(self.drzewo(), przed)
        self.assertFalse((self.root / "stan" / "kopie").exists())
        self.assertFalse((self.root / "stan" / "kolejka.json").exists())
        self.assertIn("nic nie zostało zmienione", wyj)
        self.assertIn("5 do dodania", wyj)
        # dry-run nie uruchamia zapisujacych krokow
        nazwy = [Path(c[1]).name for c, _ in self.atrapa.wywolania if Path(c[0]).name.lower().startswith("python")]
        self.assertIn("update_data.py", nazwy)
        self.assertNotIn("export_chunks.py", nazwy)
        self.assertNotIn("load_to_postgres.py", nazwy)
        for c, _ in self.atrapa.wywolania:
            if c[1:2] and Path(c[1]).name == "update_data.py":
                self.assertIn("--dry-run", c)
        self.assertFalse(any(Path(c[0]).name.startswith(("npm", "vercel")) for c, _ in self.atrapa.wywolania))

    def test_dry_run_uzywa_kopii_stanu_nie_prawdziwego(self):
        self.uruchom("--dry-run")
        stan_arg = [c[c.index("--stan") + 1] for c in self.atrapa.wywolania_skryptu("update_data.py")]
        self.assertTrue(all(Path(s) != self.root / "stan" for s in stan_arg))
        self.assertFalse(any(Path(s).exists() for s in stan_arg))     # katalog tymczasowy posprzatany

    def test_dry_run_pierwsze_uruchomienie_bez_manifestu(self):
        (self.root / "stan" / "manifest.json").unlink()
        przed = self.drzewo()
        kod, wyj = self.uruchom("--dry-run")
        self.assertEqual(kod, 0)
        self.assertEqual(self.drzewo(), przed)
        self.assertIn("PLAN pierwszego uruchomienia", wyj)


class TestPierwszyRaz(BazaTestu):
    def test_brak_manifestu_robi_bootstrap_i_konczy(self):
        (self.root / "stan" / "manifest.json").unlink()
        kod, wyj = self.uruchom()
        self.assertEqual(kod, 0)
        c = self.atrapa.wywolania_skryptu("update_data.py")
        self.assertEqual(len(c), 1)
        self.assertIn("--bootstrap", c[0])
        self.assertEqual(self.atrapa.wywolania_skryptu("export_chunks.py"), [])
        self.assertEqual(self.atrapa.wywolania_skryptu("load_to_postgres.py"), [])
        self.assertIn("PIERWSZE URUCHOMIENIE", wyj)
        self.assertTrue(list((self.root / "stan").glob("raport_*.md")))

    def test_flaga_pierwszy_raz_przy_istniejacym_manifescie(self):
        kod, _ = self.uruchom("--pierwszy-raz")
        self.assertEqual(kod, 0)
        self.assertIn("--bootstrap", self.atrapa.wywolania_skryptu("update_data.py")[0])

    def test_brak_manifestu_i_indeksow_to_blad_bez_pelnego_pobrania(self):
        (self.root / "stan" / "manifest.json").unlink()
        for n in A.INDEKSY:
            (self.root / "dane" / n).unlink()
        kod, wyj = self.uruchom()
        self.assertEqual(kod, 1)
        self.assertEqual(self.atrapa.wywolania_skryptu("update_data.py"), [])
        self.assertIn("pełne pobranie", wyj)


class TestPelnyPrzebieg(BazaTestu):
    def przygotuj_zmiany(self):
        self.atrapa.zmiany = {"added": ["DU/2026/1317", "DU/2026/1317#U"], "changed": ["DU/2020/5"],
                              "removed": ["DU/2019/9"]}

    def test_pelny_przebieg_z_baza(self):
        self.przygotuj_zmiany()
        kod, wyj = self.uruchom("--zgoda", "wdrozenie", env_local={"DATABASE_URL": DB_URL})
        self.assertEqual(kod, 0, wyj)
        # kolejnosc krokow
        nazwy = []
        for c, _ in self.atrapa.wywolania:
            e = Path(c[0]).name.lower()
            nazwy.append(Path(c[1]).name if e.startswith("python") else e.split(".")[0] + (":" + c[1] if e.startswith("git") else ""))
        porzadek = [n for n in nazwy if n in ("update_data.py", "export_chunks.py", "build_data_info.py",
                                               "load_to_postgres.py", "vercel", "npm")]
        self.assertEqual(porzadek[0], "update_data.py")
        self.assertLess(porzadek.index("export_chunks.py"), porzadek.index("build_data_info.py"))
        self.assertLess(porzadek.index("build_data_info.py"), porzadek.index("npm"))
        self.assertLess(porzadek.index("npm"), porzadek.index("load_to_postgres.py"))
        self.assertLess(porzadek.index("load_to_postgres.py"), porzadek.index("vercel"))
        # eksport dostaje scalony plik zmian
        exp = self.atrapa.wywolania_skryptu("export_chunks.py")[0]
        zm = json.loads(Path(exp[exp.index("--changed") + 1]).read_text(encoding="utf-8"))
        self.assertEqual(zm["added"], ["DU/2026/1317", "DU/2026/1317#U"])
        self.assertEqual(zm["changed"], ["DU/2020/5"])
        self.assertEqual(zm["removed"], ["DU/2019/9"])
        # loader: --sync, --input z chunks.jsonl, --max-mb
        lo = self.atrapa.wywolania_skryptu("load_to_postgres.py")[0]
        self.assertIn("--sync", lo)
        self.assertIn("--max-mb", lo)
        self.assertEqual(lo[lo.index("--max-mb") + 1], "450")
        self.assertTrue(lo[lo.index("--input") + 1].endswith("chunks.jsonl"))
        # kolejka oprozniona, raporty zapisane
        kol = json.loads((self.root / "stan" / "kolejka.json").read_text(encoding="utf-8"))
        self.assertEqual(A.ile_w_sekcji(kol["eksport"]), 0)
        self.assertEqual(A.ile_w_sekcji(kol["baza"]), 0)
        oa = json.loads((self.root / "stan" / "ostatnia_aktualizacja.json").read_text(encoding="utf-8"))
        self.assertEqual(oa["akty"], {"nowe": 2, "zmienione": 1, "wycofane": 1, "bez_zmian": 100})
        self.assertEqual(oa["kod_wyjscia"], 0)
        rap = next((self.root / "stan").glob("raport_*.md")).read_text(encoding="utf-8")
        self.assertIn("Dz.U. 2026 poz. 1317", rap)
        self.assertIn("M.P. 2026 poz. 990", rap)
        self.assertIn("Nowych: **2**", rap)
        # commit + deploy (zgoda tylko na wdrozenie; push bez zgody)
        git_cmd = [c[1] for c, _ in self.atrapa.wywolania if Path(c[0]).name == "git"]
        self.assertIn("commit", git_cmd)
        self.assertNotIn("push", git_cmd)
        commit = next(c for c, _ in self.atrapa.wywolania if Path(c[0]).name == "git" and c[1] == "commit")
        self.assertIn("Co-Authored-By: Claude", commit[commit.index("-m") + 1])
        self.assertTrue(any(Path(c[0]).name == "vercel" for c, _ in self.atrapa.wywolania))
        self.assertTrue((self.root / "stan" / "ostatnie_wdrozenie.json").exists())

    def test_kopia_przed_zmianami_zawiera_tylko_male_pliki(self):
        self.przygotuj_zmiany()
        self.uruchom("--bez-bazy", "--bez-wdrozenia")
        kopie = list((self.root / "stan" / "kopie").iterdir())
        self.assertEqual(len(kopie), 1)
        pliki = {p.relative_to(kopie[0]).as_posix() for p in kopie[0].rglob("*") if p.is_file()}
        self.assertIn("stan/manifest.json", pliki)
        self.assertIn("dane/indeks_mp.json", pliki)
        self.assertIn("pipeline/out/raport.txt", pliki)
        self.assertNotIn("pipeline/out/chunks.jsonl", pliki)

    def test_sekret_nie_trafia_do_wyjscia_raportu_i_logu(self):
        self.przygotuj_zmiany()
        self.atrapa.kody["load_to_postgres.py"] = 1       # blad -> ogon trafia do raportu
        orig = self.atrapa.__call__

        def gadatliwa(cmd, **kw):
            kod, out = orig(cmd, **kw)
            if Path(cmd[1]).name == "load_to_postgres.py" if len(cmd) > 1 else False:
                out += f"\nconnect {DB_URL} nie dziala"
            return kod, out
        ctx_run = self.atrapa
        self.atrapa = gadatliwa
        kod, wyj = self.uruchom(env_local={"DATABASE_URL": DB_URL})
        self.assertEqual(kod, 1)
        tekst = wyj
        for p in (self.root / "stan").glob("raport_*.md"):
            tekst += p.read_text(encoding="utf-8")
        for p in (self.root / "stan").glob("log_*.txt"):
            tekst += p.read_text(encoding="utf-8")
        tekst += (self.root / "stan" / "ostatnia_aktualizacja.json").read_text(encoding="utf-8")
        self.assertNotIn(SEKRET, tekst)
        self.assertIn("***", tekst)

    def test_brak_database_url_pomija_baze_i_wstrzymuje_wdrozenie(self):
        self.przygotuj_zmiany()
        kod, wyj = self.uruchom("--zgoda", "wdrozenie", "push", env_local={})
        self.assertEqual(kod, 0)
        self.assertEqual(self.atrapa.wywolania_skryptu("load_to_postgres.py"), [])
        kol = json.loads((self.root / "stan" / "kolejka.json").read_text(encoding="utf-8"))
        self.assertGreater(A.ile_w_sekcji(kol["baza"]), 0)        # zmiany czekaja na baze
        self.assertFalse(any(Path(c[0]).name == "vercel" for c, _ in self.atrapa.wywolania))
        self.assertFalse(any(Path(c[0]).name == "git" and c[1] == "push" for c, _ in self.atrapa.wywolania))
        self.assertIn("DATABASE_URL", wyj)

    def test_blad_bazy_zatrzymuje_commit_i_wdrozenie_a_kolejka_przetrwa(self):
        self.przygotuj_zmiany()
        self.atrapa.kody["load_to_postgres.py"] = 1
        kod, wyj = self.uruchom("--zgoda", "wdrozenie", env_local={"DATABASE_URL": DB_URL})
        self.assertEqual(kod, 1)
        self.assertFalse(any(Path(c[0]).name == "git" and c[1] == "commit" for c, _ in self.atrapa.wywolania))
        self.assertFalse(any(Path(c[0]).name == "vercel" for c, _ in self.atrapa.wywolania))
        self.assertIn("BŁĄD na kroku „baza”", wyj)
        # drugi przebieg: brak nowych zmian, ale zalegle zmiany trafiaja do bazy
        self.atrapa.kody.pop("load_to_postgres.py")
        self.atrapa.zmiany = {"added": [], "changed": [], "removed": []}
        self.atrapa.wywolania.clear()
        time.sleep(1.1)       # run_at (rozdzielczosc 1 s) musi sie roznic od poprzedniego przebiegu
        kod, wyj = self.uruchom(env_local={"DATABASE_URL": DB_URL})
        self.assertEqual(kod, 0, wyj)
        lo = self.atrapa.wywolania_skryptu("load_to_postgres.py")
        self.assertEqual(len(lo), 1)
        zm = json.loads((self.root / "stan" / "zmiany_do_bazy.json").read_text(encoding="utf-8"))
        self.assertEqual(zm["added"], ["DU/2026/1317", "DU/2026/1317#U"])
        self.assertEqual(zm["removed"], ["DU/2019/9"])

    def test_plik_strony_brudny_przed_aktualizacja_nie_trafia_do_commita(self):
        self.atrapa.brudne_na_starcie = " M vercel/public/index.html"
        self.atrapa.git_zmienione = " M vercel/public/data-info.json"
        self.uruchom(env_local={"DATABASE_URL": DB_URL})
        add = next(c for c, _ in self.atrapa.wywolania if Path(c[0]).name == "git" and c[1] == "add")
        self.assertNotIn("vercel/public/index.html", add)
        self.assertIn("vercel/public/data-info.json", add)

    def test_zabezpieczenie_update_data_kod_3(self):
        self.atrapa.kody["update_data.py"] = 3
        kod, wyj = self.uruchom(env_local={"DATABASE_URL": DB_URL})
        self.assertEqual(kod, 3)
        self.assertEqual(self.atrapa.wywolania_skryptu("export_chunks.py"), [])
        self.assertIn("ZABLOKOWANO", wyj)
        self.assertIn("--force-removals", wyj)
        oa = json.loads((self.root / "stan" / "ostatnia_aktualizacja.json").read_text(encoding="utf-8"))
        self.assertEqual(oa["kroki"]["eksport"], A.NIEWYK)

    def test_force_removals_jest_przekazywane(self):
        self.uruchom("--force-removals", "--bez-bazy", "--bez-wdrozenia")
        self.assertIn("--force-removals", self.atrapa.wywolania_skryptu("update_data.py")[0])

    def test_brak_zmian_pomija_eksport_i_baze(self):
        kod, wyj = self.uruchom(env_local={"DATABASE_URL": DB_URL})
        self.assertEqual(kod, 0)
        self.assertEqual(self.atrapa.wywolania_skryptu("export_chunks.py"), [])
        self.assertEqual(self.atrapa.wywolania_skryptu("load_to_postgres.py"), [])
        self.assertIn("kolejka pusta", wyj)

    def test_przerwanie_ctrl_c_zapisuje_raport_i_zwalnia_blokade(self):
        self.atrapa.rzuc_przerwanie_w = "update_data.py"
        kod, wyj = self.uruchom()
        self.assertEqual(kod, 130)
        self.assertFalse((self.root / "stan" / "aktualizuj.lock").exists())
        self.assertTrue(list((self.root / "stan").glob("raport_*.md")))
        self.assertIn("PRZERWANO", wyj)

    def test_blokada_przed_drugim_uruchomieniem(self):
        zapisz(self.root / "stan" / "aktualizuj.lock", "1 test")
        with self.assertRaises(SystemExit):
            self.uruchom()

    def test_tylko_jeden_krok(self):
        kod, _ = self.uruchom("--tylko", "info")
        self.assertEqual(kod, 0)
        self.assertEqual(len(self.atrapa.wywolania_skryptu("build_data_info.py")), 1)
        self.assertEqual(self.atrapa.wywolania_skryptu("update_data.py"), [])

    def test_przebieg_czesciowy_nie_potwierdza_swiezosci_indeksow(self):
        indeks = self.root / "dane" / "indeks_mp.json"
        stary = time.time() - 86400 * 3
        for n in A.INDEKSY:
            os.utime(self.root / "dane" / n, (stary, stary))
        self.atrapa.partial = True
        self.uruchom("--bez-bazy", "--bez-wdrozenia", "--bez-testow")
        self.assertAlmostEqual(indeks.stat().st_mtime, stary, delta=2)
        self.atrapa.partial = False
        time.sleep(1.1)
        self.uruchom("--bez-bazy", "--bez-wdrozenia", "--bez-testow")
        self.assertGreater(indeks.stat().st_mtime, stary + 86400)

    def test_zrodla_wlaczone_sa_uruchamiane_i_ich_zmiany_ida_do_bazy(self):
        zapisz(self.root / "zrodla" / "sources.json", [
            {"id": "eurlex", "enabled": True, "skrypt": "zrodla/eurlex/fetch.py",
             "wyjscie": "pipeline/out/chunks_eurlex.jsonl"}])
        zapisz(self.root / "zrodla" / "eurlex" / "fetch.py", "")
        zapisz(self.root / "pipeline" / "out" / "chunks_eurlex.jsonl", '{"doc_id": "CELEX/32016R0679"}\n')
        zapisz(self.root / "stan" / "zmiany_eurlex.json",
               {"run_at": teraz_iso(5), "added": ["CELEX/32016R0679"], "changed": [], "removed": []})
        kod, wyj = self.uruchom(env_local={"DATABASE_URL": DB_URL})
        self.assertEqual(kod, 0, wyj)
        self.assertEqual(len(self.atrapa.wywolania_skryptu("fetch.py")), 1)
        lo = self.atrapa.wywolania_skryptu("load_to_postgres.py")[0]
        wej = lo[lo.index("--input") + 1:lo.index("--max-mb")]
        self.assertEqual([Path(x).name for x in wej], ["chunks.jsonl", "chunks_eurlex.jsonl"])
        zm = json.loads((self.root / "stan" / "zmiany_do_bazy.json").read_text(encoding="utf-8"))
        self.assertIn("CELEX/32016R0679", zm["added"])

    def test_uspione_zrodla_nie_sa_uruchamiane(self):
        self.uruchom(env_local={"DATABASE_URL": DB_URL})
        self.assertEqual(self.atrapa.wywolania_skryptu("fetch.py"), [])

    def test_push_tylko_za_zgoda_i_przy_zgodnej_bazie(self):
        self.przygotuj_zmiany()
        self.uruchom("--zgoda", "push", env_local={"DATABASE_URL": DB_URL})
        self.assertTrue(any(Path(c[0]).name == "git" and c[1] == "push" for c, _ in self.atrapa.wywolania))

    def test_bez_wdrozenia_wylacza_push_i_vercel(self):
        self.przygotuj_zmiany()
        self.uruchom("--zgoda", "push", "wdrozenie", "--bez-wdrozenia", env_local={"DATABASE_URL": DB_URL})
        self.assertFalse(any(Path(c[0]).name == "git" and c[1] == "push" for c, _ in self.atrapa.wywolania))
        self.assertFalse(any(Path(c[0]).name == "vercel" for c, _ in self.atrapa.wywolania))

    def test_drugi_przebieg_tego_samego_dnia_zachowuje_poprzedni_raport(self):
        self.uruchom("--bez-bazy", "--bez-wdrozenia", "--bez-testow")
        time.sleep(1.1)
        self.uruchom("--bez-bazy", "--bez-wdrozenia", "--bez-testow")
        self.assertGreaterEqual(len(list((self.root / "stan").glob("raport_*.md"))), 2)


class TestKonfiguracjaIPomocnicze(unittest.TestCase):
    def test_config_domyslny_gdy_brak_pliku(self):
        cfg, ostrz = A.wczytaj_config(Path("/nie/ma/takiego.json"))
        self.assertFalse(cfg["auto_push"])
        self.assertFalse(cfg["auto_deploy"])
        self.assertTrue(ostrz)

    def test_config_nie_bool_to_false(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.json"
            zapisz(p, {"auto_push": "tak", "auto_deploy": 1, "auto_commit": True})
            cfg, ostrz = A.wczytaj_config(p)
        self.assertIs(cfg["auto_push"], False)
        self.assertIs(cfg["auto_deploy"], False)
        self.assertIs(cfg["auto_commit"], True)
        self.assertEqual(len(ostrz), 2)

    def test_config_zepsuty_json_to_domyslne(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.json"
            p.write_text("{nie json", encoding="utf-8")
            cfg, ostrz = A.wczytaj_config(p)
        self.assertFalse(cfg["auto_push"])
        self.assertTrue(ostrz)

    def test_scalanie_operacji(self):
        s = A.scal_operacje
        self.assertEqual(s({"a": "added"}, {"a": "changed"}), {"a": "added"})
        self.assertEqual(s({"a": "added"}, {"a": "removed"}), {"a": "removed"})
        self.assertEqual(s({"a": "removed"}, {"a": "added"}), {"a": "changed"})
        self.assertEqual(s({"a": "removed"}, {"a": "changed"}), {"a": "changed"})
        self.assertEqual(s({"a": "changed"}, {"a": "removed"}), {"a": "removed"})
        self.assertEqual(s({"a": "changed"}, {"a": "added"}), {"a": "changed"})
        self.assertEqual(s({"a": "added"}, {"b": "removed"}), {"a": "added", "b": "removed"})

    def test_redakcja_sekretow(self):
        t = A.redaguj(f"polaczenie {DB_URL} oraz haslo {SEKRET}", A.zbierz_sekrety({"DATABASE_URL": DB_URL}))
        self.assertNotIn(SEKRET, t)
        t2 = A.redaguj("postgresql://u:innehaslo@host/db", set())
        self.assertNotIn("innehaslo", t2)
        self.assertIn("***", t2)

    def test_publiczne_zmienne_nie_sa_sekretami(self):
        env = {"DATABASE_URL": DB_URL, "NEXT_PUBLIC_SITE_URL": "https://prawo-pl.vercel.app",
               "NEXT_PUBLIC_ANON_KEY": "publiczny-klucz-123", "SOME_URL": "https://example.com/strona",
               "OPENAI_API_KEY": "sk-tajny-klucz-123", "REDIS_URL": "redis://u:redishaslo@host:6379"}
        sek = A.zbierz_sekrety(env)
        self.assertNotIn("https://prawo-pl.vercel.app", sek)
        self.assertNotIn("https://example.com/strona", sek)
        self.assertNotIn("publiczny-klucz-123", sek)
        self.assertIn("sk-tajny-klucz-123", sek)
        self.assertIn("redishaslo", sek)
        self.assertIn(SEKRET, sek)
        self.assertIn("https://prawo-pl.vercel.app", A.redaguj("adres https://prawo-pl.vercel.app", sek))

    def test_pominiete_przez_limit_wracaja_do_kolejki_bazy(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "stan").mkdir()
            zapisz(root / "stan" / "pominiete_limit.json", {"doc_ids": ["DU/2026/1", "DU/2026/2"]})
            zapisz(root / "stan" / "kolejka.json", {"baza": {"removed": ["DU/2026/2"], "added": [], "changed": []},
                                                    "eksport": {}, "ingested": {}})
            args = A.zbuduj_parser().parse_args([])
            ctx = A.Ctx(root, args, dict(A.DEFAULT_CONFIG), run=lambda *a, **k: (0, ""), env_local={})
            ids = A.dolacz_pominiete_limitem(ctx)
            self.assertEqual(ids, ["DU/2026/1", "DU/2026/2"])
            kol = ctx.wczytaj_kolejke()
            self.assertEqual(kol["baza"]["added"], ["DU/2026/1"])
            self.assertEqual(kol["baza"]["removed"], ["DU/2026/2"], "pozniejsze wycofanie ma pierwszenstwo")

    def test_env_local_parser(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / ".env.local"
            p.write_text("# komentarz\nDATABASE_URL=\"postgresql://a:b@c/d\"\nexport API_KEY=abc\n\n", encoding="utf-8")
            e = A.wczytaj_env_local(p)
        self.assertEqual(e["DATABASE_URL"], "postgresql://a:b@c/d")
        self.assertEqual(e["API_KEY"], "abc")

    def test_format_daty(self):
        self.assertEqual(A.fmt_data("2026-10-11"), "11.10.2026")
        self.assertEqual(A.fmt_data("2026-10-11T15:21:00+02:00"), "11.10.2026")
        self.assertEqual(A.fmt_data(None), "brak danych")


class TestRetencjaKopii(BazaTestu):
    def test_zostaje_tylko_n_najnowszych_kopii(self):
        kopie = self.root / "stan" / "kopie"
        for i in range(7):
            (kopie / f"2026-01-0{i + 1}_000000").mkdir(parents=True)
        (kopie / "wlasny-katalog-uzytkownika").mkdir()
        self.uruchom("--tylko", "kopia")
        nazwy = sorted(p.name for p in kopie.iterdir())
        daty = [n for n in nazwy if n[:2] == "20"]
        self.assertEqual(len(daty), 5)
        self.assertNotIn("2026-01-01_000000", daty)
        self.assertIn("wlasny-katalog-uzytkownika", nazwy)       # cudzych katalogow nie ruszamy


if __name__ == "__main__":
    unittest.main()
