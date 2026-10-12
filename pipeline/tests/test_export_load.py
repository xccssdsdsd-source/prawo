#!/usr/bin/env python3
"""Testy trybow przyrostowych: export_chunks.py --changed i load_to_postgres.py --sync.

Uruchomienie (bez pytest, tylko biblioteka standardowa):
    python -m unittest discover -s pipeline/tests -v
Testy integracyjne z baza uruchamiaja sie tylko, gdy ustawiono PRAWO_TEST_DATABASE_URL
(wskaz PUSTA, jednorazowa baze - testy robia TRUNCATE tabel documents/chunks), np.:
    docker run -d --rm --name prawo-pg -e POSTGRES_PASSWORD=x -e POSTGRES_DB=t -p 127.0.0.1:55432:5432 postgres:16
    set PRAWO_TEST_DATABASE_URL=postgresql://postgres:x@127.0.0.1:55432/t
Wszystkie pliki robocze powstaja w katalogach tymczasowych - pipeline/out/ i dane/ nie sa dotykane.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PIPE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPE))

import export_chunks as ex  # noqa: E402
import load_to_postgres as ld  # noqa: E402

EXPORT = PIPE / "export_chunks.py"
LOAD = PIPE / "load_to_postgres.py"
DB_URL = os.environ.get("PRAWO_TEST_DATABASE_URL")


def run(script, args, env_extra=None, drop_env=()):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    for k in drop_env:
        env.pop(k, None)
    env.update(env_extra or {})
    p = subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, env=env,
                       encoding="utf-8", errors="replace", timeout=300)
    return p.returncode, p.stdout, p.stderr


def read_jsonl(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def write_jsonl(path, rows):
    Path(path).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


# ----------------------------------------------------------------- dane testowe

def html_doc(*arts):
    body = "".join(f"<p>Art. {n}. {t}</p>" for n, t in arts)
    return f"<html><head><title>x</title></head><body><div>{body}</div></body></html>".encode("utf-8")


LONG = ("Sprawca jest zobowiązany do naprawienia szkody oraz do zapłaty zadośćuczynienia za doznaną krzywdę "
        "w terminie wskazanym przez właściwy sąd, a w razie zwłoki do zapłaty odsetek ustawowych. ")


def make_pdf(path, lines):
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    y = 72
    for l in lines:
        page.insert_text((50, y), l)
        y += 14
    doc.save(str(path))
    doc.close()


def rec(pub, year, pos, title, kat):
    return {"ELI": f"{pub}/{year}/{pos}", "publisher": pub, "year": year, "pos": pos, "title": title,
            "displayAddress": f"{'Dz.U.' if pub == 'DU' else 'M.P.'} {year} poz. {pos}",
            "announcementDate": f"{year}-01-02", "status": "obowiązujący", "kategoria": kat}


class ExportFixture(unittest.TestCase):
    """Maly katalog dane/ + out/ w tmp. Kazdy test dostaje swiezy."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="prawo_a2_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.dane = self.tmp / "dane"
        self.out_dir = self.tmp / "out"
        self.out = self.out_dir / "chunks.jsonl"
        for d in ("podstawowe", "mp", "ujednolicone", "_wycofane"):
            (self.dane / d).mkdir(parents=True)
        du = [rec("DU", 2020, p, f"Ustawa testowa {p}", "podstawowe") for p in (1, 2, 3, 4, 6, 7)]
        (self.dane / "indeks_obowiazujacych.json").write_text(json.dumps(du, ensure_ascii=False), encoding="utf-8")
        (self.dane / "indeks_mp.json").write_text(json.dumps([rec("MP", 2026, 5, "Uchwała testowa", "mp")], ensure_ascii=False), encoding="utf-8")
        (self.dane / "indeks_ujednolicone.json").write_text(json.dumps([rec("DU", 2020, 1, "Ustawa testowa 1 (tekst jednolity)", "ujednolicone")], ensure_ascii=False), encoding="utf-8")
        (self.dane / "podstawowe" / "DU_2020_1.html").write_bytes(html_doc((1, LONG + "STARA TRESC."), (2, LONG)))
        (self.dane / "podstawowe" / "DU_2020_2.html").write_bytes(html_doc((1, LONG), (2, LONG), (3, LONG)))
        (self.dane / "podstawowe" / "DU_2020_3.html").write_bytes(html_doc((1, LONG)))
        (self.dane / "podstawowe" / "DU_2020_4.html").write_bytes(html_doc((1, "Krotki.")))  # za malo tekstu
        (self.dane / "mp" / "MP_2026_5.html").write_bytes(html_doc((1, LONG)))
        make_pdf(self.dane / "ujednolicone" / "U-DU_2020_1.pdf",
                 ["Art. 1. Tekst jednolity ustawy testowej pierwszej, wystarczajaco dlugi aby przejsc prog.",
                  "Art. 2. Kolejny artykul tekstu jednolitego zawiera dodatkowe slowa potrzebne do progu.",
                  "Art. 3. Trzeci artykul tekstu jednolitego takze zawiera sporo zwyklych slow w zdaniu."])
        # plik w _wycofane nie moze byc eksportowany
        (self.dane / "_wycofane" / "podstawowe").mkdir()
        (self.dane / "_wycofane" / "podstawowe" / "DU_2020_7.html").write_bytes(html_doc((1, LONG)))

    def export(self, *extra):
        return run(EXPORT, ["--dane", self.dane, "--out", self.out, "--workers", 2, *extra])

    def changes(self, added=(), changed=(), removed=()):
        p = self.tmp / "zmiany.json"
        p.write_text(json.dumps({"run_at": "2026-10-11T10:00:00", "added": list(added), "changed": list(changed),
                                 "removed": list(removed), "unchanged": 1, "latest": {}}), encoding="utf-8")
        return p

    def ids(self):
        return {r["doc_id"] for r in read_jsonl(self.out)}

    def lines_of(self, doc_ids):
        return [l for l in self.out.read_text(encoding="utf-8").splitlines() if json.loads(l)["doc_id"] in doc_ids]


class TestExportChanged(ExportFixture):
    def test_full_export_baseline_skips_wycofane(self):
        code, so, se = self.export()
        self.assertEqual(code, 0, se)
        self.assertEqual(self.ids(), {"DU/2020/1", "DU/2020/2", "DU/2020/3", "MP/2026/5", "DU/2020/1#U"})
        kats = {r["doc_id"]: r["kategoria"] for r in read_jsonl(self.out)}
        self.assertEqual(kats["DU/2020/1#U"], "ujednolicone")
        self.assertEqual(kats["MP/2026/5"], "mp")
        self.assertIn("DU/2020/4", (self.out_dir / "bez_tekstu.txt").read_text(encoding="utf-8"))
        self.assertTrue((self.out_dir / "raport.txt").exists())  # raport obok --out, nie w pipeline/out

    def test_changed_added_changed_removed(self):
        self.assertEqual(self.export()[0], 0)
        keep_before = self.lines_of({"DU/2020/2", "MP/2026/5", "DU/2020/1#U"})
        # zmiana tresci, nowy dokument, usuniecie (plik przeniesiony), dodany bez pliku
        (self.dane / "podstawowe" / "DU_2020_1.html").write_bytes(html_doc((1, LONG + "NOWA TRESC."), (2, LONG), (3, LONG)))
        shutil.move(str(self.dane / "podstawowe" / "DU_2020_3.html"), str(self.dane / "_wycofane" / "podstawowe" / "DU_2020_3.html"))
        (self.dane / "podstawowe" / "DU_2020_6.html").write_bytes(html_doc((1, LONG), (2, LONG)))
        z = self.changes(added=["DU/2020/6", "DU/2020/99"], changed=["DU/2020/1"], removed=["DU/2020/3"])
        code, so, se = run(EXPORT, ["--dane", self.dane, "--out", self.out, "--workers", 2, "--changed", z])
        self.assertEqual(code, 0, se)
        self.assertIn("DU/2020/99", se)  # ostrzezenie o braku pliku
        rows = read_jsonl(self.out)
        self.assertEqual({r["doc_id"] for r in rows}, {"DU/2020/1", "DU/2020/2", "DU/2020/6", "MP/2026/5", "DU/2020/1#U"})
        d1 = [r for r in rows if r["doc_id"] == "DU/2020/1"]
        self.assertEqual(len(d1), 3)  # 3 artykuly po zmianie, brak starych wierszy
        self.assertEqual([r["ord"] for r in d1], [1, 2, 3])
        self.assertTrue(any("NOWA TRESC" in r["text"] for r in d1))
        self.assertFalse(any("STARA TRESC" in r["text"] for r in d1))
        self.assertEqual(len([r for r in rows if r["doc_id"] == "DU/2020/6"]), 2)
        # nietkniete dokumenty - bajt w bajt
        self.assertEqual(self.lines_of({"DU/2020/2", "MP/2026/5", "DU/2020/1#U"}), keep_before)
        # delta = tylko nowe wiersze
        delta = read_jsonl(self.out_dir / "chunks_delta.jsonl")
        self.assertEqual({r["doc_id"] for r in delta}, {"DU/2020/1", "DU/2020/6"})
        self.assertEqual(len(delta), 5)
        # polskie znaki zachowane (kody znakow, nie wyswietlanie)
        self.assertIn("zadośćuczynienia", "".join(r["text"] for r in d1))
        self.assertNotIn("�", self.out.read_text(encoding="utf-8"))
        # brak plikow tymczasowych, raport zapisany
        self.assertEqual([p.name for p in self.out_dir.glob("*.tmp")], [])
        self.assertIn("added=2, changed=1, removed=1", (self.out_dir / "raport_changed.txt").read_text(encoding="utf-8"))

    def test_changed_error_keeps_old_rows_and_notext_drops_them(self):
        self.assertEqual(self.export()[0], 0)
        old2 = self.lines_of({"DU/2020/2"})
        # uszkodzony plik zamiast HTML -> blad ekstrakcji -> stare wiersze zostaja
        (self.dane / "podstawowe" / "DU_2020_2.html").unlink()
        (self.dane / "podstawowe" / "DU_2020_2.pdf").write_bytes(b"to nie jest pdf")
        # dokument, ktory stracil warstwe tekstowa -> wiersze znikaja, wpis w bez_tekstu
        (self.dane / "podstawowe" / "DU_2020_3.html").write_bytes(html_doc((1, "Krotki.")))
        z = self.changes(changed=["DU/2020/2", "DU/2020/3"])
        code, so, se = run(EXPORT, ["--dane", self.dane, "--out", self.out, "--workers", 2, "--changed", z])
        self.assertEqual(code, 0, se)
        self.assertEqual(self.lines_of({"DU/2020/2"}), old2)
        self.assertNotIn("DU/2020/3", self.ids())
        self.assertIn("DU/2020/2", (self.out_dir / "bledy.txt").read_text(encoding="utf-8"))
        self.assertIn("DU/2020/3", (self.out_dir / "bez_tekstu.txt").read_text(encoding="utf-8"))
        # kolejny przebieg z poprawionym plikiem czysci wpis w bledy.txt
        (self.dane / "podstawowe" / "DU_2020_2.pdf").unlink()
        (self.dane / "podstawowe" / "DU_2020_2.html").write_bytes(html_doc((1, LONG)))
        code, so, se = run(EXPORT, ["--dane", self.dane, "--out", self.out, "--workers", 2, "--changed", self.changes(changed=["DU/2020/2"])])
        self.assertEqual(code, 0, se)
        self.assertFalse((self.out_dir / "bledy.txt").exists())
        self.assertEqual(len([r for r in read_jsonl(self.out) if r["doc_id"] == "DU/2020/2"]), 1)

    def test_changed_ujednolicone_pdf_and_idempotent_rerun(self):
        self.assertEqual(self.export()[0], 0)
        make_pdf(self.dane / "ujednolicone" / "U-DU_2020_1.pdf",
                 ["Art. 1. Nowe brzmienie tekstu jednolitego pierwszej ustawy testowej, dostatecznie dlugie.",
                  "Art. 2. Drugi artykul nowego brzmienia zawiera dodatkowe zwykle slowa w zdaniu testowym."
                  " Pozostale slowa pomagaja przekroczyc minimalny prog dlugosci tekstu w tescie."])
        z = self.changes(changed=["DU/2020/1#U"])
        for _ in range(2):  # drugi przebieg nie moze zdublowac wierszy
            code, so, se = run(EXPORT, ["--dane", self.dane, "--out", self.out, "--workers", 2, "--changed", z])
            self.assertEqual(code, 0, se)
        rows = [r for r in read_jsonl(self.out) if r["doc_id"] == "DU/2020/1#U"]
        self.assertTrue(rows)
        self.assertIn("Nowe brzmienie", " ".join(r["text"] for r in rows))
        self.assertNotIn("Tekst jednolity ustawy testowej pierwszej", " ".join(r["text"] for r in rows))
        self.assertEqual(len(rows), len({r["ord"] for r in rows}))

    def test_changed_empty_and_bad_file(self):
        self.assertEqual(self.export()[0], 0)
        before = self.out.read_bytes()
        code, so, se = run(EXPORT, ["--dane", self.dane, "--out", self.out, "--changed", self.changes()])
        self.assertEqual(code, 0, se)
        self.assertEqual(self.out.read_bytes(), before)
        self.assertEqual((self.out_dir / "chunks_delta.jsonl").read_bytes(), b"")
        bad = self.tmp / "zle.json"
        bad.write_text("{nie json", encoding="utf-8")
        code, so, se = run(EXPORT, ["--dane", self.dane, "--out", self.out, "--changed", bad])
        self.assertNotEqual(code, 0)
        self.assertEqual(self.out.read_bytes(), before)  # plik wyjsciowy nietkniety

    def test_rewrite_chunks_unit(self):
        out = self.tmp / "c.jsonl"
        delta = self.tmp / "d.jsonl"
        out.write_bytes(b'{"doc_id": "A", "ord": 1}\n{"doc_id":"B","ord":1}\n{"ord":1,"doc_id":"C"}\n{"doc_id": "D", "or')
        delta.write_bytes(b'{"doc_id": "E", "ord": 1}')
        rm, add, trunc = ex.rewrite_chunks(out, {"A", "C"}, delta)
        self.assertEqual((rm, add, trunc), (2, 1, True))
        self.assertEqual(out.read_bytes(), b'{"doc_id":"B","ord":1}\n{"doc_id": "E", "ord": 1}\n')
        self.assertFalse(out.with_name("c.jsonl.tmp").exists())

    def test_load_changes_validation(self):
        p = self.tmp / "z.json"
        p.write_text(json.dumps({"added": ["a", "a", "b"], "changed": None}), encoding="utf-8")
        self.assertEqual(ex.load_changes(p), (["a", "b"], [], []))
        p.write_text(json.dumps({"added": "DU/1/1"}), encoding="utf-8")
        with self.assertRaises(ValueError):
            ex.load_changes(p)


# ----------------------------------------------------------------- loader bez bazy

def chunk_row(doc_id, ord_, text, kat="podstawowe", article=None):
    parts = doc_id.split("#")[0].split("/")
    pub, year, pos = (parts + ["2000", "1"])[:3] if len(parts) < 3 else parts
    return {"doc_id": doc_id, "eli": doc_id.split("#")[0], "kategoria": kat, "publisher": pub, "year": int(year),
            "pos": int(pos), "title": f"Tytuł {doc_id}", "display_address": f"Dz.U. {year} poz. {pos}",
            "announcement_date": f"{year}-01-02", "status": "obowiązujący", "is_consolidated": doc_id.endswith("#U"),
            "source_url": f"https://example.invalid/{doc_id}", "ord": ord_, "article": article or str(ord_),
            "heading": "Rozdział 1", "text": text}


class TestLoaderNoDb(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="prawo_a2_ld_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_database_url_sources(self):
        self.assertEqual(ld.get_database_url({"DATABASE_URL": " postgresql://u:p@h/db "}), "postgresql://u:p@h/db")
        env = self.tmp / ".env.local"
        env.write_text('# komentarz\nINNE=1\nexport DATABASE_URL="postgresql://u:p@h/x"\n', encoding="utf-8")
        self.assertEqual(ld.get_database_url({}, env), "postgresql://u:p@h/x")
        self.assertEqual(ld.get_database_url({"DATABASE_URL": "z"}, env), "z")  # srodowisko ma pierwszenstwo
        self.assertIsNone(ld.get_database_url({}, self.tmp / "brak"))
        env.write_text("DATABASE_URL=\n", encoding="utf-8")
        self.assertIsNone(ld.get_database_url({}, env))

    def test_missing_database_url_exits_2_with_message(self):
        src = self.tmp / "c.jsonl"
        write_jsonl(src, [chunk_row("DU/2020/1", 1, "x")])
        z = self.tmp / "z.json"
        z.write_text(json.dumps({"added": ["DU/2020/1"]}), encoding="utf-8")
        for args in (["--input", src, "--sync", z], ["--input", src]):
            code, so, se = run(LOAD, [*args, "--env-file", self.tmp / "nie_ma"], drop_env=("DATABASE_URL",))
            self.assertEqual(code, 2, (so, se))
            self.assertIn("DATABASE_URL", se)

    def test_dry_run_sync_needs_no_db_and_reports_plan(self):
        src = self.tmp / "c.jsonl"
        write_jsonl(src, [chunk_row("DU/2020/1", 1, "a"), chunk_row("DU/2020/1", 2, "b"), chunk_row("DU/2020/2", 1, "c")])
        z = self.tmp / "z.json"
        z.write_text(json.dumps({"added": ["DU/2020/2", "DU/2020/9"], "changed": ["DU/2020/1"], "removed": ["DU/2020/5"]}), encoding="utf-8")
        code, so, se = run(LOAD, ["--input", src, "--sync", z, "--dry-run"], drop_env=("DATABASE_URL",))
        self.assertEqual(code, 0, se)
        self.assertIn("Do zaladowania: 2 dok., 3 fragm.", so)
        self.assertIn("DU/2020/9", se)  # brak w wejsciu - ostrzezenie

    def test_scan_multiple_files_first_wins_and_prefilter(self):
        a, b = self.tmp / "a.jsonl", self.tmp / "b.jsonl"
        write_jsonl(a, [chunk_row("DU/1/1", 1, "stary")])
        # inna kolejnosc kluczy w b - prefiltr musi zadzialac przez pelny parse
        r = chunk_row("DU/1/1", 1, "nowy")
        r2 = {"ord": 1, "doc_id": "DU/1/2", **{k: v for k, v in chunk_row("DU/1/2", 1, "drugi").items() if k not in ("ord", "doc_id")}}
        write_jsonl(b, [r, r2])
        docs = ld.scan([a, b], None)
        self.assertEqual(set(docs), {"DU/1/1", "DU/1/2"})
        self.assertEqual(docs["DU/1/1"]["src"], 0)
        self.assertEqual(docs["DU/1/1"]["n_chunks"], 1)
        self.assertEqual(docs["DU/1/1"]["dup_ignored"], 1)
        self.assertEqual(docs["DU/1/2"]["src"], 1)
        only = ld.scan([a, b], None, only_ids={"DU/1/2"})
        self.assertEqual(set(only), {"DU/1/2"})

    def test_skipped_file_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "pominiete_limit.json"
            self.assertEqual(ld.load_skipped(f), [])
            ld.save_skipped(f, {"DU/1/2", "DU/1/1"}, 450)
            self.assertEqual(ld.load_skipped(f), ["DU/1/1", "DU/1/2"])
            ld.save_skipped(f, set())
            self.assertFalse(f.exists())
            ld.save_skipped(f, set())      # brak pliku nie jest bledem

    def test_plan_sync(self):
        docs = {"A": {}, "B": {}}
        p = ld.plan_sync(["B", "C"], ["A"], ["R"], docs)
        self.assertEqual(p["found"], ["B", "A"])
        self.assertEqual(p["missing"], ["C"])
        self.assertEqual(set(p["delete"]), {"R", "A", "B", "C"})


# ----------------------------------------------------------------- integracja z Postgresem

@unittest.skipUnless(DB_URL, "ustaw PRAWO_TEST_DATABASE_URL, aby uruchomic testy z baza")
class TestSyncPostgres(unittest.TestCase):
    def setUp(self):
        import psycopg
        self.psycopg = psycopg
        self.tmp = Path(tempfile.mkdtemp(prefix="prawo_a2_pg_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.env = {"DATABASE_URL": DB_URL}
        self.chunks = self.tmp / "chunks.jsonl"
        # stan poczatkowy: A(3) B(2) C(2) D(1, ujednolicone)
        self.rows = (
            [chunk_row("DU/2020/1", i, f"Art. {i}. tresc A wersja 1", article=str(i)) for i in (1, 2, 3)]
            + [chunk_row("DU/2020/2", i, f"Art. {i}. tresc B", article=str(i)) for i in (1, 2)]
            + [chunk_row("MP/2026/3", i, f"Art. {i}. tresc C", kat="mp", article=str(i)) for i in (1, 2)]
            + [chunk_row("DU/2020/4#U", 1, "Art. 1. tresc D ujednolicona", kat="ujednolicone")]
        )
        write_jsonl(self.chunks, self.rows)
        code, so, se = run(LOAD, ["--input", self.chunks, "--schema", "--truncate"], self.env)
        self.assertEqual(code, 0, se + so)
        self.assertEqual(self.counts(), (4, 8))

    def q(self, sql, params=None):
        with self.psycopg.connect(DB_URL) as c:
            return c.execute(sql, params).fetchall()

    def counts(self):
        return self.q("select (select count(*) from documents), (select count(*) from chunks)")[0]

    def state(self):
        return {r[0]: (r[1], r[2]) for r in self.q(
            "select d.doc_id, d.n_chunks, (select count(*) from chunks c where c.doc_id=d.doc_id) from documents d")}

    def zmiany(self, **kw):
        z = self.tmp / "zmiany.json"
        z.write_text(json.dumps({"added": kw.get("added", []), "changed": kw.get("changed", []), "removed": kw.get("removed", [])}), encoding="utf-8")
        return z

    def new_chunks(self):
        """A zmienione (2 fragmenty), B usuniete, E dodane (2 fragmenty), reszta bez zmian."""
        keep = [r for r in self.rows if r["doc_id"] not in ("DU/2020/1", "DU/2020/2")]
        a = [chunk_row("DU/2020/1", i, f"Art. {i}. tresc A wersja 2", article=str(i)) for i in (1, 2)]
        e = [chunk_row("DU/2021/9", i, f"Art. {i}. tresc E nowa", article=str(i)) for i in (1, 2)]
        write_jsonl(self.chunks, keep + a + e)

    def test_sync_added_changed_removed(self):
        self.new_chunks()
        z = self.zmiany(added=["DU/2021/9"], changed=["DU/2020/1"], removed=["DU/2020/2"])
        code, so, se = run(LOAD, ["--input", self.chunks, "--sync", z], self.env)
        self.assertEqual(code, 0, se + so)
        self.assertEqual(self.state(), {"DU/2020/1": (2, 2), "MP/2026/3": (2, 2), "DU/2020/4#U": (1, 1), "DU/2021/9": (2, 2)})
        self.assertEqual(self.counts(), (4, 7))
        txt = [r[0] for r in self.q("select text from chunks where doc_id='DU/2020/1' order by ord")]
        self.assertEqual(txt, ["Art. 1. tresc A wersja 2", "Art. 2. tresc A wersja 2"])
        self.assertEqual(self.q("select count(*) from chunks where doc_id='DU/2020/2'")[0][0], 0)  # kaskada
        dup = self.q("select count(*) from (select doc_id, ord from chunks group by 1,2 having count(*)>1) t")[0][0]
        self.assertEqual(dup, 0)
        # polskie znaki w bazie - sprawdzone po kodach znakow
        self.assertEqual(self.q("select title from documents where doc_id='DU/2020/1'")[0][0], "Tytuł DU/2020/1")
        # wyszukiwanie dziala na swiezo zaladowanych danych (tsv generowany)
        hit = self.q("select doc_id from chunks where tsv @@ pl_prefix_query('nowa') ")
        self.assertEqual({r[0] for r in hit}, {"DU/2021/9"})

    def test_sync_is_idempotent(self):
        self.new_chunks()
        z = self.zmiany(added=["DU/2021/9"], changed=["DU/2020/1"], removed=["DU/2020/2"])
        for _ in range(2):
            code, so, se = run(LOAD, ["--input", self.chunks, "--sync", z], self.env)
            self.assertEqual(code, 0, se + so)
        self.assertEqual(self.counts(), (4, 7))

    def test_sync_multiple_inputs_delta_file(self):
        self.new_chunks()
        rows = read_jsonl(self.chunks)
        delta = self.tmp / "delta.jsonl"
        write_jsonl(delta, [r for r in rows if r["doc_id"] in ("DU/2020/1", "DU/2021/9")])
        write_jsonl(self.chunks, [r for r in rows if r["doc_id"] not in ("DU/2020/1", "DU/2021/9")])
        z = self.zmiany(added=["DU/2021/9"], changed=["DU/2020/1"], removed=["DU/2020/2"])
        code, so, se = run(LOAD, ["--input", self.chunks, delta, "--sync", z], self.env)
        self.assertEqual(code, 0, se + so)
        self.assertEqual(self.state()["DU/2020/1"], (2, 2))
        self.assertEqual(self.state()["DU/2021/9"], (2, 2))

    def test_sync_failure_rolls_back_everything(self):
        self.new_chunks()
        rows = read_jsonl(self.chunks)
        bad = next(r for r in rows if r["doc_id"] == "DU/2021/9" and r["ord"] == 2)
        del bad["text"]  # KeyError w trakcie ladowania, juz PO usunieciu starych dokumentow
        write_jsonl(self.chunks, rows)
        before = self.state()
        z = self.zmiany(added=["DU/2021/9"], changed=["DU/2020/1"], removed=["DU/2020/2"])
        code, so, se = run(LOAD, ["--input", self.chunks, "--sync", z], self.env)
        self.assertNotEqual(code, 0)
        self.assertEqual(self.state(), before)  # nic nie ruszone: A, B nadal sa, E nie ma
        self.assertEqual(self.counts(), (4, 8))
        self.assertEqual(self.q("select text from chunks where doc_id='DU/2020/1' and ord=1")[0][0], "Art. 1. tresc A wersja 1")

    def test_sync_max_mb_blocks_new_docs_only(self):
        self.new_chunks()
        z = self.zmiany(added=["DU/2021/9"], changed=["DU/2020/1"], removed=["DU/2020/2"])
        code, so, se = run(LOAD, ["--input", self.chunks, "--sync", z, "--max-mb", "0.001"], self.env)
        self.assertEqual(code, 0, se + so)
        st = self.state()
        self.assertNotIn("DU/2021/9", st)  # nowy dokument zablokowany limitem
        self.assertEqual(st["DU/2020/1"], (2, 2))  # zmieniony nadal podmieniony
        self.assertNotIn("DU/2020/2", st)  # usuniety
        self.assertIn("DU/2021/9", se)
        # z wysokim limitem nowy dokument wchodzi
        code, so, se = run(LOAD, ["--input", self.chunks, "--sync", z, "--max-mb", "4096"], self.env)
        self.assertEqual(code, 0, se + so)
        self.assertEqual(self.state()["DU/2021/9"], (2, 2))

    def test_sync_changed_missing_from_input_is_deleted_and_empty_changes_ok(self):
        z = self.zmiany(changed=["DU/2020/2"])  # brak w wejsciu (np. akt stracil warstwe tekstowa)
        write_jsonl(self.chunks, [r for r in self.rows if r["doc_id"] != "DU/2020/2"])
        code, so, se = run(LOAD, ["--input", self.chunks, "--sync", z], self.env)
        self.assertEqual(code, 0, se + so)
        self.assertNotIn("DU/2020/2", self.state())
        code, so, se = run(LOAD, ["--input", self.chunks, "--sync", self.zmiany()], self.env)
        self.assertEqual(code, 0, se + so)
        self.assertEqual(self.counts(), (3, 6))

    def test_full_mode_still_works_with_multiple_inputs(self):
        extra = self.tmp / "extra.jsonl"
        write_jsonl(extra, [chunk_row("SAOS/12345", 1, "wyrok testowy", kat="wyrok")])
        code, so, se = run(LOAD, ["--input", self.chunks, extra, "--truncate"], self.env)
        self.assertEqual(code, 0, se + so)
        self.assertEqual(self.counts(), (5, 9))


if __name__ == "__main__":
    unittest.main()
