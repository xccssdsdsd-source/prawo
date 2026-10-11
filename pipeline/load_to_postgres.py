#!/usr/bin/env python3
"""Ladowanie pipeline/out/chunks.jsonl do Postgresa (COPY, paczki, wznawialne).

DATABASE_URL=postgresql://... python load_to_postgres.py --schema --max-mb 400
"""
import argparse, json, os, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIORYTET = ["ujednolicone", "jednolite", "podstawowe", "mp", "zmieniajace"]
DOC_COLS = ["doc_id", "eli", "kategoria", "publisher", "year", "pos", "title", "display_address",
            "announcement_date", "status", "is_consolidated", "source_url", "n_chunks"]


def prio(kat):
    return PRIORYTET.index(kat) if kat in PRIORYTET else len(PRIORYTET)


def clean(s):
    return s.replace("\x00", "") if isinstance(s, str) else s


def iter_lines(path):
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                print(f"! linia {n}: zly JSON ({e}) - pominieta", file=sys.stderr)


def scan(path, kategorie):
    """Przebieg 1: metadane dokumentow, liczba fragmentow i rozmiar tekstu."""
    docs = {}
    for r in iter_lines(path):
        if kategorie and r["kategoria"] not in kategorie:
            continue
        d = docs.get(r["doc_id"])
        if d is None:
            d = docs[r["doc_id"]] = {k: r.get(k) for k in DOC_COLS if k != "n_chunks"}
            d["n_chunks"] = 0
            d["bytes"] = 0
        d["n_chunks"] += 1
        d["bytes"] += len((r.get("text") or "").encode()) + len((r.get("heading") or "").encode())
    return docs


def select(docs, max_mb, overhead):
    """Wybor dokumentow wg priorytetu do limitu szacowanego rozmiaru bazy."""
    order = sorted(docs.values(), key=lambda d: (prio(d["kategoria"]), d["year"] or 0, d["pos"] or 0))
    limit = max_mb * 1024 * 1024 if max_mb else None
    chosen, total = set(), 0
    skipped = {}
    for d in order:
        est = d["bytes"] * overhead + 400 + d["n_chunks"] * 120
        if limit is not None and total + est > limit:
            skipped[d["kategoria"]] = skipped.get(d["kategoria"], 0) + 1
            continue
        chosen.add(d["doc_id"])
        total += est
    return chosen, total, skipped


def report(docs, chosen, total, skipped):
    per = {}
    for d in docs.values():
        p = per.setdefault(d["kategoria"], [0, 0, 0, 0, 0])
        p[0] += 1; p[1] += d["n_chunks"]; p[2] += d["bytes"]
        if d["doc_id"] in chosen:
            p[3] += 1; p[4] += d["n_chunks"]
    print(f"{'kategoria':14}{'dok.':>9}{'fragm.':>10}{'tekst MB':>10}{'wybrane dok.':>14}{'wybr. fragm.':>14}")
    for k in sorted(per, key=prio):
        p = per[k]
        print(f"{k:14}{p[0]:>9}{p[1]:>10}{p[2]/1048576:>10.3f}{p[3]:>14}{p[4]:>14}")
    print(f"Szacowany rozmiar bazy po zaladowaniu wybranych: {total/1048576:.1f} MB")
    if skipped:
        print("Pominiete przez --max-mb (dokumentow wg kategorii):", skipped)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default=str(HERE / "out" / "chunks.jsonl"))
    ap.add_argument("--schema", action="store_true", help="utworz schemat (schema.sql) przed ladowaniem")
    ap.add_argument("--truncate", action="store_true", help="wyczysc documents/chunks przed ladowaniem")
    ap.add_argument("--kategorie", help="lista po przecinku, np. ujednolicone,jednolite")
    ap.add_argument("--max-mb", type=float, help="limit szacowanego rozmiaru bazy (MB)")
    ap.add_argument("--overhead", type=float, default=2.5,
                    help="mnoznik rozmiar_bazy/rozmiar_tekstu (tsv+GIN+indeksy), domyslnie 2.5; skoryguj po pierwszym ladowaniu")
    ap.add_argument("--batch", type=int, default=5000, help="fragmentow na paczke COPY")
    ap.add_argument("--dry-run", action="store_true", help="tylko policz i pokaz, bez bazy")
    a = ap.parse_args()

    inp = Path(a.input)
    if not inp.exists():
        sys.exit(f"Brak pliku {inp} (probka: {HERE/'out'/'sample_chunks.jsonl'}, uzyj --input)")
    kat = set(x.strip() for x in a.kategorie.split(",")) if a.kategorie else None

    t0 = time.time()
    docs = scan(inp, kat)
    chosen, total, skipped = select(docs, a.max_mb, a.overhead)
    report(docs, chosen, total, skipped)
    if a.dry_run:
        print("--dry-run: nic nie zaladowano.")
        return

    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("Ustaw zmienna DATABASE_URL.")
    import psycopg

    with psycopg.connect(url, autocommit=True) as conn:
        if a.schema:
            conn.execute((HERE / "schema.sql").read_text(encoding="utf-8"))
            print("Schemat utworzony.")
        if a.truncate:
            conn.execute("truncate chunks, documents restart identity cascade")
            print("Tabele wyczyszczone.")

        # wznawianie: dokument kompletny, gdy n_chunks == faktyczna liczba == liczba z przebiegu 1
        have = conn.execute(
            "select d.doc_id, d.n_chunks, (select count(*) from chunks c where c.doc_id=d.doc_id) from documents d").fetchall()
        done, bad = set(), []
        for did, n, actual in have:
            if did in docs and n == actual == docs[did]["n_chunks"]:
                done.add(did)
            elif did in docs:
                bad.append(did)
        if bad:
            conn.execute("delete from documents where doc_id = any(%s)", (bad,))
            print(f"Usunieto {len(bad)} niekompletnych dokumentow (zostana zaladowane ponownie).")
        todo = chosen - done
        print(f"Juz zaladowane: {len(done)}, do zaladowania: {len(todo)} dok.")

        # przebieg 2 (n_chunks w documents ustawiane z przebiegu 1 => marker kompletnosci)
        st = {"docs": 0, "chunks": 0}
        buf_docs, buf_rows, started = [], [], set()

        def flush():
            nonlocal buf_docs, buf_rows
            if not buf_rows and not buf_docs:
                return
            with conn.transaction():
                with conn.cursor() as cur:
                    if buf_docs:
                        with cur.copy(f"copy documents ({','.join(DOC_COLS)}) from stdin") as cp:
                            for row in buf_docs:
                                cp.write_row(row)
                    with cur.copy("copy chunks (doc_id, ord, article, heading, text) from stdin") as cp:
                        for row in buf_rows:
                            cp.write_row(row)
            st["docs"] += len(buf_docs); st["chunks"] += len(buf_rows)
            buf_docs, buf_rows = [], []
            print(f"  ... {st['docs']} dok., {st['chunks']} fragm. ({time.time()-t0:.0f}s)", flush=True)

        for r in iter_lines(inp):
            did = r["doc_id"]
            if did not in todo:
                continue
            if did not in started:
                started.add(did)
                m = docs[did]
                buf_docs.append(tuple(clean(m[k]) for k in DOC_COLS))
            buf_rows.append((did, r["ord"], clean(r.get("article")), clean(r.get("heading")), clean(r["text"])))
            if len(buf_rows) >= a.batch:
                flush()
        flush()

        conn.execute("update documents d set n_chunks = (select count(*) from chunks c where c.doc_id = d.doc_id)")
        conn.execute("analyze documents")
        conn.execute("analyze chunks")
        nd = conn.execute("select count(*) from documents").fetchone()[0]
        nc = conn.execute("select count(*) from chunks").fetchone()[0]
        size = conn.execute("select pg_database_size(current_database()), pg_size_pretty(pg_database_size(current_database()))").fetchone()
        print(f"Gotowe: dokumentow {nd}, fragmentow {nc}, rozmiar bazy {size[1]} ({size[0]/1048576:.0f} MB), czas {time.time()-t0:.0f}s")
        print("Limit darmowego Neon ~512 MB; jesli blisko - uzyj --max-mb / --kategorie.")


if __name__ == "__main__":
    main()
