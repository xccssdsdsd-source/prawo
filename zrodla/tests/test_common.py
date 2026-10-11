"""Testy jednostkowe zrodla/_common.py (bez sieci). Uruchom: python -m unittest discover -s zrodla/tests -v"""
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _common as C  # noqa: E402

PL = "zażółć gęślą jaźń ZAŻÓŁĆ GĘŚLĄ JAŹŃ"


class FakeResp:
    def __init__(self, body: bytes, ctype: str, status: int = 200, url: str = "http://x/"):
        self._b, self.status, self._u = body, status, url
        self.headers = {"Content-Type": ctype}

    def read(self, n=-1):
        return self._b

    def geturl(self):
        return self._u

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def http_error(code, headers=None):
    return urllib.error.HTTPError("http://x/", code, "err", headers or {}, io.BytesIO(b"blad"))


def row(**kw):
    meta = {"doc_id": "T/1", "eli": "T/1", "kategoria": "wyrok", "publisher": "T", "year": 2020, "pos": 1,
            "title": "Tytuł", "display_address": "adres", "announcement_date": "2020-01-02", "status": "orzeczenie",
            "is_consolidated": False, "source_url": "https://example.org/1"}
    r = C.make_row(meta, kw.pop("ord", 1), kw.pop("article", None), kw.pop("heading", "H"), kw.pop("text", "Treść " + PL))
    r.update(kw)
    return r


class TestHtml(unittest.TestCase):
    def test_polskie_znaki_i_nbsp(self):
        t = C.html_to_text("<p>Wyrok&nbsp;S&#261;du&nbsp;&mdash; " + PL + "</p>")
        self.assertIn(PL, t)
        self.assertNotIn(chr(0xA0), t)
        self.assertEqual(t.split("\n")[0].split(" ")[:2], ["Wyrok", "Sądu"])

    def test_blokowe_i_tabele(self):
        h = ("<div><h2>WYROK</h2><p>Akapit 1</p><p>Akapit 2</p>"
             "<table><tr><td><p>a)</p></td><td><p>treść punktu</p></td></tr>"
             "<tr><td>b)</td><td>drugi</td></tr></table><script>x()</script></div>")
        self.assertEqual(C.html_to_lines(h), ["WYROK", "Akapit 1", "Akapit 2", "a) treść punktu", "b) drugi"])

    def test_przypisy_i_head(self):
        h = ('<html><head><title>Tytuł strony</title></head><body><p>Tekst <a href="#ntr1-L_1">(<span>1</span>)</a> dalej</p></body></html>')
        self.assertEqual(C.html_to_lines(h), ["Tekst dalej"])

    def test_blocks_klasy(self):
        b = C.html_blocks('<p class="oj-ti-art">Artykuł 1</p><p class="oj-normal">Tekst</p>')
        self.assertEqual(b, [("oj-ti-art", "Artykuł 1"), ("oj-normal", "Tekst")])

    def test_clean_text_usuwa_fffd(self):
        s, n = C.clean_text("a" + chr(0xFFFD) + "b\x00c" + chr(0xFFFD))
        self.assertEqual((s, n), ("abc", 2))

    def test_clean_text_nfc(self):
        s, _ = C.clean_text("a" + chr(0x0328))  # a + combining ogonek -> ą
        self.assertEqual(s, chr(0x105))

    def test_decode_body(self):
        raw = PL.encode("utf-8")
        self.assertEqual(C.decode_body(raw, "text/html; charset=UTF-8")[0], PL)
        self.assertEqual(C.decode_body(PL.encode("cp1250"), "text/html")[0], PL)  # fallback


class TestSplit(unittest.TestCase):
    def test_limit_i_bez_utraty(self):
        para = " ".join(f"Zdanie numer {i} o żółtej gęsi." for i in range(400))
        text = para + "\n" + "Krótki akapit.\n" + "x" * 5000
        parts = C.split_text(text, 2000)
        self.assertTrue(all(len(p) <= 2000 for p in parts), [len(p) for p in parts])
        self.assertEqual("".join(text.split()).replace("x", ""), "".join("".join(parts).split()).replace("x", ""))
        self.assertEqual(sum(p.count("x") for p in parts), 5000)

    def test_krotki_tekst_jeden_fragment(self):
        self.assertEqual(C.split_text("a\nb", 2000), ["a\nb"])

    def test_pusty(self):
        self.assertEqual(C.split_text("  \n ", 2000), [])


class TestSchema(unittest.TestCase):
    def test_poprawny(self):
        self.assertEqual(C.validate_chunk(row()), [])
        self.assertEqual(list(row().keys()), C.CHUNK_KEYS)

    def test_bledy(self):
        self.assertTrue(C.validate_chunk(row(kategoria="zla")))
        self.assertTrue(C.validate_chunk(row(text="")))
        self.assertTrue(C.validate_chunk(row(text="x" * 6001)))
        self.assertTrue(C.validate_chunk(row(text="a" + chr(0xFFFD))))
        self.assertTrue(C.validate_chunk(row(announcement_date="02.01.2020")))
        self.assertTrue(C.validate_chunk(row(ord=0)))
        self.assertTrue(C.validate_chunk(row(article=5)))
        self.assertTrue(C.validate_chunk(row(source_url="ftp://x")))
        self.assertTrue(C.validate_chunk(row(is_consolidated="nie")))
        bad = dict(row())
        del bad["heading"]
        self.assertTrue(C.validate_chunk(bad))

    def test_doc_id_pierwszy_klucz(self):
        r = row()
        shuffled = {k: r[k] for k in reversed(list(r))}
        self.assertTrue(any("doc_id" in e for e in C.validate_chunk(shuffled)))

    def test_validate_rows(self):
        self.assertEqual(C.validate_rows([row(ord=1), row(ord=2)]), [])
        self.assertTrue(C.validate_rows([row(ord=1), row(ord=3)]))
        self.assertTrue(C.validate_rows([row(ord=1), row(ord=2, doc_id="T/2")]))
        self.assertTrue(C.validate_rows([]))

    def test_dumps_zachowuje_polskie_znaki_i_doc_id_pierwszy(self):
        line = C.dumps_row(row())
        self.assertTrue(line.startswith('{"doc_id":"T/1"'))
        self.assertIn(PL, line)
        self.assertNotIn("\\u", line)
        self.assertEqual(C.line_doc_id(line.encode()), "T/1")


class TestHttp(unittest.TestCase):
    def setUp(self):
        self.sleeps = []
        p1 = mock.patch.object(C, "sleep", lambda s: self.sleeps.append(s))
        p1.start()
        self.addCleanup(p1.stop)

    def patch_urlopen(self, seq):
        it = iter(seq)

        def fake(req, timeout=None):
            x = next(it)
            if isinstance(x, Exception):
                raise x
            return x

        p = mock.patch.object(C, "urlopen", fake)
        p.start()
        self.addCleanup(p.stop)

    def test_retry_5xx_potem_ok(self):
        self.patch_urlopen([http_error(503), FakeResp(b'{"a":1}', "application/json;charset=UTF-8")])
        r = C.http_get("http://x/", expect="json", backoff=2)
        self.assertEqual(r.json(), {"a": 1})
        self.assertEqual(self.sleeps, [2.0])

    def test_html_zamiast_json_to_przerwa(self):
        html = FakeResp(b"<html><title>Przerwa techniczna</title>", "text/html")
        self.patch_urlopen([html, html, html])
        with self.assertRaises(C.NotExpectedContent):
            C.http_get("http://x/", expect="json", retries=2, backoff=1)
        self.assertEqual(len(self.sleeps), 2)

    def test_404_bez_ponowien(self):
        self.patch_urlopen([http_error(404)])
        with self.assertRaises(C.HttpStatus) as cm:
            C.http_get("http://x/", retries=3)
        self.assertEqual(cm.exception.status, 404)
        self.assertEqual(self.sleeps, [])

    def test_siec_wyczerpane(self):
        self.patch_urlopen([urllib.error.URLError("boom")] * 3)
        with self.assertRaises(C.FetchError):
            C.http_get("http://x/", retries=2, backoff=1)
        self.assertEqual(self.sleeps, [1.0, 2.0])

    def test_retry_after(self):
        self.patch_urlopen([http_error(429, {"Retry-After": "30"}), FakeResp(b"ok", "text/plain")])
        C.http_get("http://x/", backoff=1)
        self.assertEqual(self.sleeps, [30.0])

    def test_pdf_po_magic(self):
        self.patch_urlopen([FakeResp(b"%PDF-1.7 ...", "application/octet-stream")])
        self.assertEqual(C.http_get("http://x/", expect="pdf").body[:4], b"%PDF")

    def test_rate_limiter(self):
        t = [100.0]
        with mock.patch.object(C, "monotonic", lambda: t[0]):
            rl = C.RateLimiter(2.0)
            rl.wait()
            t[0] += 0.5
            rl.wait()
        self.assertEqual(self.sleeps, [1.5])


class TestFiles(unittest.TestCase):
    def test_merge_zastepuje_dokument_i_dopisuje(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "o.jsonl"
            C.merge_into_jsonl(out, {"T/1": [row(ord=1), row(ord=2)], "T/2": [row(doc_id="T/2", ord=1)]})
            self.assertEqual(C.read_doc_ids(out), {"T/1", "T/2"})
            C.merge_into_jsonl(out, {"T/1": [row(ord=1, text="nowy " + PL)]})
            lines = out.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertIn("nowy " + PL, lines[1])
            self.assertEqual([p.name for p in Path(d).iterdir()], ["o.jsonl"])  # brak plikow tymczasowych

    def test_part_writer_recover(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "o.jsonl"
            w = C.PartWriter(out)
            w.add([row(ord=1), row(ord=2)])
            w.add([row(ord=1, text="druga wersja"), ])  # ten sam doc_id ponownie -> wygrywa ostatni
            w._f.close()
            with open(w.part, "ab") as f:
                f.write(b'{"doc_id":"T/9","ord":1,"tex')  # ucieta linia po przerwaniu
            w2 = C.PartWriter(out)
            self.assertEqual(w2.recover(), 1)
            rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["text"], "druga wersja")
            self.assertFalse(w.part.exists())

    def test_stan_i_zmiany(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(C.load_state("x", Path(d)), {})
            C.save_state("x", {"count": 3, "opis": PL}, Path(d))
            self.assertEqual(C.load_state("x", Path(d))["opis"], PL)
            p = C.write_changes("x", ["B", "A"], ["C"], Path(d))
            data = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual((data["added"], data["changed"], data["removed"]), (["A", "B"], ["C"], []))
            (Path(d) / "zrodlo_bad.json").write_text("{zepsuty", encoding="utf-8")
            self.assertEqual(C.load_state("bad", Path(d)), {})


class TestLaczenieZmian(unittest.TestCase):
    def test_laczenie(self):
        import laczenie_zmian as L
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "zmiany.json").write_text(json.dumps({"added": ["DU/1/1"], "changed": ["DU/2/2#U"], "removed": ["DU/3/3"]}), encoding="utf-8")
            (d / "zmiany_saos.json").write_text(json.dumps({"added": ["SAOS/1", "DU/1/1"], "changed": ["SAOS/2"], "removed": []}), encoding="utf-8")
            (d / "zmiany_eurlex.json").write_text(json.dumps({"added": [], "changed": ["DU/3/3"], "removed": []}), encoding="utf-8")
            r = L.merge([d / "zmiany.json", d / "zmiany_saos.json", d / "zmiany_eurlex.json", d / "brak.json"])
            self.assertEqual(r["added"], ["DU/1/1", "SAOS/1"])
            self.assertEqual(sorted(r["changed"]), ["DU/2/2#U", "DU/3/3", "SAOS/2"])
            self.assertEqual(r["removed"], [])
            self.assertEqual(r["zrodla"], ["zmiany.json", "zmiany_saos.json", "zmiany_eurlex.json"])
            out = d / "razem.json"
            self.assertEqual(L.main(["--out", str(out), str(d / "zmiany.json")]), 0)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["removed"], ["DU/3/3"])


class TestRejestr(unittest.TestCase):
    def test_sources_json_zgodny_z_kontraktem(self):
        src = C.load_sources()
        by = {s["id"]: s for s in src}
        for k in ("eli-du", "eli-mp", "isap-ujednolicone", "saos", "eurlex"):
            self.assertIn(k, by)
        need = {"id", "nazwa", "opis", "enabled", "kategoria", "skrypt", "wyjscie", "zakres", "licencja", "status"}
        for s in src:
            self.assertTrue(need <= set(s), (s["id"], need - set(s)))
            self.assertIn(s["status"], ("aktywne", "uśpione", "planowane"))
            self.assertIsInstance(s["enabled"], bool)
        for k in ("eli-du", "eli-mp", "isap-ujednolicone"):
            self.assertTrue(by[k]["enabled"] and by[k]["skrypt"] is None and by[k]["status"] == "aktywne")
        for k in ("saos", "eurlex"):
            self.assertFalse(by[k]["enabled"])
            self.assertEqual(by[k]["status"], "uśpione")
            self.assertTrue((C.ROOT / by[k]["skrypt"]).is_file())


if __name__ == "__main__":
    unittest.main()
