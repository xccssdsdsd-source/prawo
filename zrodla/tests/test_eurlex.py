"""Testy fetchera EUR-Lex (Cellar) z mockiem i syntetycznymi dokumentami (bez sieci)."""
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

spec = importlib.util.spec_from_file_location("eurlex_fetch", ZR / "eurlex" / "fetch.py")
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)

ZD = "Państwa członkowskie zapewniają, że przetwarzanie danych osobowych odbywa się zgodnie z prawem. "


def oj_xhtml(extra_art="", footnotes=True):
    long_art = "".join(f'<p class="oj-normal">{i}. {ZD * 8}</p>' for i in range(1, 9))  # > 5500 znakow
    return f"""<?xml version="1.0" encoding="UTF-8"?><html xmlns="http://www.w3.org/1999/xhtml"><head><title>L_2016119PL.01000101.xml</title></head><body>
<table><tbody><tr><td><p class="oj-hd-date">4.5.2016&#160;&#160;</p></td><td><p class="oj-hd-lg">PL</p></td>
<td><p class="oj-hd-ti">Dziennik Urzędowy Unii Europejskiej</p></td><td><p class="oj-hd-oj">L 119/1</p></td></tr></tbody></table>
<div class="eli-container"><div class="eli-main-title">
<p class="oj-doc-ti">ROZPORZĄDZENIE PARLAMENTU EUROPEJSKIEGO I RADY (UE) 2016/679</p>
<p class="oj-doc-ti">z dnia 27 kwietnia 2016 r.</p>
<p class="oj-doc-ti">w sprawie ochrony osób fizycznych (ogólne rozporządzenie testowe)</p>
<p class="oj-doc-ti">(Tekst mający znaczenie dla EOG)</p></div>
<div><p class="oj-normal">PARLAMENT EUROPEJSKI I RADA UNII EUROPEJSKIEJ,</p>
<p class="oj-normal">uwzględniając opinię Komitetu <a href="#ntr1-L_2016119PL.01000101-E0001"><span class="oj-super oj-note-tag">1</span></a>,</p>
<table><tr><td><p>(1)</p></td><td><p>Ochrona osób fizycznych jest prawem podstawowym. {ZD}</p></td></tr></table>
<p class="oj-ti-section-1">ROZDZIAŁ I</p><p class="oj-ti-section-2">Przepisy ogólne</p>
<p class="oj-ti-art">Artykuł 1</p><p class="oj-sti-art">Przedmiot i cele</p>
<p class="oj-normal">1. Niniejsze rozporządzenie ustanawia przepisy. {ZD}</p>
<table><tr><td><p>a)</p></td><td><p>pierwszy punkt;</p></td></tr><tr><td><p>b)</p></td><td><p>drugi punkt.</p></td></tr></table>
<p class="oj-ti-art">Artykuł 2</p><p class="oj-sti-art">Długi artykuł</p>{long_art}
<p class="oj-ti-section-1">ROZDZIAŁ II</p><p class="oj-ti-section-2">Zasady</p>
<p class="oj-ti-art">Artykuł 3a</p><p class="oj-sti-art">Zasada</p><p class="oj-normal">Dane muszą być przetwarzane zgodnie z prawem.</p>{extra_art}
<p class="oj-normal">Sporządzono w Brukseli dnia 27 kwietnia 2016 r.</p>
<p class="oj-doc-ti">ZAŁĄCZNIK I</p><p class="oj-doc-ti">Wykaz</p>
<p class="oj-normal">Artykuł 9</p><p class="oj-normal">Tekst załącznika, który wspomina Artykuł 9. {ZD}</p></div></div>
{'<p class="oj-note">(1) Dz.U. C 229 z 31.7.2012, s. 90.</p>' if footnotes else ''}
</body></html>"""


def old_html():
    return ("<html><head><title>x</title></head><body><div id='banner'><p>Ważna informacja prawna</p></div><h1>32002L0058</h1>"
            "<p><strong>Dyrektywa 2002/58/WE parlamentu europejskiego i rady z dnia 12 lipca 2002 r. dotycząca przetwarzania "
            "danych osobowych (dyrektywa o prywatności)</strong><br><em><br>Dziennik Urzędowy L 201 , 31/07/2002 P. 0037 - 0047<br></em></p>"
            "<div id='TexteOnly'><p>Dyrektywa 2002/58/WE parlamentu europejskiego i rady</p><p>z dnia 12 lipca 2002 r.</p>"
            "<p>PARLAMENT EUROPEJSKI I RADA UNII EUROPEJSKIEJ,</p><p>(1) Dyrektywa wymaga zapewnienia ochrony. " + ZD + "</p>"
            "<p>Artykuł 1</p><p>Zakres i cel</p><p>1. Niniejsza dyrektywa harmonizuje przepisy. " + ZD + "</p>"
            "<p>Artykuł 2</p><p>Definicje</p><p>Stosuje się następujące definicje. " + ZD + "</p>"
            "<p>Sporządzono w Brukseli, dnia 12 lipca 2002 r.</p></div>"
            "<p>--------------------------------------------------</p><p>[1] Dz.U. C 365 E z 19.12.2000, str. 223.</p></body></html>")


class TestPure(unittest.TestCase):
    def test_celex(self):
        self.assertEqual(E.parse_celex("32016R0679")["numer"], 679)
        self.assertTrue(E.parse_celex("02016R0679-20160504")["ujednolicony"])
        self.assertEqual(E.parse_celex("12012E101")["rok"], 2012)
        for bad in ("", "abc", "3201R0679", "32016R"):
            self.assertIsNone(E.parse_celex(bad))

    def test_fix_title(self):
        self.assertEqual(E.fix_title("ROZPORZĄDZENIE PARLAMENTU EUROPEJSKIEGO I RADY (UE) 2016/679 z dnia 27 kwietnia 2016 r. w sprawie ochrony"),
                         "Rozporządzenie Parlamentu Europejskiego i Rady (UE) 2016/679 z dnia 27 kwietnia 2016 r. w sprawie ochrony")
        self.assertEqual(E.fix_title("Dyrektywa 2002/58/WE parlamentu europejskiego i rady z dnia 12 lipca 2002 r."),
                         "Dyrektywa 2002/58/WE Parlamentu Europejskiego i Rady z dnia 12 lipca 2002 r.")
        self.assertEqual(E.fix_title("DYREKTYWA RADY 93/13/EWG z dnia 5 kwietnia 1993 r. w sprawie nieuczciwych warunków"),
                         "Dyrektywa Rady 93/13/EWG z dnia 5 kwietnia 1993 r. w sprawie nieuczciwych warunków")

    def test_data_aktu(self):
        self.assertEqual(E.parse_act_date("z dnia 27 kwietnia 2016 r."), "2016-04-27")
        self.assertEqual(E.parse_act_date("z dnia 5 września 1993 r."), "1993-09-05")
        self.assertIsNone(E.parse_act_date("bez daty"))

    def test_polskosc(self):
        self.assertTrue(E.looks_polish(ZD * 10))
        self.assertFalse(E.looks_polish("The quick brown fox jumps over the lazy dog. " * 20))

    def test_seed_44_poprawne_unikalne(self):
        seed = E.load_seed(E.HERE / "seed.json")
        self.assertEqual(len(seed), 44)
        self.assertEqual(len({a["celex"] for a in seed}), 44)
        self.assertTrue(all(E.parse_celex(a["celex"]) and a.get("nazwa") for a in seed))
        raw = (E.HERE / "seed.json").read_text(encoding="utf-8")
        self.assertNotIn(chr(0xFFFD), raw)
        for c in ("32016R0679", "32024R1689", "12012E101", "32001R0044"):
            self.assertIn(c, {a["celex"] for a in seed})


class TestBuild(unittest.TestCase):
    def build(self, html, celex="32016R0679", seed=None, fmt="xhtml"):
        blocks, bad = E.to_blocks(fmt, html.encode("utf-8"))
        return E.build_rows(celex, seed or {"nazwa": "RODO testowe"}, blocks, bad)

    def test_oj_xhtml(self):
        rows, info = self.build(oj_xhtml())
        self.assertEqual(C.validate_rows(rows), [])
        r0 = rows[0]
        self.assertEqual((r0["doc_id"], r0["kategoria"], r0["publisher"], r0["year"], r0["pos"]), ("CELEX/32016R0679", "ue", "UE", 2016, 679))
        self.assertEqual(r0["title"], "Rozporządzenie Parlamentu Europejskiego i Rady (UE) 2016/679 z dnia 27 kwietnia 2016 r. "
                                      "w sprawie ochrony osób fizycznych (ogólne rozporządzenie testowe)")
        self.assertEqual(r0["announcement_date"], "2016-04-27")
        self.assertEqual(r0["display_address"], "Dz.Urz. UE L 119 z 4.5.2016, s. 1 (CELEX 32016R0679)")
        self.assertEqual(r0["source_url"], "https://eur-lex.europa.eu/legal-content/PL/TXT/?uri=CELEX:32016R0679")
        self.assertFalse(r0["is_consolidated"])
        self.assertIn("Nazwa skrócona: RODO testowe", r0["text"])
        self.assertEqual(r0["heading"], "Informacje o akcie")
        arts = [r["article"] for r in rows if r["article"]]
        self.assertEqual(sorted(set(arts)), ["1", "2", "3a"])
        a1 = next(r for r in rows if r["article"] == "1")
        self.assertEqual(a1["heading"], "ROZDZIAŁ I Przepisy ogólne")
        self.assertTrue(a1["text"].startswith("Artykuł 1\nPrzedmiot i cele\n1. Niniejsze"))
        self.assertIn("\na) pierwszy punkt;\nb) drugi punkt.", a1["text"])
        a3 = next(r for r in rows if r["article"] == "3a")
        self.assertEqual(a3["heading"], "ROZDZIAŁ II Zasady")
        # preambula: bez przypisu "1", motyw z tabeli w jednej linii
        pre = next(r for r in rows if r["heading"] == "Preambuła")
        self.assertIn("(1) Ochrona osób fizycznych jest prawem podstawowym.", pre["text"])
        self.assertNotIn("uwzględniając opinię Komitetu 1", pre["text"])
        self.assertIn("uwzględniając opinię Komitetu ,", pre["text"])
        # przypis dolny usuniety
        self.assertNotIn("Dz.U. C 229", "\n".join(r["text"] for r in rows))
        self.assertEqual(info["articles"], 3)

    def test_dlugi_artykul_dzielony(self):
        rows, _ = self.build(oj_xhtml())
        a2 = [r for r in rows if r["article"] == "2"]
        self.assertGreater(len(a2), 1)
        self.assertTrue(all(len(r["text"]) <= 6000 for r in a2))
        self.assertTrue(a2[1]["text"].startswith("Artykuł 2 (ciąg dalszy)"))

    def test_zalacznik_nie_wykrywa_artykulow(self):
        rows, _ = self.build(oj_xhtml())
        ann = [r for r in rows if r["heading"].startswith("ZAŁĄCZNIK I")]
        self.assertTrue(ann)
        self.assertEqual(ann[0]["heading"], "ZAŁĄCZNIK I Wykaz")
        self.assertIsNone(ann[0]["article"])
        self.assertIn("Artykuł 9", ann[0]["text"])
        self.assertEqual(sorted({r["article"] for r in rows if r["article"]}), ["1", "2", "3a"])

    def test_stary_html(self):
        rows, info = self.build(old_html(), "32002L0058", {"nazwa": "e-Privacy"}, fmt="html")
        self.assertEqual(C.validate_rows(rows), [])
        r0 = rows[0]
        self.assertEqual(r0["title"], "Dyrektywa 2002/58/WE Parlamentu Europejskiego i Rady z dnia 12 lipca 2002 r. "
                                      "dotycząca przetwarzania danych osobowych (dyrektywa o prywatności)")
        self.assertEqual(r0["display_address"], "Dz.Urz. UE L 201 z 31.7.2002, s. 37 (CELEX 32002L0058)")
        self.assertEqual(sorted({r["article"] for r in rows if r["article"]}), ["1", "2"])
        self.assertNotIn("str. 223", "\n".join(r["text"] for r in rows))  # przypisy za linia ----

    def test_ujednolicony_i_traktat(self):
        rows, _ = self.build(oj_xhtml(), "02016R0679-20160504")
        self.assertTrue(rows[0]["is_consolidated"])
        self.assertEqual(rows[0]["status"], "tekst ujednolicony UE (dokumentacyjny)")
        rows, _ = self.build(oj_xhtml(), "12012E101", {"tytul": "TFUE art. 101"})
        self.assertEqual(rows[0]["title"], "TFUE art. 101")
        self.assertIn("traktat", rows[0]["status"])

    def test_odrzuca_nie_polski_i_za_krotki(self):
        en = "<html><body><p>REGULATION OF THE EUROPEAN PARLIAMENT</p><p>Article 1</p>" + "<p>" + "The quick brown fox. " * 60 + "</p></body></html>"
        with self.assertRaises(ValueError):
            self.build(en, "32016R0679", fmt="html")
        with self.assertRaises(ValueError):
            self.build("<html><body><p>Artykuł 1</p><p>Krótki żółw.</p></body></html>", fmt="html")

    def test_brak_artykulow_fragmenty(self):
        html = "<html><body><p class='doc-ti'>DECYZJA TESTOWA</p>" + "".join(f"<p>Akapit {i}. {ZD * 6}</p>" for i in range(12)) + "</body></html>"
        rows, info = self.build(html, "32010D0001", fmt="html")
        self.assertEqual(info["articles"], 0)
        self.assertTrue(all(r["article"] is None and len(r["text"]) <= 2000 for r in rows))
        self.assertGreater(len(rows), 3)


class TestMain(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        d = Path(self.tmp.name)
        self.out, self.stan = str(d / "chunks_eurlex.jsonl"), str(d / "stan")
        self.seed = d / "seed.json"
        self.seed.write_text(json.dumps({"akty": [
            {"celex": "32016R0679", "nazwa": "RODO", "format": "xhtml"},
            {"celex": "32002L0058", "nazwa": "e-Privacy", "format": "html"},
            {"celex": "32099R9999", "nazwa": "nie istnieje", "format": "xhtml"}]}, ensure_ascii=False), encoding="utf-8")
        p = mock.patch.object(C, "sleep", lambda s: None)
        p.start()
        self.addCleanup(p.stop)
        self.requests = []

    def fake_get(self, url, **kw):
        acc = kw["headers"]["Accept"]
        self.requests.append((url.rsplit("/", 1)[-1], acc))
        if url.endswith("32099R9999"):
            raise C.HttpStatus(404, url, b"cellar identifier ... does not hold a content datastream")
        if url.endswith("32016R0679"):
            if acc == "application/xhtml+xml":
                return C.Response(200, {"content-type": "application/xhtml+xml;charset=UTF-8"}, oj_xhtml().encode("utf-8"), url)
        if url.endswith("32002L0058"):
            if acc == "application/xhtml+xml":
                raise C.HttpStatus(404, url, b"no xhtml")
            if acc == "text/html":
                return C.Response(200, {"content-type": "text/html;charset=UTF-8"}, old_html().encode("utf-8"), url)
        raise C.HttpStatus(404, url, b"x")

    def run_main(self, *extra, getter=None):
        with mock.patch.object(C, "http_get", getter or self.fake_get):
            return E.main(["--force", "--seed", str(self.seed), "--out", self.out, "--stan-dir", self.stan,
                           "--delay", "0", *extra])

    def test_pelny_przebieg_fallback_i_blad_jednego_aktu(self):
        rc = self.run_main()
        self.assertEqual(rc, C.EXIT_ERROR)  # jeden akt bez tresci
        self.assertEqual(C.read_doc_ids(Path(self.out)), {"CELEX/32016R0679", "CELEX/32002L0058"})
        # fallback: e-Privacy probowane od 'html' (podpowiedz seed), 32099 probowane we wszystkich 3 formatach
        reqs = [a for c, a in self.requests if c == "32099R9999"]
        self.assertEqual(reqs, ["application/xhtml+xml", "text/html", "application/pdf"])
        st = C.load_state("eurlex", Path(self.stan))
        self.assertEqual(st["count"], 2)
        self.assertEqual(st["newest_date"], "2016-04-27")
        self.assertIn("32099R9999", st["errors"])
        self.assertEqual(st["docs"]["32002L0058"]["format"], "html")
        ch = json.loads((Path(self.stan) / "zmiany_eurlex.json").read_text(encoding="utf-8"))
        self.assertEqual(ch["added"], ["CELEX/32002L0058", "CELEX/32016R0679"])
        for line in Path(self.out).read_text(encoding="utf-8").splitlines():
            self.assertEqual(C.validate_chunk(json.loads(line)), [])
        self.assertNotIn(chr(0xFFFD), Path(self.out).read_text(encoding="utf-8"))

    def test_przyrostowo_swieze_pomijane_odswiez_bez_zmian(self):
        self.run_main()
        self.requests.clear()
        self.run_main()
        self.assertEqual({c for c, _ in self.requests}, {"32099R9999"})  # tylko niepobrany akt
        self.requests.clear()
        self.run_main("--odswiez")
        ch = json.loads((Path(self.stan) / "zmiany_eurlex.json").read_text(encoding="utf-8"))
        self.assertEqual((ch["added"], ch["changed"]), ([], []))  # ta sama tresc -> bez zmian
        self.assertEqual(len(C.read_doc_ids(Path(self.out))), 2)

    def test_zmiana_tresci_to_changed(self):
        self.run_main("--tylko-celex", "--celex", "32016R0679")
        self.assertEqual(C.load_state("eurlex", Path(self.stan))["count"], 1)

        def changed(url, **kw):
            body = oj_xhtml(extra_art='<p class="oj-ti-art">Artykuł 4</p><p class="oj-normal">Nowy przepis zażółć.</p>')
            return C.Response(200, {"content-type": "application/xhtml+xml"}, body.encode("utf-8"), url)

        self.run_main("--tylko-celex", "--celex", "32016R0679", getter=changed)
        ch = json.loads((Path(self.stan) / "zmiany_eurlex.json").read_text(encoding="utf-8"))
        self.assertEqual(ch["changed"], ["CELEX/32016R0679"])
        text = Path(self.out).read_text(encoding="utf-8")
        self.assertEqual(text.count('"ord":1,'), 1)  # stary dokument zastapiony, nie zdublowany
        self.assertIn("Nowy przepis", text)

    def test_limit(self):
        self.run_main("--limit", "1")
        self.assertEqual(C.read_doc_ids(Path(self.out)), {"CELEX/32016R0679"})

    def test_503_przerywa_przebieg_kodem_3(self):
        def down(url, **kw):
            raise C.NotExpectedContent("html zamiast xhtml")

        self.assertEqual(self.run_main(getter=down), C.EXIT_UNAVAILABLE)
        self.assertFalse(Path(self.out).exists())

    def test_odkryj(self):
        sparql = {"results": {"bindings": [
            {"celex": {"value": "32026R2262"}, "date": {"value": "2026-10-09"}},
            {"celex": {"value": "32026R2263"}, "date": {"value": "2026-10-08"}}]}}

        def g(url, **kw):
            self.assertIn("sparql", url)
            self.assertEqual(kw["headers"]["Accept"], "application/sparql-results+json")
            return C.Response(200, {"content-type": "application/sparql-results+json"}, json.dumps(sparql).encode(), url)

        rc = self.run_main("--odkryj", "--since", "2026-10-01", getter=g)
        self.assertEqual(rc, 0)
        data = json.loads((Path(self.stan) / "zrodlo_eurlex_kandydaci.json").read_text(encoding="utf-8"))
        self.assertEqual([a["celex"] for a in data["akty"]], ["32026R2262", "32026R2263"])
        self.assertFalse(Path(self.out).exists())

    def test_uspione_i_dry_run(self):
        with mock.patch.object(C, "http_get", side_effect=AssertionError("siec!")):
            self.assertEqual(E.main(["--seed", str(self.seed), "--out", self.out, "--stan-dir", self.stan]), 0)
            self.assertEqual(E.main(["--dry-run", "--seed", str(self.seed), "--out", self.out, "--stan-dir", self.stan]), 0)
        self.assertFalse(Path(self.out).exists())
        self.assertFalse(Path(self.stan).exists())


if __name__ == "__main__":
    unittest.main()
