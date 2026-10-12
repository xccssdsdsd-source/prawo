# SPEC – Prawo API dla modeli AI (Vercel + Postgres)

Wspólna umowa między częściami projektu. Każdy agent trzyma się swojego katalogu i tej specyfikacji.

## Układ katalogów (kto co pisze)
- `pipeline/` – przetwarzanie danych: ekstrakcja tekstu, dzielenie na artykuły, eksport JSONL, ładowanie do Postgresa, źródła dodatkowe.
- `vercel/` – aplikacja Vercel (TypeScript, Node 24.x na Vercel - lokalnie do testów wystarczy Node 20+, Vercel Functions w `vercel/api/*.ts`), `vercel/lib/*.ts`, `vercel/public/*`.
- `ai/` – instrukcje dla modeli: `AGENTS.md`, `SYSTEM_PROMPT.md`, `claude-skill/SKILL.md`, `openai-actions/INSTRUCTIONS.md`, `mcp/README.md`.
- `docs/` – dokumentacja dla człowieka (`DEPLOY.md`), ta specyfikacja.
- Dane źródłowe: `dane/<kategoria>/…` (tylko do odczytu). Metadane: `dane/indeks_obowiazujacych.json`, `dane/indeks_mp.json`, `dane/indeks_ujednolicone.json`.
  Nazwy plików: `DU_<rok>_<poz>.(html|pdf)`, `MP_<rok>_<poz>.*`, `U-DU_<rok>_<poz>.pdf` (tekst ujednolicony).
- NIE modyfikuj: `prawnik.py`, `pobierz_*.py`, `kategorie.py`, `indeks.sqlite*`, `dane/`.

## Identyfikatory
- `eli` = `DU/1964/93` (wydawca/rok/pozycja).
- `doc_id` = `eli` albo `eli#U` dla tekstu ujednoliconego (np. `DU/1964/93#U`). W URL-ach i parametrach `#` kodować jako `%23`; API przyjmuje też `variant=U` jako osobny parametr.
- `kategoria`: `ujednolicone | jednolite | podstawowe | zmieniajace | mp | orzeczenie | umowa | inne | wyrok | ue`.

## Format `pipeline/out/chunks.jsonl` (jedna linia = jeden fragment)
```json
{"doc_id":"DU/1964/93#U","eli":"DU/1964/93","kategoria":"ujednolicone","publisher":"DU","year":1964,"pos":93,
 "title":"Ustawa z dnia 23 kwietnia 1964 r. – Kodeks cywilny","display_address":"Dz.U. 1964 nr 16 poz. 93",
 "announcement_date":"1964-05-18","status":"obowiązujący","is_consolidated":true,
 "source_url":"https://api.sejm.gov.pl/eli/acts/DU/1964/93/text/U/D19640093Lj.pdf",
 "ord":445,"article":"445","heading":"Księga trzecia … > Tytuł VI","text":"Art. 445. § 1. W wypadkach …"}
```
- `article`: numer artykułu jako string (`"445"`, `"46[1]"`), `null` dla części wstępnej/nagłówków/aktów bez artykułów.
- Akty bez struktury „Art.” dzielone na fragmenty ~1500–2500 znaków (`article=null`, rosnące `ord`).
- Fragment nie dłuższy niż ~6000 znaków (dłuższe artykuły dzielić po paragrafach `§`, zachowując `article`).
- Plik UTF-8, bez znaków zastępczych U+FFFD (chunker ma je zliczać i raportować).

## Schemat Postgresa (`pipeline/schema.sql`)
```sql
create extension if not exists unaccent;
create extension if not exists pg_trgm;
create table documents(
  doc_id text primary key, eli text not null, kategoria text not null, publisher text, year int, pos int,
  title text not null, display_address text, announcement_date date, status text,
  is_consolidated boolean default false, source_url text, n_chunks int default 0);
create table chunks(
  id bigserial primary key, doc_id text not null references documents(doc_id) on delete cascade,
  ord int not null, article text, heading text, text text not null,
  tsv tsvector generated always as (to_tsvector('simple', unaccent(coalesce(heading,'')||' '||text))) stored);
create index chunks_tsv on chunks using gin(tsv);
create index chunks_doc on chunks(doc_id, ord);
create index chunks_art on chunks(doc_id, article);
create index documents_title_trgm on documents using gin(title gin_trgm_ops);
create index documents_eli on documents(eli);
```
Zapytania: `to_tsquery('simple', unaccent(...))` z prefiksami `słowo:*` (przybliżony stemming polski: ucięcie 2 końcowych liter słów >6 znaków, 1 litery dla >4 – jak `rdzen()` w `prawnik.py`), tokeny łączone `&`. Ranking `ts_rank_cd`, premia dla `ujednolicone`/`jednolite`/`podstawowe`; domyślnie bez `orzeczenie`, `umowa`, `inne`.

## API (Vercel Functions, wszystko JSON UTF-8, CORS `*`)
Auth: nagłówek `Authorization: Bearer <API_KEY>` lub `x-api-key`. Zmienna `API_KEY` w env; brak/zły klucz → 401. `/api/health`, `/openapi.json`, `/llms.txt` publiczne. Zmienna `DATABASE_URL` (Postgres, `@neondatabase/serverless`).

| Endpoint | Parametry | Zwraca |
|---|---|---|
| `GET /api/search` | `q` (wymagane), `kategoria`, `act` (eli), `limit` (1–20, domyślnie 8) | `{query, count, results:[{doc_id, eli, title, display_address, kategoria, is_consolidated, article, heading, snippet, score, source_url, warnings:[]}]}` |
| `GET /api/article` | `id` (eli lub doc_id), `art` (np. `445`), `variant` (`U`, opcjonalnie) | `{doc_id, title, display_address, article, heading, text, source_url, warnings}` – gdy wariant nieokreślony, preferuj `#U`, potem sam `eli` |
| `GET /api/act` | `id`, `variant`, `include_toc=1` | metadane + `articles:[{article, heading}]` |
| `GET /api/health` | – | `{ok, db, documents, chunks, version}` |
| `ALL /api/mcp` | – | serwer MCP (Streamable HTTP, JSON-RPC 2.0): narzędzia `search_law`, `get_article`, `get_act`; te same dane co REST |
| `GET /openapi.json` | – | OpenAPI 3.1 (statyczny plik w `vercel/public/openapi.json`) |
| `GET /llms.txt` | – | instrukcja dla modeli (kopia `ai/AGENTS.md` w skrócie) |

Każdy wynik ma `warnings` (np. `"Tekst w brzmieniu z dnia ogłoszenia – nie jest tekstem ujednoliconym; sprawdź ISAP."`, `"Orzeczenie TK – nie jest przepisem."`). Błędy: `{error:{code,message}}` + właściwy status HTTP. Treść artykułu obcinana do 12 000 znaków z flagą `truncated`.

## Zasady dla modeli (ma się odzwierciedlić w `ai/`)
1. Zawsze cytuj: `display_address`, numer artykułu, kategorię i `source_url`.
2. Preferuj `ujednolicone`, potem `jednolite`; ostrzegaj, gdy źródłem jest akt zmieniający lub brzmienie z dnia ogłoszenia.
3. Nie wymyślaj numerów artykułów – używaj `get_article` do weryfikacji.
4. To nie jest porada prawna; aktualność weryfikować w ISAP.
5. Zakres: Dz.U. + M.P. obowiązujące (+ wyroki/UE jeśli załadowane); brak wyniku ≠ brak przepisu.
