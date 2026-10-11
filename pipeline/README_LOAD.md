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

## 6. Aktualizacje przyrostowe (`stan/zmiany.json`)
`python aktualizuj.py` (lub reczne kroki ponizej) odswieza tylko to, co sie zmienilo. Wejsciem jest `stan/zmiany.json`
(`added`, `changed`, `removed` - lista `doc_id`, np. `DU/1964/93#U`) zapisany przez `pipeline/update_data.py`.

```
python pipeline/export_chunks.py --changed stan/zmiany.json
python pipeline/load_to_postgres.py --sync stan/zmiany.json [--max-mb 400] [--dry-run]
```
**Eksport `--changed`:** z `pipeline/out/chunks.jsonl` usuwa wiersze `changed`+`removed`, eksportuje `added`+`changed`
(kategorie ujednolicone / mp / zwykle; HTML lub PDF) i dopisuje je atomowo (plik `.tmp` obok + `os.replace`; potrzeba chwilowo
miejsca na druga kopie pliku). Nowe wiersze trafiaja tez do `pipeline/out/chunks_delta.jsonl`. Zasady:
- brak pliku/metadanych dla `added`/`changed` (np. akt wycofany) - ostrzezenie, dokument pominiety, stare wiersze zostaja;
- blad ekstrakcji - stare wiersze zostaja, wpis w `bledy.txt`; akt, ktory stracil warstwe tekstowa - stare wiersze znikaja, wpis w `bez_tekstu.txt`;
- katalogi `dane/_*` (np. `_wycofane`) nigdy nie sa eksportowane; `--dane DIR` pozwala wskazac inny katalog danych;
- raporty (`raport.txt`, `bez_tekstu.txt`, `bledy.txt`, `chunks_delta.jsonl`) powstaja obok pliku z `--out`.

**Ladowanie `--sync`:** w JEDNEJ transakcji usuwa z bazy `removed`+`changed` (kaskadowo fragmenty), laduje `added`+`changed` (COPY),
przelicza `n_chunks` (niezgodnosc z liczba z pliku = ROLLBACK), a po zatwierdzeniu robi `ANALYZE`. Blad w trakcie = baza bez zmian.
- `--input` przyjmuje wiele plikow (`chunks.jsonl chunks_saos.jsonl` albo `chunks.jsonl chunks_delta.jsonl`); dokument nalezy do pierwszego pliku, w ktorym wystapil.
- `--max-mb N`: NOWE dla bazy dokumenty sa dodawane tylko dopoki `pg_database_size` < N MB (sprawdzane na granicy paczek/dokumentow, wiec mozliwe
  jest przekroczenie o ok. jedna paczke); podmiana `changed` i usuwanie `removed` nie podlegaja limitowi.
- `changed` bez wierszy w plikach wejsciowych (np. skan) jest usuwany z bazy - stary tekst bylby nieaktualny.
- Ponowne uruchomienie tego samego `zmiany.json` jest bezpieczne (idempotentne). `--dry-run` nie laczy sie z baza.
- `--sync` nie laczy sie z `--truncate` ani `--kategorie`.

**Brak `DATABASE_URL`:** komunikat i kod wyjscia **2** (orkiestrator traktuje to jako "krok pominiety"). Adres jest brany ze zmiennej
srodowiskowej, a gdy jej brak - z `.env.local` w korzeniu repo (`--env-file` zmienia sciezke). Wartosc nigdy nie jest wypisywana.

## 7. Testy
```
python -m unittest discover -s pipeline/tests -v
```
Testy eksportu i loadera bez bazy dzialaja zawsze (katalogi tymczasowe, `pipeline/out/` i `dane/` nietkniete). Testy z baza wymagaja
JEDNORAZOWEJ pustej bazy w `PRAWO_TEST_DATABASE_URL` (robia `TRUNCATE`), np. `docker run -d --rm --name prawo-pg -e POSTGRES_PASSWORD=x
-e POSTGRES_DB=t -p 127.0.0.1:55432:5432 postgres:16` i `PRAWO_TEST_DATABASE_URL=postgresql://postgres:x@127.0.0.1:55432/t`.
