# -*- coding: utf-8 -*-
"""Testy pipeline/update_data.py.

Uruchomienie (z korzenia repo):
    python -m unittest discover -s pipeline/tests -v
    PRAWO_LIVE_TEST=1 python -m unittest pipeline.tests.test_update_data.LiveApi   (zywe API, katalogi tymczasowe)

Testy 1-n uzywaja zamockowanego HTTP (FakeApi). Test bootstrap kopiuje MALA probke z prawdziwego dane/
do katalogu tymczasowego (jesli dane/ istnieje) - prawdziwego dane/ nigdy nie zmienia.
"""
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(ROOT))

import update_data as ud  # noqa: E402

OBOW = "obowiązujący"
TJ = "akt posiada tekst jednolity"
UCH = "uchylony"


class FakeApi:
    """Atrapa API ELI: get(url) -> (status, bytes), jak ud.Client.get."""

    def __init__(self):
        self.acts = {"DU": {}, "MP": {}}   # pub -> year -> {pos: item}
        self.body = {}                     # (pub, y, p, kind) -> bytes ; kind html|pdf|U
        self.ufile = {}                    # (y, p) -> fileName
        self.fail_year = set()
        self.empty_year = set()
        self.urls = []
        self.deliveries = []               # udane pobrania tresci
        self.raise_kbd_at = None           # numer pobrania tresci, ktore rzuca KeyboardInterrupt
        self._lock = threading.Lock()

    # --- budowanie danych
    def add(self, pub, y, p, status=OBOW, title=None, html=True, pdf=True, change="2026-01-01T00:00:00",
            typ="Ustawa", u=False, text=None, utext=None):
        title = title or f"Ustawa z dnia 1 stycznia {y} r. o testach nr {p}"
        item = {"address": f"W{pub}{y}{p:07d}", "announcementDate": f"{y}-01-02", "changeDate": change,
                "displayAddress": f"{'Dz.U.' if pub == 'DU' else 'M.P.'} {y} poz. {p}", "pos": p,
                "publisher": pub, "status": status, "textHTML": html, "textPDF": pdf, "title": title,
                "type": typ, "volume": 0, "year": y, "ELI": f"{pub}/{y}/{p}"}
        self.acts[pub].setdefault(y, {})[p] = item
        self.body[(pub, y, p, "html")] = (text or f"<html><body>ąęłóżźćń {pub}{y}{p}</body></html>").encode("utf-8")
        self.body[(pub, y, p, "pdf")] = b"%PDF-1.4\n" + (text or f"pdf {pub}{y}{p}").encode("utf-8")
        if u:
            self.ufile[(y, p)] = f"D{y}{p:04d}Lj.pdf"
            self.body[(pub, y, p, "U")] = b"%PDF-1.4\n" + (utext or f"U {y}{p}").encode("utf-8")
        return item

    def item(self, pub, y, p):
        return self.acts[pub][y][p]

    def set_content(self, pub, y, p, text, change=None, kind="html"):
        if kind == "U":
            self.body[(pub, y, p, "U")] = b"%PDF-1.4\n" + text.encode("utf-8")
        elif kind == "html":
            self.body[(pub, y, p, "html")] = text.encode("utf-8")
        else:
            self.body[(pub, y, p, "pdf")] = b"%PDF-1.4\n" + text.encode("utf-8")
        if change:
            self.item(pub, y, p)["changeDate"] = change

    def text_deliveries(self):
        return list(self.deliveries)

    # --- HTTP
    def get(self, url):
        with self._lock:
            self.urls.append(url)
        path = url[len(ud.API):]
        m = re.fullmatch(r"/acts/(DU|MP)", path)
        if m:
            pub = m.group(1)
            return 200, json.dumps({"years": sorted(self.acts[pub])}).encode("utf-8")
        m = re.fullmatch(r"/acts/(DU|MP)/(\d+)", path)
        if m:
            pub, y = m.group(1), int(m.group(2))
            if (pub, y) in self.fail_year:
                raise ud.HttpError(f"HTTP 503 dla {url} (po 5 probach)")
            if (pub, y) in self.empty_year:
                return 200, json.dumps({"count": 0, "items": []}).encode("utf-8")
            items = list(reversed(list(self.acts[pub].get(y, {}).values())))
            return 200, json.dumps({"count": len(items), "items": items}).encode("utf-8")
        m = re.fullmatch(r"/acts/(DU|MP)/(\d+)/(\d+)", path)
        if m:
            pub, y, p = m.group(1), int(m.group(2)), int(m.group(3))
            if p not in self.acts[pub].get(y, {}):
                return 404, b""
            texts = [{"fileName": "text.html", "type": "H"}]
            if (y, p) in self.ufile:
                texts.append({"fileName": self.ufile[(y, p)], "type": "U"})
            return 200, json.dumps({"texts": texts}).encode("utf-8")
        m = re.fullmatch(r"/acts/(DU|MP)/(\d+)/(\d+)/text\.(html|pdf)", path)
        if m:
            pub, y, p, ext = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
            return self._deliver((pub, y, p, ext))
        m = re.fullmatch(r"/acts/DU/(\d+)/(\d+)/text/U/(.+)", path)
        if m:
            y, p = int(m.group(1)), int(m.group(2))
            if self.ufile.get((y, p)) != m.group(3):
                return 404, b""
            return self._deliver(("DU", y, p, "U"))
        return 404, b""

    def _deliver(self, key):
        with self._lock:
            if key not in self.body:
                return 404, b""
            n = len(self.deliveries) + 1
            if self.raise_kbd_at is not None and n == self.raise_kbd_at:
                self.raise_kbd_at = None
                raise KeyboardInterrupt()
            self.deliveries.append(key)
            return 200, self.body[key]


def snapshot(root: Path):
    out = {}
    if root.exists():
        for p in sorted(root.rglob("*")):
            if p.is_file():
                out[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="prawo_ud_test_")
        self.addCleanup(self._tmp.cleanup)
        self.dane = Path(self._tmp.name) / "dane"
        self.stan = Path(self._tmp.name) / "stan"

    def run_ud(self, api, *extra, expect=0):
        argv = ["--dane", str(self.dane), "--stan", str(self.stan), "--workers", "2", *extra]
        code = ud.main(argv, client=api)
        self.assertEqual(code, expect, f"kod wyjscia {code} != {expect}")
        return code

    def zmiany(self):
        return json.loads((self.stan / "zmiany.json").read_text(encoding="utf-8"))

    def manifest(self):
        return json.loads((self.stan / "manifest.json").read_text(encoding="utf-8"))

    def index(self, name):
        return json.loads((self.dane / name).read_text(encoding="utf-8"))

    def basic_api(self):
        api = FakeApi()
        api.add("DU", 2025, 1, title="Ustawa z dnia 1 stycznia 2025 r. o żółwiach", u=True)
        api.add("DU", 2025, 2, html=False, title="Rozporządzenie Ministra z dnia 2 stycznia 2025 r. w sprawie łąk")
        api.add("DU", 2025, 3, status=UCH)
        api.add("DU", 2025, 4, status=TJ, u=True)
        api.add("MP", 2025, 1, typ="Uchwała", title="Uchwała nr 1 Rady Ministrów")
        return api


class TestNewAndUnchanged(Base):
    def test_first_run_downloads_everything_needed(self):
        api = self.basic_api()
        self.run_ud(api)
        self.assertTrue((self.dane / "podstawowe" / "DU_2025_1.html").is_file())
        self.assertTrue((self.dane / "podstawowe" / "DU_2025_2.pdf").is_file(), "tylko PDF -> pdf")
        self.assertTrue((self.dane / "mp" / "MP_2025_1.html").is_file())
        self.assertTrue((self.dane / "ujednolicone" / "U-DU_2025_1.pdf").is_file())
        self.assertTrue((self.dane / "ujednolicone" / "U-DU_2025_4.pdf").is_file())
        self.assertFalse((self.dane / "podstawowe" / "DU_2025_3.html").exists(), "uchylony nie jest pobierany")
        self.assertFalse((self.dane / "podstawowe" / "DU_2025_4.html").exists(), "status TJ: tylko wariant U")
        z = self.zmiany()
        self.assertEqual(set(z["added"]), {"DU/2025/1", "DU/2025/1#U", "DU/2025/2", "DU/2025/4#U", "MP/2025/1"})
        self.assertEqual(z["changed"], [])
        self.assertEqual(z["removed"], [])
        self.assertEqual(z["latest"]["DU"], "Dz.U. 2025 poz. 4")
        self.assertEqual(z["latest"]["MP"], "M.P. 2025 poz. 1")
        self.assertIn("run_at", z)
        # indeksy w dotychczasowym formacie
        obow = self.index("indeks_obowiazujacych.json")
        self.assertEqual({a["ELI"] for a in obow}, {"DU/2025/1", "DU/2025/2"})
        self.assertTrue(all(a["kategoria"] == "podstawowe" and a["status"] == OBOW for a in obow))
        self.assertIn("żółwiach", next(a for a in obow if a["pos"] == 1)["title"])
        self.assertEqual([a["ELI"] for a in self.index("indeks_mp.json")], ["MP/2025/1"])
        uj = self.index("indeks_ujednolicone.json")
        self.assertEqual({a["ELI"] for a in uj}, {"DU/2025/1", "DU/2025/4"})
        self.assertTrue(all(a["kategoria"] == "ujednolicone" for a in uj))
        # manifest
        m = self.manifest()
        e = m["DU/2025/1"]
        self.assertEqual(e["files"], ["podstawowe/DU_2025_1.html"])
        self.assertEqual(e["sha256"], hashlib.sha256((self.dane / e["files"][0]).read_bytes()).hexdigest())
        self.assertEqual(m["DU/2025/1#U"]["files"], ["ujednolicone/U-DU_2025_1.pdf"])
        self.assertTrue(m["DU/2025/2#U"]["no_text"])
        # brak resztek tymczasowych i dziennika
        self.assertEqual(list(self.dane.rglob("*.part")), [])
        self.assertFalse((self.stan / "biezacy_przebieg.json").exists())
        self.assertFalse((self.stan / "update.lock").exists())

    def test_second_run_is_noop(self):
        api = self.basic_api()
        self.run_ud(api)
        before = snapshot(self.dane)
        api.deliveries.clear()
        api.urls.clear()
        self.run_ud(api)
        z = self.zmiany()
        self.assertEqual((z["added"], z["changed"], z["removed"]), ([], [], []))
        self.assertEqual(z["unchanged"], 6)
        self.assertEqual(api.deliveries, [])
        self.assertFalse([u for u in api.urls if re.search(r"/acts/\w+/\d+/\d+", u)], "zadnych zapytan o akty")
        self.assertEqual(snapshot(self.dane), before)
        self.assertEqual(ud.main(["--dane", str(self.dane), "--stan", str(self.stan)], client=api), 0)


class TestChanged(Base):
    def test_changed_content_vs_touched_only(self):
        api = self.basic_api()
        self.run_ud(api)
        old_html = (self.dane / "podstawowe" / "DU_2025_1.html").read_bytes()
        api.set_content("DU", 2025, 1, "<html>NOWA tresc</html>", change="2026-05-05T10:00:00")
        api.item("DU", 2025, 2)["changeDate"] = "2026-05-05T10:00:00"     # tylko changeDate, ta sama tresc
        api.set_content("DU", 2025, 4, "nowe U", change="2026-06-06T00:00:00", kind="U")
        api.deliveries.clear()
        self.run_ud(api)
        z = self.zmiany()
        self.assertEqual(set(z["changed"]), {"DU/2025/1", "DU/2025/4#U"})
        self.assertEqual(z["added"], [])
        self.assertNotEqual((self.dane / "podstawowe" / "DU_2025_1.html").read_bytes(), old_html)
        self.assertEqual(self.manifest()["DU/2025/2"]["changeDate"], "2026-05-05T10:00:00")
        # trzeci przebieg: nic
        api.deliveries.clear()
        self.run_ud(api)
        z = self.zmiany()
        self.assertEqual((z["added"], z["changed"], z["removed"]), ([], [], []))
        self.assertEqual(api.deliveries, [])

    def test_category_change_moves_file_without_download(self):
        api = self.basic_api()
        self.run_ud(api)
        api.item("DU", 2025, 2)["title"] = "Ustawa z dnia 2 stycznia 2025 r. o zmianie ustawy o testach"
        api.deliveries.clear()
        self.run_ud(api)
        self.assertFalse((self.dane / "podstawowe" / "DU_2025_2.pdf").exists())
        self.assertTrue((self.dane / "zmieniajace" / "DU_2025_2.pdf").is_file())
        z = self.zmiany()
        self.assertIn("DU/2025/2", z["changed"])
        self.assertEqual(z["moved"], ["DU/2025/2"])
        self.assertEqual(api.deliveries, [])
        self.assertEqual(self.manifest()["DU/2025/2"]["kategoria"], "zmieniajace")
        self.assertIn("DU/2025/2", {a["ELI"] for a in self.index("indeks_obowiazujacych.json")
                                    if a["kategoria"] == "zmieniajace"})

    def test_missing_file_is_repaired_as_changed(self):
        api = self.basic_api()
        self.run_ud(api)
        (self.dane / "podstawowe" / "DU_2025_1.html").unlink()
        self.run_ud(api)
        self.assertTrue((self.dane / "podstawowe" / "DU_2025_1.html").is_file())
        z = self.zmiany()
        self.assertEqual(z["changed"], ["DU/2025/1"])
        self.assertEqual(z["added"], [])


def many_acts(n=100, y=2025):
    api = FakeApi()
    for p in range(1, n + 1):
        api.add("DU", y, p)
    api.add("MP", y, 1)      # puste API MP wygladaloby jak awaria (slusznie blokuje wycofywanie)
    return api


class TestRemoval(Base):
    def test_removed_status_moves_file_to_wycofane(self):
        api = many_acts(100)
        self.run_ud(api)
        api.item("DU", 2025, 7)["status"] = UCH           # 1% < 3%
        self.run_ud(api)
        z = self.zmiany()
        self.assertEqual(z["removed"], ["DU/2025/7"])
        self.assertFalse((self.dane / "podstawowe" / "DU_2025_7.html").exists())
        self.assertTrue((self.dane / "_wycofane" / "podstawowe" / "DU_2025_7.html").is_file())
        e = self.manifest()["DU/2025/7"]
        self.assertTrue(e["wycofany"])
        self.assertTrue(e["files"][0].startswith("_wycofane/podstawowe/"))
        self.assertNotIn(7, [a["pos"] for a in self.index("indeks_obowiazujacych.json")])
        self.assertEqual(len(self.index("indeks_obowiazujacych.json")), 99)

    def test_vanished_act_is_removed_and_can_return(self):
        api = many_acts(100)
        self.run_ud(api)
        removed_item = api.acts["DU"][2025].pop(9)
        self.run_ud(api)
        self.assertEqual(self.zmiany()["removed"], ["DU/2025/9"])
        self.assertTrue((self.dane / "_wycofane" / "podstawowe" / "DU_2025_9.html").is_file())
        # akt wraca
        api.acts["DU"][2025][9] = removed_item
        api.deliveries.clear()
        self.run_ud(api)
        z = self.zmiany()
        self.assertIn("DU/2025/9", z["changed"] + z["added"])
        self.assertTrue((self.dane / "podstawowe" / "DU_2025_9.html").is_file())
        self.assertFalse(self.manifest()["DU/2025/9"].get("wycofany"))

    def test_boundary_three_percent_allowed(self):
        api = many_acts(100)
        self.run_ud(api)
        for p in (1, 2, 3):
            api.item("DU", 2025, p)["status"] = UCH
        self.run_ud(api)
        self.assertEqual(len(self.zmiany()["removed"]), 3)

    def test_more_than_three_percent_aborts_without_changes(self):
        api = many_acts(100)
        self.run_ud(api)
        before_dane, before_manifest = snapshot(self.dane), (self.stan / "manifest.json").read_bytes()
        before_zm = (self.stan / "zmiany.json").read_bytes()
        for p in range(1, 11):
            api.item("DU", 2025, p)["status"] = UCH
        self.run_ud(api, expect=3)
        self.assertEqual(snapshot(self.dane), before_dane)
        self.assertEqual((self.stan / "manifest.json").read_bytes(), before_manifest)
        self.assertEqual((self.stan / "zmiany.json").read_bytes(), before_zm)
        self.assertFalse((self.dane / "_wycofane").exists())
        # --force-removals
        self.run_ud(api, "--force-removals")
        self.assertEqual(len(self.zmiany()["removed"]), 10)
        self.assertEqual(len(list((self.dane / "_wycofane" / "podstawowe").glob("*.html"))), 10)

    def test_api_returning_empty_year_does_not_remove_everything(self):
        api = many_acts(50)
        self.run_ud(api)
        api.empty_year.add(("DU", 2025))
        before = snapshot(self.dane)
        self.run_ud(api)                   # nie powinno rzucic Blocked: faza wycofywania pominieta
        self.assertEqual(snapshot(self.dane), before)
        z = self.zmiany()
        self.assertEqual(z["removed"], [])
        self.assertTrue(any("2025" in w for w in z["warnings"]))


class TestYearFailure(Base):
    def test_failed_year_blocks_removal_but_other_years_proceed(self):
        api = FakeApi()
        for p in range(1, 41):
            api.add("DU", 2024, p)
            api.add("DU", 2025, p)
        api.add("MP", 2025, 1)
        self.run_ud(api)
        # rok 2024 niedostepny, a 2024/1 "zniknal"; w 2025 jest realna zmiana
        api.fail_year.add(("DU", 2024))
        api.acts["DU"][2024].pop(1)
        api.set_content("DU", 2025, 3, "<html>zmiana 2025</html>", change="2026-09-09T09:09:09")
        self.run_ud(api)
        z = self.zmiany()
        self.assertEqual(z["removed"], [], "brak metadanych roku != wycofanie")
        self.assertIn("DU/2025/3", z["changed"])
        self.assertTrue(any("2024" in w for w in z["warnings"]))
        self.assertTrue(z["partial"])
        self.assertTrue((self.dane / "podstawowe" / "DU_2024_1.html").is_file())
        self.assertFalse(self.manifest()["DU/2024/1"].get("wycofany"))
        # indeks nadal zawiera akty z 2024 (metadane ze starego indeksu)
        self.assertEqual(len([a for a in self.index("indeks_obowiazujacych.json") if a["year"] == 2024]), 40)
        # po naprawie API faktyczne wycofanie dziala
        api.fail_year.clear()
        self.run_ud(api)
        self.assertEqual(self.zmiany()["removed"], ["DU/2024/1"])

    def test_whole_pub_list_failure_blocks_removal(self):
        api = self.basic_api()
        self.run_ud(api)
        before = snapshot(self.dane)
        orig = api.get

        def flaky(url):
            if url.endswith("/acts/MP"):
                raise ud.HttpError("HTTP 500")
            return orig(url)
        api.get = flaky
        self.run_ud(api)
        self.assertEqual(self.zmiany()["removed"], [])
        self.assertEqual(snapshot(self.dane), before)

    def test_all_metadata_failing_is_critical(self):
        api = self.basic_api()

        def dead(url):
            raise ud.HttpError("brak sieci")
        api.get = dead
        self.run_ud(api, expect=2)
        self.assertFalse(self.dane.exists() and any(self.dane.rglob("*.html")))


class TestResume(Base):
    def test_interrupted_run_resumes_and_reports_everything(self):
        api = many_acts(10)
        api.raise_kbd_at = 4
        code = ud.main(["--dane", str(self.dane), "--stan", str(self.stan), "--workers", "1"], client=api)
        self.assertEqual(code, 130)
        self.assertTrue((self.stan / "biezacy_przebieg.json").is_file(), "dziennik przerwanego przebiegu")
        done_first = len(api.deliveries)
        self.assertGreaterEqual(done_first, 1)
        mfirst = self.manifest()
        self.assertEqual(len([k for k, e in mfirst.items() if e.get("files")]), done_first)
        # symulacja twardego przerwania: resztka .part
        (self.dane / "podstawowe").mkdir(parents=True, exist_ok=True)
        (self.dane / "podstawowe" / "DU_2025_9.html.123.456.part").write_bytes(b"polowa")
        code = ud.main(["--dane", str(self.dane), "--stan", str(self.stan), "--workers", "1"], client=api)
        self.assertEqual(code, 0)
        # kazda tresc pobrana dokladnie raz
        self.assertEqual(len(api.deliveries), 11)
        self.assertEqual(len(set(api.deliveries)), 11)
        z = self.zmiany()
        self.assertEqual(len(z["added"]), 11, "zmiany.json uwzglednia akty z przerwanego przebiegu")
        self.assertEqual(list(self.dane.rglob("*.part")), [])
        self.assertFalse((self.stan / "biezacy_przebieg.json").exists())
        self.assertEqual(len(self.index("indeks_obowiazujacych.json")), 10)

    def test_max_akty_limits_and_continues(self):
        api = many_acts(10)
        self.run_ud(api, "--max-akty", "8")      # 4 akty + 4 kandydaci na U (najnowsze najpierw)
        self.assertEqual(len(list((self.dane / "podstawowe").glob("*.html"))), 4)
        # najnowsze najpierw
        self.assertTrue((self.dane / "podstawowe" / "DU_2025_10.html").is_file())
        z = self.zmiany()
        self.assertEqual(len(z["added"]), 4)
        self.assertGreater(z["odlozone"], 0)
        self.run_ud(api)
        self.assertEqual(len(list((self.dane / "podstawowe").glob("*.html"))), 10)
        self.assertEqual(len(self.zmiany()["added"]), 7)     # 6 DU + MP/2025/1

    def test_adopts_file_left_by_crash_between_write_and_manifest(self):
        api = many_acts(3)
        (self.dane / "podstawowe").mkdir(parents=True)
        pre = api.body[("DU", 2025, 2, "html")]
        (self.dane / "podstawowe" / "DU_2025_2.html").write_bytes(pre)
        self.run_ud(api)
        self.assertEqual(len(api.deliveries), 4 - 1)     # 3 DU + 1 MP, jeden przyjety z dysku
        self.assertIn("DU/2025/2", self.zmiany()["added"])


class TestDryRun(Base):
    def test_dry_run_writes_only_plan(self):
        api = self.basic_api()
        self.run_ud(api, "--dry-run")
        self.assertEqual(api.deliveries, [])
        self.assertFalse(self.dane.exists() and any(self.dane.rglob("*")))
        self.assertEqual(sorted(p.name for p in self.stan.rglob("*") if p.is_file()), ["plan_dry_run.json"])
        plan = json.loads((self.stan / "plan_dry_run.json").read_text(encoding="utf-8"))
        self.assertEqual(plan["podsumowanie"]["dodac"], 6)   # 5 + brak-U-kandydat DU/2025/2#U
        self.assertTrue(plan["dry_run"])

    def test_dry_run_after_real_run_changes_nothing(self):
        api = many_acts(100)
        self.run_ud(api)
        for p in range(1, 4):
            api.item("DU", 2025, p)["status"] = UCH
        api.set_content("DU", 2025, 50, "<html>x</html>", change="2027-01-01T00:00:00")
        api.add("DU", 2025, 101)
        d0, s0 = snapshot(self.dane), snapshot(self.stan)
        self.run_ud(api, "--dry-run")
        self.assertEqual(snapshot(self.dane), d0)
        s1 = snapshot(self.stan)
        self.assertEqual({k: v for k, v in s1.items() if k != "plan_dry_run.json"}, s0)
        plan = json.loads((self.stan / "plan_dry_run.json").read_text(encoding="utf-8"))
        self.assertEqual(len(plan["do_wycofania"]), 3)
        self.assertIn("DU/2025/50", plan["do_sprawdzenia"])
        self.assertIn("DU/2025/101", plan["dodac"])

    def test_dry_run_reports_block_at_over_3_percent(self):
        api = many_acts(100)
        self.run_ud(api)
        for p in range(1, 21):
            api.item("DU", 2025, p)["status"] = UCH
        d0 = snapshot(self.dane)
        self.run_ud(api, "--dry-run", expect=3)
        self.assertEqual(snapshot(self.dane), d0)


class TestRobustness(Base):
    def test_invalid_pdf_body_is_failure_and_retried_next_run(self):
        api = FakeApi()
        api.add("DU", 2025, 1, html=False)
        api.add("DU", 2025, 2, html=False)
        api.add("MP", 2025, 1)
        api.body[("DU", 2025, 1, "pdf")] = b"<html>Error 500</html>"
        self.run_ud(api)
        z = self.zmiany()
        self.assertEqual([f["klucz"] for f in z["failed"]], ["DU/2025/1"])
        self.assertNotIn("DU/2025/1", self.manifest())
        self.assertFalse((self.dane / "podstawowe" / "DU_2025_1.pdf").exists())
        self.assertIn("DU/2025/2", z["added"])
        api.body[("DU", 2025, 1, "pdf")] = b"%PDF-1.4 ok"
        self.run_ud(api)
        self.assertIn("DU/2025/1", self.zmiany()["added"])

    def test_truncated_year_listing_is_treated_as_failure(self):
        api = many_acts(50)
        self.run_ud(api)
        orig = api.get

        def trunc(url):
            st, body = orig(url)
            if url.endswith("/acts/DU/2025"):
                d = json.loads(body)
                d["items"] = d["items"][:5]          # count=50, items=5
                return st, json.dumps(d).encode("utf-8")
            return st, body
        api.get = trunc
        before = snapshot(self.dane)
        self.run_ud(api)
        z = self.zmiany()
        self.assertEqual(z["removed"], [])
        self.assertTrue(any("2025" in w for w in z["warnings"]))
        self.assertEqual(snapshot(self.dane), before)

    def test_lata_scope_does_not_remove_other_years(self):
        api = FakeApi()
        for p in range(1, 51):
            api.add("DU", 2024, p)
            api.add("DU", 2025, p)
        api.add("MP", 2025, 1)
        self.run_ud(api)
        api.acts["DU"][2024].clear()                  # gdyby rok 2024 byl w zakresie, to by sie wycofalo
        api.acts["DU"][2024][1] = api.acts["DU"][2025][1]
        api.item("DU", 2025, 2)["status"] = UCH
        api.urls.clear()
        self.run_ud(api, "--lata", "2025")
        z = self.zmiany()
        self.assertEqual(z["removed"], ["DU/2025/2"])
        self.assertFalse([u for u in api.urls if u.endswith("/acts/DU/2024")])
        self.assertTrue((self.dane / "podstawowe" / "DU_2024_5.html").is_file())
        self.assertEqual(len([a for a in self.index("indeks_obowiazujacych.json") if a["year"] == 2024]), 50)
        self.assertEqual(z["latest"]["DU"], "Dz.U. 2025 poz. 50")
        self.assertTrue(z["partial"])

    def test_full_reverifies_by_sha(self):
        api = self.basic_api()
        self.run_ud(api)
        api.deliveries.clear()
        api.body[("DU", 2025, 1, "html")] = b"<html>podmienione bez zmiany changeDate</html>"
        self.run_ud(api, "--full")
        z = self.zmiany()
        self.assertEqual(z["changed"], ["DU/2025/1"])
        self.assertGreaterEqual(len(api.deliveries), 5)

    def test_corrupt_manifest_is_not_overwritten(self):
        api = self.basic_api()
        self.stan.mkdir(parents=True)
        (self.stan / "manifest.json").write_text("{ucięty", encoding="utf-8")
        self.run_ud(api, expect=2)
        self.assertEqual((self.stan / "manifest.json").read_text(encoding="utf-8"), "{ucięty")

    def test_concurrent_run_is_refused(self):
        api = self.basic_api()
        self.stan.mkdir(parents=True)
        (self.stan / "update.lock").write_text("1 x")
        self.run_ud(api, expect=2)


class TestClientRetry(unittest.TestCase):
    class Resp:
        def __init__(self, code, content=b"", headers=None):
            self.status_code, self.content, self.headers = code, content, headers or {}

    class Sess:
        def __init__(self, seq):
            self.seq = list(seq)
            self.calls = 0

        def get(self, url, timeout=None):
            self.calls += 1
            x = self.seq.pop(0)
            if isinstance(x, Exception):
                raise x
            return x

    def client(self, seq):
        import requests
        c = ud.Client(workers=2, retries=4, backoff=0.01)
        sess = self.Sess(seq)
        c._session = lambda: sess
        return c, sess, requests

    def test_retries_then_succeeds(self):
        import requests
        R = self.Resp
        c, sess, _ = self.client([R(503), requests.ConnectionError("x"), R(429, headers={"Retry-After": "0"}), R(200, b"ok")])
        self.assertEqual(c.get("https://x/y"), (200, b"ok"))
        self.assertEqual(sess.calls, 4)
        self.assertEqual(c.n_retries, 3)

    def test_404_returned_not_retried(self):
        c, sess, _ = self.client([self.Resp(404)])
        self.assertEqual(c.get("u"), (404, b""))
        self.assertEqual(sess.calls, 1)

    def test_gives_up_with_http_error(self):
        c, sess, _ = self.client([self.Resp(500)] * 4)
        with self.assertRaises(ud.HttpError):
            c.get("u")
        self.assertEqual(sess.calls, 4)

    def test_4xx_fails_fast(self):
        c, sess, _ = self.client([self.Resp(403)])
        with self.assertRaises(ud.HttpError):
            c.get("u")
        self.assertEqual(sess.calls, 1)


class TestUtils(unittest.TestCase):
    def test_parse_lata(self):
        self.assertEqual(ud.parse_lata("2025,2026"), {2025, 2026})
        self.assertEqual(ud.parse_lata("2020-2022"), {2020, 2021, 2022})
        self.assertIsNone(ud.parse_lata(None))

    def test_merge_op(self):
        self.assertEqual(ud.merge_op(None, "added"), "added")
        self.assertEqual(ud.merge_op("added", "changed"), "added")
        self.assertEqual(ud.merge_op("added", "removed"), "removed")
        self.assertEqual(ud.merge_op("removed", "added"), "changed")
        self.assertEqual(ud.merge_op("changed", "changed"), "changed")

    def test_atomic_write_no_leftovers(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a" / "b.bin"
            ud.atomic_write_bytes(p, b"x")
            ud.atomic_write_bytes(p, b"yy")
            self.assertEqual(p.read_bytes(), b"yy")
            self.assertEqual([x.name for x in p.parent.iterdir()], ["b.bin"])

    def test_polish_literals_are_correct_code_points(self):
        self.assertEqual(ud.ST_OBOW, "obowiązujący")
        self.assertEqual(ud.ST_TJ, "akt posiada tekst jednolity")

    def test_client_headers_and_limits(self):
        self.assertIn("PrawoAPI", ud.USER_AGENT)
        self.assertLessEqual(ud.MAX_WORKERS, 12)


REAL_DANE = ROOT / "dane"


@unittest.skipUnless((REAL_DANE / "indeks_mp.json").is_file(), "brak prawdziwego dane/ - test probki pominiety")
class TestBootstrapOnSampleCopy(Base):
    """Bootstrap na KOPII malej probki prawdziwych danych (prawdziwy dane/ tylko do odczytu)."""

    def make_sample(self, n=6):
        names = {"obow": "indeks_obowiazujacych.json", "mp": "indeks_mp.json", "uj": "indeks_ujednolicone.json"}
        self.dane.mkdir(parents=True)
        sample = {}
        for k, fn in names.items():
            items = json.loads((REAL_DANE / fn).read_text(encoding="utf-8"))
            picked = []
            for a in items[::-1]:
                stem = (f"U-DU_{a['year']}_{a['pos']}.pdf" if k == "uj" else None)
                cand = [stem] if stem else [f"{a['publisher']}_{a['year']}_{a['pos']}.html",
                                            f"{a['publisher']}_{a['year']}_{a['pos']}.pdf"]
                for c in cand:
                    src = REAL_DANE / a["kategoria"] / c
                    if src.is_file() and src.stat().st_size < 3_000_000:
                        (self.dane / a["kategoria"]).mkdir(exist_ok=True)
                        shutil.copy2(src, self.dane / a["kategoria"] / c)
                        picked.append(a)
                        break
                if len(picked) >= n:
                    break
            (self.dane / fn).write_text(json.dumps(picked, ensure_ascii=False, indent=1), encoding="utf-8")
            sample[k] = picked
        return sample

    def api_from_sample(self, sample):
        api = FakeApi()
        seen = {}
        for k in ("obow", "mp", "uj"):
            for a in sample[k]:
                key = (a["publisher"], a["year"], a["pos"])
                if key in seen and seen[key]["status"] == OBOW:
                    continue
                it = {x: v for x, v in a.items() if x != "kategoria"}
                if k == "uj" and not any(b["ELI"] == a["ELI"] for b in sample["obow"]):
                    it["status"] = TJ     # probka: akt spoza probki "obow" nie jest tu osobnym celem
                seen[key] = it
        for (pub, y, p), it in seen.items():
            api.acts[pub].setdefault(y, {})[p] = it
        for a in sample["uj"]:
            api.ufile[(a["year"], a["pos"])] = f"D{a['year']}{a['pos']:04d}Lj.pdf"
        return api

    def test_bootstrap_builds_manifest_without_downloading(self):
        sample = self.make_sample()
        before = snapshot(self.dane)
        api = FakeApi()   # bootstrap nie moze dotknac sieci
        api.get = lambda url: (_ for _ in ()).throw(AssertionError("siec w bootstrapie: " + url))
        self.run_ud(api, "--bootstrap")
        m = self.manifest()
        n_main = len(sample["obow"]) + len(sample["mp"])
        mains = {k for k in m if not k.endswith("#U")}
        self.assertEqual(len(mains), n_main)
        ujkeys = {f"DU/{a['year']}/{a['pos']}#U" for a in sample["uj"]}
        self.assertTrue(ujkeys <= set(m))
        for k, e in m.items():
            if e.get("files"):
                self.assertTrue((self.dane / e["files"][0]).is_file(), k)
        # dane/ nie zmienione (poza brakiem zapisow - bootstrap pisze tylko stan/)
        self.assertEqual(snapshot(self.dane), before)
        self.assertEqual(self.zmiany()["added"], [])
        # --hash
        self.run_ud(api, "--bootstrap", "--hash")
        e = self.manifest()[next(iter(mains))]
        self.assertEqual(e["sha256"], hashlib.sha256((self.dane / e["files"][0]).read_bytes()).hexdigest())

    def test_run_after_bootstrap_is_noop_and_detects_single_change(self):
        sample = self.make_sample()
        self.run_ud(FakeApi(), "--bootstrap")
        api = self.api_from_sample(sample)
        before = snapshot(self.dane)
        self.run_ud(api)                    # jawnie bez --bootstrap: manifest juz jest
        z = self.zmiany()
        self.assertEqual((z["added"], z["changed"], z["removed"]), ([], [], []), z)
        self.assertEqual(api.deliveries, [])
        # indeksy zgodne semantycznie z oryginalem probki
        for n, k in (("indeks_obowiazujacych.json", "obow"), ("indeks_mp.json", "mp"), ("indeks_ujednolicone.json", "uj")):
            got = {(a["year"], a["pos"]) for a in self.index(n)}
            self.assertEqual(got, {(a["year"], a["pos"]) for a in sample[k]}, n)
        self.assertEqual({k: v for k, v in snapshot(self.dane).items() if not k.endswith(".json")},
                         {k: v for k, v in before.items() if not k.endswith(".json")})
        # jedna zmiana
        a = sample["mp"][0]
        api.set_content("MP", a["year"], a["pos"], "<html>zmieniona tresc</html>", change="2099-01-01T00:00:00")
        api.item("MP", a["year"], a["pos"])["textHTML"] = True
        self.run_ud(api)
        z = self.zmiany()
        self.assertEqual(z["changed"], [f"MP/{a['year']}/{a['pos']}"])
        self.assertEqual(z["added"], [])

    def test_implicit_bootstrap_when_manifest_missing(self):
        sample = self.make_sample(4)
        api = self.api_from_sample(sample)
        self.run_ud(api)                    # brak manifestu + sa indeksy => niejawny bootstrap
        z = self.zmiany()
        self.assertEqual((z["added"], z["changed"], z["removed"]), ([], [], []))
        self.assertTrue((self.stan / "manifest.json").is_file())


@unittest.skipUnless(os.environ.get("PRAWO_LIVE_TEST") == "1", "ustaw PRAWO_LIVE_TEST=1, aby uruchomic test na zywym API")
class LiveApi(Base):
    def test_live_small_run_in_temp_dirs(self):
        argv = ["--dane", str(self.dane), "--stan", str(self.stan), "--lata", "2026",
                "--max-akty", "15", "--workers", "4"]
        self.assertEqual(ud.main(argv + ["--dry-run"]), 0)
        self.assertEqual(sorted(p.name for p in self.stan.rglob("*") if p.is_file()), ["plan_dry_run.json"])
        self.assertEqual(ud.main(argv), 0)
        z = self.zmiany()
        self.assertTrue(0 < len(z["added"]) <= 15, z["added"])
        self.assertEqual(z["removed"], [])
        self.assertTrue(z["latest"]["DU"].startswith("Dz.U. 2026"), z["latest"])
        files = [p for p in self.dane.rglob("*") if p.is_file() and p.suffix in (".html", ".pdf")]
        self.assertTrue(files)
        for f in files:
            self.assertGreater(f.stat().st_size, 100)
            if f.suffix == ".pdf":
                self.assertEqual(f.read_bytes()[:5], b"%PDF-")
        self.assertEqual(list(self.dane.rglob("*.part")), [])
        idx = self.index("indeks_obowiazujacych.json")
        self.assertTrue(idx and all(a["status"] == OBOW and a["year"] == 2026 for a in idx))
        # ponowny przebieg z tym samym limitem dobiera kolejne, nie rusza juz pobranych
        before = snapshot(self.dane)
        self.assertEqual(ud.main(argv), 0)
        for k, v in before.items():
            if not k.endswith(".json"):
                self.assertEqual(snapshot(self.dane).get(k), v, k)


if __name__ == "__main__":
    unittest.main(verbosity=2)
