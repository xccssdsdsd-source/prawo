"""Testy fetchera SAOS z mockiem (bez sieci)."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ZR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ZR))
import _common as C  # noqa: E402

spec = importlib.util.spec_from_file_location("saos_fetch", ZR / "saos" / "fetch.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)

PL = "zażółć gęślą jaźń"
ORIG_LOAD_COURTS = S.load_courts
BODY_HTML = ("<p>Sygnatura akt I C 1055/23</p> <div> <h2>WYROK CZĘŚCIOWY</h2> <h5>W IMIENIU RZECZYPOSPOLITEJ POLSKIEJ</h5>"
             "<p>Dnia 1 września 2026 r. Sąd Okręgowy w Warszawie I Wydział Cywilny w składzie: " + PL + "</p>"
             + "".join(f"<p>Uzasadnienie część {i}. " + ("Sąd zważył, co następuje. " * 30) + "</p>" for i in range(12)) + "</div>")


def item(i=551102, ctype="COMMON", html=BODY_HTML, **kw):
    d = {"id": i, "courtType": ctype, "courtCases": [{"caseNumber": "I C 1055/23"}], "judgmentType": "SENTENCE",
         "judgmentDate": "2026-09-01",
         "source": {"code": "COMMON_COURT", "judgmentUrl": "http://orzeczenia.ms.gov.pl/ncourt-api/judgement/details?id=x",
                    "publicationDate": "2026-10-04"},
         "textContent": html,
         "legalBases": ["art. 405 kc"],
         "referencedRegulations": [{"journalTitle": "Ustawa z dnia 23 kwietnia 1964 r. - Kodeks cywilny", "journalNo": 16,
                                    "journalYear": 1964, "journalEntry": 93, "text": "Dz.U. 1964 nr 16 poz. 93"}],
         "keywords": ["bezpodstawne wzbogacenie"]}
    d.update(kw)
    return d


class TestRows(unittest.TestCase):
    def test_wiersze_zgodne_ze_schematem(self):
        rows, why = S.item_to_rows(item(), {"COMMON"}, 150000)
        self.assertEqual(why, "ok")
        self.assertEqual(C.validate_rows(rows), [])
        r0 = rows[0]
        self.assertEqual((r0["doc_id"], r0["eli"], r0["kategoria"], r0["status"]), ("SAOS/551102", "SAOS/551102", "wyrok", "orzeczenie"))
        self.assertEqual(r0["announcement_date"], "2026-09-01")
        self.assertIsNone(r0["article"])
        self.assertEqual(r0["heading"], "Sąd Okręgowy w Warszawie, sygn. I C 1055/23, 01.09.2026")
        self.assertTrue(all(r["heading"] == r0["heading"] for r in rows))
        self.assertIn("Dz.U. 1964 nr 16 poz. 93 (DU/1964/93)", r0["text"])
        self.assertIn("Słowa kluczowe: bezpodstawne wzbogacenie", r0["text"])
        self.assertTrue(r0["title"].startswith("Wyrok – Sąd Okręgowy w Warszawie"))
        self.assertGreater(len(rows), 3)
        self.assertTrue(all(len(r["text"]) <= 2000 for r in rows))
        self.assertIn(PL, "\n".join(r["text"] for r in rows))  # polskie znaki zachowane

    def test_source_url(self):
        rows, _ = S.item_to_rows(item(), {"COMMON"}, 150000)
        self.assertEqual(rows[0]["source_url"], "https://www.saos.org.pl/judgments/551102")  # ncourt-api -> strona SAOS
        it = item(ctype="SUPREME")
        it["source"]["judgmentUrl"] = "https://www.sn.pl/orzecznictwo/Strony/x.aspx?id=1"
        rows, _ = S.item_to_rows(it, {"SUPREME"}, 150000)
        self.assertEqual(rows[0]["source_url"], "https://www.sn.pl/orzecznictwo/Strony/x.aspx?id=1")
        self.assertIn("oryginał: https://www.sn.pl", rows[0]["text"])

    def test_filtr_typu_i_pusty(self):
        self.assertEqual(S.item_to_rows(item(ctype="COMMON"), {"SUPREME"}, 1000), (None, "typ"))
        self.assertEqual(S.item_to_rows(item(html=""), {"COMMON"}, 1000), (None, "pusty"))
        self.assertEqual(S.item_to_rows({"courtType": "COMMON"}, {"COMMON"}, 1000), (None, "zly"))

    def test_nazwa_sadu_heurystyka(self):
        self.assertEqual(S.guess_court("SUPREME", "Wyrok. Sąd Najwyższy w składzie"), "Sąd Najwyższy")
        self.assertEqual(S.guess_court("ADMINISTRATIVE", "Wojewódzki Sąd Administracyjny w Gorzowie Wielkopolskim po rozpoznaniu"),
                         "Wojewódzki Sąd Administracyjny w Gorzowie Wielkopolskim")
        self.assertEqual(S.guess_court("COMMON", "bez nazwy sądu"), "Sąd powszechny")
        self.assertEqual(S.guess_court("COMMON", "Sąd Rejonowy w Łodzi Wydział"), "Sąd Rejonowy w Łodzi")
        self.assertEqual(S.guess_court("COMMON", "Sąd Okręgowy w Jeleniej Górze w VI Wydziale Karnym Odwoławczym"),
                         "Sąd Okręgowy w Jeleniej Górze")
        self.assertEqual(S.guess_court("COMMON", "Sąd Okręgowy w Warszawie I Wydział Cywilny"), "Sąd Okręgowy w Warszawie")
        self.assertEqual(S.guess_court("COMMON", "Sąd Rejonowy dla Warszawy-Mokotowa w Warszawie, II Wydział"),
                         "Sąd Rejonowy dla Warszawy-Mokotowa w Warszawie")
        self.assertEqual(S.guess_court("COMMON", "Sąd Okręgowy w Olsztynie Wydział I Cywilny"), "Sąd Okręgowy w Olsztynie")

    def test_slownik_sadow(self):
        courts = {"common": {"1630": {"court": "Sąd Okręgowy w Poznaniu", "division": "II Wydział Cywilny Odwoławczy"}},
                  "sc": {"7": "Izba Karna Wydział VI"}}
        it = item(division={"id": 1630})
        rows, _ = S.item_to_rows(it, {"COMMON"}, 150000, courts)
        self.assertEqual(rows[0]["heading"], "Sąd Okręgowy w Poznaniu, sygn. I C 1055/23, 01.09.2026")
        self.assertIn("Wydział/izba: II Wydział Cywilny Odwoławczy", rows[0]["text"])
        rows, _ = S.item_to_rows(item(ctype="SUPREME", division={"id": 7}), {"SUPREME"}, 150000, courts)
        self.assertTrue(rows[0]["heading"].startswith("Sąd Najwyższy, sygn."))
        self.assertIn("Wydział/izba: Izba Karna Wydział VI", rows[0]["text"])
        # nieznany wydzial -> heurystyka z tresci
        rows, _ = S.item_to_rows(item(division={"id": 99999}), {"COMMON"}, 150000, courts)
        self.assertTrue(rows[0]["heading"].startswith("Sąd Okręgowy w Warszawie,"))

    def test_fetch_courts_i_cache(self):
        pages = {
            "commonCourts": {"links": [], "items": [{"id": 1, "name": "Sąd Apelacyjny we Wrocławiu",
                                                    "divisions": [{"id": 1, "name": "I Wydział Cywilny"}, {"id": 2, "name": "II Wydział Karny"}]}]},
            "scChambers": {"items": [{"id": 1, "name": "Izba Karna", "divisions": [{"id": 4, "name": "Wydział I", "fullName": "Izba Karna Wydział I"}]}]},
        }
        calls = []

        def fake(url, limiter):
            calls.append(url)
            return pages["commonCourts" if "commonCourts" in url else "scChambers"]

        with tempfile.TemporaryDirectory() as d, mock.patch.object(S, "get_json", fake):
            c = S.fetch_courts(None)
            self.assertEqual(c["common"]["2"], {"court": "Sąd Apelacyjny we Wrocławiu", "division": "II Wydział Karny"})
            self.assertEqual(c["sc"]["4"], "Izba Karna Wydział I")
            n = len(calls)
            first = ORIG_LOAD_COURTS(None, Path(d))
            self.assertEqual(first["common"]["1"]["court"], "Sąd Apelacyjny we Wrocławiu")
            n2 = len(calls)
            self.assertGreater(n2, n)
            ORIG_LOAD_COURTS(None, Path(d))  # z cache - bez nowych zapytan
            self.assertEqual(len(calls), n2)
            f = Path(d) / S.COURTS_FILE
            cached = json.loads(f.read_text(encoding="utf-8"))
            cached["fetched"] = "2026-01-01"  # przeterminowany
            f.write_text(json.dumps(cached), encoding="utf-8")
            ORIG_LOAD_COURTS(None, Path(d))
            self.assertGreater(len(calls), n2)

    def test_slownik_sadow_blad_to_none(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(S, "get_json", side_effect=C.FetchError("x")):
            self.assertIsNone(ORIG_LOAD_COURTS(None, Path(d)))

    def test_prune_retry(self):
        import datetime as dt
        today = dt.date(2026, 10, 11)
        r = {"1": {"n": 0, "od": "2026-10-10"}, "2": {"n": 6, "od": "2026-10-10"}, "3": {"n": 0, "od": "2026-06-01"}}
        self.assertEqual(list(S.prune_retry(r, today)), ["1"])
        big = {str(i): {"n": 0, "od": "2026-10-10"} for i in range(2500)}
        self.assertEqual(len(S.prune_retry(big, today)), 2000)

    def test_limit_rozmiaru(self):
        rows, _ = S.item_to_rows(item(), {"COMMON"}, 3000)
        self.assertIn("pominięta", rows[-1]["text"])
        self.assertEqual(C.validate_rows(rows), [])

    def test_dlugi_akapit_bez_utraty_limitu(self):
        rows, _ = S.item_to_rows(item(html="<p>" + ("Słowo " * 3000) + "</p>"), {"COMMON"}, 150000)
        self.assertTrue(all(len(r["text"]) <= 2000 for r in rows))

    def test_urls(self):
        u = S.dump_url("2026-10-01T00:00:00.000", 2, 100)
        self.assertIn("withGenerated=false", u)
        self.assertIn("pageNumber=2", u)
        self.assertIn("sinceModificationDate=2026-10-01T00%3A00%3A00.000", u)
        self.assertEqual(S.next_link({"links": [{"rel": "next", "href": "http://www.saos.org.pl/api/dump/judgments?pageNumber=1"}]}),
                         "https://www.saos.org.pl/api/dump/judgments?pageNumber=1")
        self.assertIsNone(S.next_link({"links": [{"rel": "next", "href": "https://evil.example/x"}]}))
        self.assertIsNone(S.next_link({"links": [{"rel": "self", "href": "x"}]}))


class TestMain(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = str(Path(self.tmp.name) / "chunks_saos.jsonl")
        self.stan = str(Path(self.tmp.name) / "stan")
        for target, repl in ((C, ("sleep", lambda s: None)), (S, ("load_courts", lambda limiter, stan_dir: None))):
            p = mock.patch.object(target, repl[0], repl[1])
            p.start()
            self.addCleanup(p.stop)
        self.calls = []

    def run_main(self, pages, extra=(), judgments=None):
        """pages: lista odpowiedzi dumpa po kolei; judgments: id -> data dla /api/judgments/{id}."""
        it = iter(pages)

        def fake(url, limiter):
            self.calls.append(url)
            if "/api/judgments/" in url:
                jid = url.rsplit("/", 1)[1]
                return {"data": (judgments or {}).get(jid, {})}
            x = next(it)
            if isinstance(x, Exception):
                raise x
            return x

        with mock.patch.object(S, "get_json", fake):
            return S.main(["--force", "--out", self.out, "--stan-dir", self.stan, "--delay", "0",
                           "--typy", "wszystkie", *extra])

    def page(self, items, nxt=None):
        links = [{"rel": "self", "href": "https://www.saos.org.pl/api/dump/judgments?pageNumber=0"}]
        if nxt:
            links.append({"rel": "next", "href": nxt})
        return {"links": links, "items": items, "info": None}

    def state(self):
        return C.load_state("saos", Path(self.stan))

    def test_dwie_strony_pusty_wpis_i_kolejka_ponowien(self):
        nxt = "https://www.saos.org.pl/api/dump/judgments?pageNumber=1"
        rc = self.run_main([self.page([item(1), item(2, html="")], nxt), self.page([item(3, "SUPREME")])])
        self.assertEqual(rc, 0)
        self.assertEqual(C.read_doc_ids(Path(self.out)), {"SAOS/1", "SAOS/3"})
        st = self.state()
        self.assertEqual(st["count"], 2)
        self.assertEqual(st["newest_date"], "2026-09-01")
        self.assertIn("2", st["retry"])
        self.assertTrue(st["watermark"])
        self.assertIsNone(st["partial"])
        ch = json.loads((Path(self.stan) / "zmiany_saos.json").read_text(encoding="utf-8"))
        self.assertEqual(ch["added"], ["SAOS/1", "SAOS/3"])
        for line in Path(self.out).read_text(encoding="utf-8").splitlines():
            self.assertEqual(C.validate_chunk(json.loads(line)), [])

    def test_przyrostowo_ponowienie_i_zmiana(self):
        self.run_main([self.page([item(1), item(2, html="")])])
        self.calls.clear()
        # drugi przebieg: wpis 2 dostaje tresc (przez /api/judgments/2), wpis 1 zmieniony
        rc = self.run_main([self.page([item(1, html="<p>Zmieniony tekst " + PL + " " + "x " * 30 + "</p>")])],
                           judgments={"2": item(2)})
        self.assertEqual(rc, 0)
        self.assertEqual(C.read_doc_ids(Path(self.out)), {"SAOS/1", "SAOS/2"})
        self.assertEqual(self.state()["retry"], {})
        ch = json.loads((Path(self.stan) / "zmiany_saos.json").read_text(encoding="utf-8"))
        self.assertEqual((sorted(ch["added"]), ch["changed"]), (["SAOS/2"], ["SAOS/1"]))
        text = Path(self.out).read_text(encoding="utf-8")
        self.assertIn("Zmieniony tekst", text)
        self.assertEqual(text.count('"doc_id":"SAOS/1","eli"') >= 1, True)
        self.assertNotIn("Sąd zważył", "".join(l for l in text.splitlines() if '"SAOS/1"' in l))  # stara tresc zastapiona
        # zapytanie przyrostowe zawiera sinceModificationDate z zapasem wzgledem watermarku
        dump_calls = [u for u in self.calls if "/dump/" in u]
        self.assertTrue(dump_calls and "sinceModificationDate=" in dump_calls[0])

    def test_ponowienie_najwyzej_raz_dziennie(self):
        self.run_main([self.page([item(2, html="")])])
        for _ in range(2):
            self.calls.clear()
            self.run_main([self.page([])], judgments={"2": item(2, html="")})
            n = len([u for u in self.calls if "/api/judgments/" in u])
            if _ == 0:
                self.assertEqual(n, 1)
        self.assertEqual(n, 0)  # drugie uruchomienie tego samego dnia nie pyta ponownie
        self.assertEqual(self.state()["retry"]["2"]["n"], 1)

    def test_limit_i_wznowienie(self):
        nxt = "https://www.saos.org.pl/api/dump/judgments?pageNumber=1"
        rc = self.run_main([self.page([item(1), item(2), item(3)], nxt)], extra=["--limit", "2"])
        self.assertEqual(rc, 0)
        st = self.state()
        self.assertEqual(st["count"], 2)
        self.assertEqual(st["partial"]["next_page"], 0)  # przerwane w polowie strony 0
        self.assertNotIn("watermark", st)
        # wznowienie bez limitu: ta sama strona od poczatku (upsert), potem koniec
        self.calls.clear()
        self.run_main([self.page([item(1), item(2), item(3)])])
        self.assertIn("pageNumber=0", self.calls[0])
        self.assertEqual(C.read_doc_ids(Path(self.out)), {"SAOS/1", "SAOS/2", "SAOS/3"})
        self.assertIsNone(self.state()["partial"])

    def test_max_stron(self):
        nxt = "https://www.saos.org.pl/api/dump/judgments?pageNumber=1"
        self.run_main([self.page([item(1)], nxt)], extra=["--max-stron", "1"])
        st = self.state()
        self.assertEqual(st["partial"]["next_page"], 1)

    def test_przerwa_techniczna_kod_3_bez_utraty_danych(self):
        self.run_main([self.page([item(1)])])
        before = Path(self.out).read_text(encoding="utf-8")
        wm = self.state()["watermark"]
        rc = self.run_main([C.NotExpectedContent("Przerwa techniczna")])
        self.assertEqual(rc, C.EXIT_UNAVAILABLE)
        self.assertEqual(Path(self.out).read_text(encoding="utf-8"), before)
        self.assertEqual(self.state()["watermark"], wm)

    def test_domyslnie_bez_sadow_powszechnych(self):
        it = iter([self.page([item(1, "COMMON"), item(2, "SUPREME")])])

        def fake(url, limiter):
            return next(it)

        with mock.patch.object(S, "get_json", fake):
            S.main(["--force", "--out", self.out, "--stan-dir", self.stan, "--delay", "0"])
        self.assertEqual(C.read_doc_ids(Path(self.out)), {"SAOS/2"})

    def test_uspione_nic_nie_robi(self):
        with mock.patch.object(S, "get_json", side_effect=AssertionError("siec!")):
            self.assertEqual(S.main(["--out", self.out, "--stan-dir", self.stan]), 0)
        self.assertFalse(Path(self.out).exists())

    def test_dry_run_nie_zapisuje(self):
        with mock.patch.object(S, "get_json", side_effect=AssertionError("siec!")):
            self.assertEqual(S.main(["--dry-run", "--out", self.out, "--stan-dir", self.stan]), 0)
        self.assertFalse(Path(self.out).exists())
        self.assertFalse(Path(self.stan).exists())


if __name__ == "__main__":
    unittest.main()
