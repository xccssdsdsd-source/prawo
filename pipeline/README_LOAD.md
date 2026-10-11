# Ladowanie danych do Postgresa (Neon)

## 1. Konto i baza (darmowy Neon)
1. Zaloz konto na https://neon.tech i utworz projekt (region np. Frankfurt - blisko Vercel `fra1`).
2. Skopiuj connection string (`postgresql://user:haslo@ep-xxx.eu-central-1.aws.neon.tech/neondb?sslmode=require`).
3. Rozszerzenia `unaccent` i `pg_trgm` sa dostepne w Neon; `schema.sql` wlacza je sam (`create extension if not exists`).
   Gdyby brakowalo uprawnien, w SQL Editor w konsoli Neon wykonaj: `create extension unaccent; create extension pg_trgm;`.

## 2. Zmienna srodowiskowa
PowerShell: `$env:DATABASE_URL = "postgresql://..."`
bash: `export DATABASE_URL="postgresql://..."`
Ten sam adres ustaw w Vercel jako `DATABASE_URL` (do ladowania mozna uzyc adresu bezposredniego, dla Vercel - adresu z `-pooler`).

## 3. Uruchomienie
```
pip install -r pipeline/requirements.txt
python pipeline/load_to_postgres.py --dry-run --max-mb 400        # tylko szacunek
python pipeline/load_to_postgres.py --schema --max-mb 400         # pierwsze ladowanie
python pipeline/load_to_postgres.py --kategorie ujednolicone,jednolite   # tylko wybrane
python pipeline/load_to_postgres.py --input pipeline/out/sample_chunks.jsonl --schema   # probka do testu
```
Flagi: `--schema` (tworzy schemat, idempotentnie), `--truncate` (czysci tabele), `--kategorie`, `--max-mb`,
`--overhead` (mnoznik rozmiaru bazy wzgledem tekstu, domyslnie 2.5), `--batch`, `--dry-run`, `--input`.

Kolejnosc priorytetow przy limicie: ujednolicone, jednolite, podstawowe, mp, zmieniajace, reszta (w obrebie kategorii od najstarszych).
Wznawianie: ponowne uruchomienie pomija kompletne dokumenty, a niekompletne (przerwane w pol) usuwa i laduje od nowa.
Na koncu: aktualizacja `documents.n_chunks`, `ANALYZE`, wypisanie liczby dokumentow/fragmentow i `pg_database_size`.

## 4. Szacunek rozmiaru
Baza ~ 2-3x rozmiaru surowego tekstu (kolumna `text` + `tsvector` + indeks GIN + pozostale indeksy).
Darmowy Neon ma ok. 0,5 GB, wiec zaladowanych moze byc ok. 150-200 MB czystego tekstu. Przyklad: probka 6 fragmentow = 8 MB
(to glownie narzut pustej bazy). Po pierwszym ladowaniu porownaj wynik z szacunkiem i skoryguj `--overhead`.
Zostaw zapas ~15% (WAL, rosnace indeksy). Gdy za duzo: zacznij od `--kategorie ujednolicone,jednolite`.

## 5. Uwaga techniczna (odstepstwo od SPEC)
`unaccent()` jest STABLE, wiec w kolumnie generowanej `tsv` Postgres odrzuca je ("generation expression is not immutable").
Schemat definiuje wiec `f_unaccent(text)` (IMMUTABLE) i uzywa go w `tsv`. Zapytania powinny uzywac `pl_prefix_query(q)`
(zwraca `tsquery` z prefiksami i stemmingiem jak `rdzen()`), albo `to_tsquery('simple', f_unaccent(...))`.
Przyklad: `select doc_id, article from chunks where tsv @@ pl_prefix_query('zadośćuczynienie art. 445') order by ts_rank_cd(tsv, pl_prefix_query('zadośćuczynienie art. 445')) desc limit 8;`
