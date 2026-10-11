#!/usr/bin/env python3
"""Ladowanie pipeline/out/chunks*.jsonl do Postgresa (COPY, paczki, wznawialne).

Tryb pelny (jak dotad):
  DATABASE_URL=postgresql://... python load_to_postgres.py --schema --max-mb 400
Tryb przyrostowy (po aktualizacji danych):
  python load_to_postgres.py --sync stan/zmiany.json [--input chunks.jsonl chunks_saos.jsonl] [--max-mb 400]
    w jednej transakcji: usuwa z bazy removed+changed, laduje added+changed, przelicza n_chunks, potem ANALYZE.
    Blad w trakcie = ROLLBACK, baza zostaje w poprzednim stanie.

Kody wyjscia: 0 ok, 1 blad, 2 brak DATABASE_URL (orkiestrator traktuje jako "krok pominiety").
DATABASE_URL brany ze zmiennej srodowiskowej, a jesli jej brak - z .env.local w korzeniu repo (wartosc nigdy nie jest wypisywana).
"""
import argparse, json, os, re, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PRIORYTET = ["ujednolicone", "jednolite", "podstawowe", "mp", "zmieniajace"]
DOC_COLS = ["doc_id", "eli", "kategoria", "publisher", "year", "pos", "title", "display_address",
            "announcement_date", "status", "is_consolidated", "source_url", "n_chunks"]
_DOCID_RE = re.compile(rb'\{"doc_id": ?"([^"]+)"')
EXIT_NO_DB = 2


def prio(kat):
    return PRIORYTET.index(kat) if kat in PRIORYTET else len(PRIORYTET)


def clean(s):
    return s.replace("\x00", "") if isinstance(s, str) else s


# ----------------------------------------------------------------- konfiguracja

def get_database_url(environ=None, env_file=None):
    """DATABASE_URL ze srodowiska, a w razie braku z pliku .env.local (KEY=VALUE). Brak -> None."""
    environ = os.environ if environ is None else environ
    url = (environ.get("DATABASE_URL") or "").strip()
    if url:
        return url
    if env_file and Path(env_file).is_file():
        for line in Path(env_file).read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line.startswith("export "):
                line = line[7:].strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == "DATABASE_URL":
                v = v.strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                    v = v[1:-1]
                if v:
                    return v
    return None


def no_db_exit():
    print("BRAK DATABASE_URL: nie ustawiono zmiennej srodowiskowej ani wpisu w .env.local - krok bazy pominiety.\n"
          "Ustaw np. (PowerShell) $env:DATABASE_URL = \"postgresql://...\" albo dodaj linie DATABASE_URL=... do .env.local "
          "(patrz pipeline/README_LOAD.md).", file=sys.stderr)
    sys.exit(EXIT_NO_DB)


def load_changes(path):
    """stan/zmiany.json -> (added, changed, removed) jako listy doc_id (unikalne, kolejnosc zachowana)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: oczekiwano obiektu JSON z kluczami added/changed/removed")

    def lst(k):
        v = data.get(k) or []
        if not isinstance(v, list):
            raise ValueError(f"{path}: pole '{k}' musi byc lista")
        return list(dict.fromkeys(str(x) for x in v))

    return lst("added"), lst("changed"), lst("removed")


# ----------------------------------------------------------------- odczyt JSONL

def iter_lines(path, only_ids=None):
    """Wiersze JSONL jako dict. Przy only_ids linie innych dokumentow sa odrzucane PRZED parsowaniem JSON (szybko dla duzych plikow)."""
    with open(path, "rb") as f:
        for n, raw in enumerate(f, 1):
            if not raw.strip():
                continue
            if only_ids is not None:
                m = _DOCID_RE.match(raw)
                if m is not None and m.group(1).decode("utf-8") not in only_ids:
                    continue
            try:
                r = json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                print(f"! {Path(path).name} linia {n}: zly JSON ({e}) - pominieta", file=sys.stderr)
                continue
            if only_ids is not None and r.get("doc_id") not in only_ids:
                continue
            yield r


def _paths(p):
    return [Path(x) for x in ([p] if isinstance(p, (str, Path)) else p)]


def iter_chunks(paths, only_ids=None):
    """-> (indeks_pliku, wiersz) po wszystkich plikach wejsciowych w podanej kolejnosci."""
    for i, p in enumerate(_paths(paths)):
        for r in iter_lines(p, only_ids):
            yield i, r


def scan(paths, kategorie, only_ids=None):
    """Przebieg 1: metadane dokumentow, liczba fragmentow i rozmiar tekstu.
    Wiele plikow: dokument nalezy do PIERWSZEGO pliku, w ktorym wystapil (wiersze z pozniejszych plikow sa ignorowane)."""
    docs = {}
    for idx, r in iter_chunks(paths, only_ids):
        if kategorie and r["kategoria"] not in kategorie:
            continue
        d = docs.get(r["doc_id"])
        if d is None:
            d = docs[r["doc_id"]] = {k: r.get(k) for k in DOC_COLS if k != "n_chunks"}
            d["n_chunks"] = 0
            d["bytes"] = 0
            d["src"] = idx
        elif d["src"] != idx:
            d["dup_ignored"] = d.get("dup_ignored", 0) + 1
            continue
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


# ----------------------------------------------------------------- COPY

def copy_docs(conn, paths, docs, todo, batch, t0, gated=None, limit_check=None):
    """Przebieg 2: COPY dokumentow z `todo` (n_chunks z przebiegu 1 = marker kompletnosci).
    gated: zbior doc_id, ktore wolno zaladowac tylko dopoki limit_check() zwraca False (sprawdzane na granicy dokumentu).
    Zwraca (zaladowane_doc_id, liczba_fragmentow, pominiete_przez_limit)."""
    st = {"docs": 0, "chunks": 0}
    buf_docs, buf_rows = [], []
    started, loaded, blocked = set(), set(), set()
    state = {"limit": bool(limit_check and limit_check())}

    def flush():
        nonlocal buf_docs, buf_rows
        if not buf_rows and not buf_docs:
            return
        with conn.transaction():  # w transakcji zewnetrznej = savepoint
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
        if limit_check and gated:
            state["limit"] = bool(limit_check())

    for idx, r in iter_chunks(paths, todo):
        did = r["doc_id"]
        if did not in todo or did in blocked:
            continue
        m = docs[did]
        if m["src"] != idx:
            continue
        if did not in started:
            if gated and did in gated and state["limit"]:
                blocked.add(did)
                continue
            started.add(did)
            loaded.add(did)
            buf_docs.append(tuple(clean(m[k]) for k in DOC_COLS))
        buf_rows.append((did, r["ord"], clean(r.get("article")), clean(r.get("heading")), clean(r["text"])))
        if len(buf_rows) >= batch:
            flush()
    flush()
    return loaded, st["chunks"], blocked


def db_size(conn):
    return conn.execute("select pg_database_size(current_database())").fetchone()[0]


# ----------------------------------------------------------------- tryb --sync

def plan_sync(added, changed, removed, docs):
    """Czysta logika planu (testowalna bez bazy). docs = dokumenty znalezione w plikach wejsciowych (tylko cele)."""
    targets = list(dict.fromkeys(added + changed))
    found = [i for i in targets if i in docs]
    missing = [i for i in targets if i not in docs]
    return {"targets": targets, "found": found, "missing": missing,
            "delete": list(dict.fromkeys(removed + changed + added))}


def run_sync(a, paths, url):
    added, changed, removed = load_changes(a.sync)
    targets = set(added) | set(changed)
    print(f"--sync: added={len(added)} changed={len(changed)} removed={len(removed)}", flush=True)
    t0 = time.time()
    docs = scan(paths, None, only_ids=targets) if targets else {}
    plan = plan_sync(added, changed, removed, docs)
    for i in plan["missing"]:
        print(f"! OSTRZEZENIE: {i} z listy zmian nie ma w plikach wejsciowych"
              + (" - dokument zostanie USUNIETY z bazy (stary tekst jest nieaktualny)" if i in changed else " - pomijam"),
              file=sys.stderr)
    dups = sum(d.get("dup_ignored", 0) for d in docs.values())
    if dups:
        print(f"Uwaga: {dups} wierszy z kolejnych plikow --input zignorowano (dokument wystepuje juz we wczesniejszym pliku; "
              "to normalne, gdy podano razem chunks.jsonl i chunks_delta.jsonl).")
    nfrag = sum(d["n_chunks"] for d in docs.values())
    print(f"Do zaladowania: {len(docs)} dok., {nfrag} fragm.; do usuniecia z bazy (jesli sa): {len(plan['delete'])} dok.")
    if a.dry_run:
        print("--dry-run: nic nie zmieniono w bazie (limit --max-mb nie jest sprawdzany bez polaczenia).")
        return 0
    if not plan["delete"] and not docs:
        print("Brak zmian do zsynchronizowania.")
        return 0

    import psycopg
    limit_bytes = int(a.max_mb * 1024 * 1024) if a.max_mb else None
    with connect(psycopg, url) as conn:
        if a.schema:
            conn.execute((HERE / "schema.sql").read_text(encoding="utf-8"))
            print("Schemat utworzony.")
        ids = list(set(plan["delete"]) | set(docs))
        existing = {r[0] for r in conn.execute("select doc_id from documents where doc_id = any(%s)", (ids,)).fetchall()}
        gated = set(docs) - existing  # nowe w bazie => podlegaja limitowi rozmiaru
        limit_check = (lambda: db_size(conn) >= limit_bytes) if limit_bytes else None
        with conn.transaction():
            cur = conn.execute("delete from documents where doc_id = any(%s)", (plan["delete"],))
            n_del = cur.rowcount
            todo = set(docs)
            loaded, nchunks, blocked = copy_docs(conn, paths, docs, todo, a.batch, t0, gated, limit_check)
            if loaded:
                conn.execute("update documents d set n_chunks = (select count(*) from chunks c where c.doc_id = d.doc_id) "
                             "where d.doc_id = any(%s)", (list(loaded),))
                bad = conn.execute("select doc_id, n_chunks from documents where doc_id = any(%s)", (list(loaded),)).fetchall()
                wrong = [(i, n, docs[i]["n_chunks"]) for i, n in bad if n != docs[i]["n_chunks"]]
                if wrong or len(bad) != len(loaded):
                    raise RuntimeError(f"niezgodna liczba fragmentow po zaladowaniu (np. {wrong[:3]}) - ROLLBACK")
        conn.execute("analyze documents")
        conn.execute("analyze chunks")
        nd = conn.execute("select count(*) from documents").fetchone()[0]
        nc = conn.execute("select count(*) from chunks").fetchone()[0]
        size = db_size(conn)
    if blocked:
        print(f"! Limit --max-mb {a.max_mb:g} MB osiagniety: nie dodano {len(blocked)} nowych dokumentow "
              f"({', '.join(sorted(blocked)[:10])}{'...' if len(blocked) > 10 else ''}).", file=sys.stderr)
    print(f"Sync gotowy: usunieto {n_del} dok., zaladowano {len(loaded)} dok. / {nchunks} fragm., "
          f"pominieto przez limit {len(blocked)}, brak w plikach {len(plan['missing'])}.")
    print(f"Baza teraz: dokumentow {nd}, fragmentow {nc}, rozmiar {size/1048576:.0f} MB, czas {time.time()-t0:.0f}s")
    return 0


def connect(psycopg, url):
    """Polaczenie z ukryciem DATABASE_URL w komunikatach bledow."""
    try:
        return psycopg.connect(url, autocommit=True)
    except psycopg.Error as e:
        msg = str(e).replace(url, "<DATABASE_URL>")
        print(f"Nie mozna polaczyc z baza: {type(e).__name__}: {msg}", file=sys.stderr)
        sys.exit(1)


# ----------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", nargs="+", default=[str(HERE / "out" / "chunks.jsonl")],
                    help="jeden lub wiele plikow JSONL (np. chunks.jsonl chunks_saos.jsonl)")
    ap.add_argument("--sync", metavar="ZMIANY_JSON", help="tryb przyrostowy wg stan/zmiany.json (added/changed/removed)")
    ap.add_argument("--schema", action="store_true", help="utworz schemat (schema.sql) przed ladowaniem")
    ap.add_argument("--truncate", action="store_true", help="wyczysc documents/chunks przed ladowaniem")
    ap.add_argument("--kategorie", help="lista po przecinku, np. ujednolicone,jednolite")
    ap.add_argument("--max-mb", type=float, help="limit rozmiaru bazy (MB); w --sync: nowe dokumenty tylko gdy pg_database_size ponizej limitu")
    ap.add_argument("--overhead", type=float, default=2.5,
                    help="mnoznik rozmiar_bazy/rozmiar_tekstu (tsv+GIN+indeksy), domyslnie 2.5; skoryguj po pierwszym ladowaniu")
    ap.add_argument("--batch", type=int, default=5000, help="fragmentow na paczke COPY")
    ap.add_argument("--dry-run", action="store_true", help="tylko policz i pokaz, bez bazy")
    ap.add_argument("--env-file", default=str(ROOT / ".env.local"), help="plik z DATABASE_URL, gdy brak zmiennej srodowiskowej")
    a = ap.parse_args(argv)

    paths = _paths(a.input)
    missing_files = [p for p in paths if not p.exists()]
    if missing_files:
        sys.exit(f"Brak pliku {missing_files[0]} (probka: {HERE/'out'/'sample_chunks.jsonl'}, uzyj --input)")
    kat = set(x.strip() for x in a.kategorie.split(",")) if a.kategorie else None

    url = None
    if not a.dry_run:
        url = get_database_url(env_file=a.env_file)
        if not url:
            no_db_exit()

    if a.sync:
        if a.truncate or kat:
            sys.exit("--sync nie laczy sie z --truncate ani --kategorie")
        try:
            return run_sync(a, paths, url)
        except (OSError, ValueError) as e:
            sys.exit(f"Blad trybu --sync: {e}")

    t0 = time.time()
    docs = scan(paths, kat)
    chosen, total, skipped = select(docs, a.max_mb, a.overhead)
    report(docs, chosen, total, skipped)
    if a.dry_run:
        print("--dry-run: nic nie zaladowano.")
        return 0

    import psycopg

    with connect(psycopg, url) as conn:
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

        copy_docs(conn, paths, docs, todo, a.batch, t0)

        conn.execute("update documents d set n_chunks = (select count(*) from chunks c where c.doc_id = d.doc_id)")
        conn.execute("analyze documents")
        conn.execute("analyze chunks")
        nd = conn.execute("select count(*) from documents").fetchone()[0]
        nc = conn.execute("select count(*) from chunks").fetchone()[0]
        size = conn.execute("select pg_database_size(current_database()), pg_size_pretty(pg_database_size(current_database()))").fetchone()
        print(f"Gotowe: dokumentow {nd}, fragmentow {nc}, rozmiar bazy {size[1]} ({size[0]/1048576:.0f} MB), czas {time.time()-t0:.0f}s")
        print("Limit darmowego Neon ~512 MB; jesli blisko - uzyj --max-mb / --kategorie.")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
