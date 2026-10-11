# Prawo API (Vercel + Postgres)

Funkcje Vercel (Node 20, TypeScript, bez Next.js) udostępniające polskie przepisy modelom AI: `/api/search`, `/api/article`, `/api/act`, `/api/health`, `/api/mcp`, statyczne `/openapi.json` i `/llms.txt`. Kontrakt: `../docs/SPEC.md`.

## Wdrożenie krok po kroku

1. **Baza Postgres (Neon).** Załóż projekt na neon.tech, region możliwie blisko Frankfurtu (`aws-eu-central-1`). Skopiuj connection string (`postgresql://...?sslmode=require`).
2. **Schemat i dane.** Załaduj `../pipeline/schema.sql` (wymaga rozszerzeń `unaccent` i `pg_trgm`), potem dane z `pipeline/` (loader ładujący `chunks.jsonl`). Szczegóły: `../docs/DEPLOY.md`.
3. **Klucz API.** Wygeneruj losowy: `node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"`.
4. **Lokalnie (opcjonalnie).** `cd vercel && npm install && cp .env.example .env`, uzupełnij `DATABASE_URL` i `API_KEY`, uruchom `npx vercel dev`.
5. **Vercel.** `npm i -g vercel`, w katalogu `vercel/` wykonaj `vercel login` i `vercel link`. (Przy imporcie z Git ustaw *Root Directory* = `vercel`.)
6. **Zmienne środowiskowe:** `vercel env add DATABASE_URL production` oraz `vercel env add API_KEY production`.
7. **Deploy:** `vercel --prod`. Region funkcji: `fra1` (w `vercel.json`).
8. **Sprawdzenie:**
   ```
   curl https://TWOJA-DOMENA/api/health
   curl -H "Authorization: Bearer $API_KEY" "https://TWOJA-DOMENA/api/search?q=art.%20445%20kodeks%20cywilny"
   curl -H "x-api-key: $API_KEY" "https://TWOJA-DOMENA/api/article?id=DU/1964/93&art=445"
   ```
9. **Podłączenie modeli.**
   - ChatGPT Actions: importuj `https://TWOJA-DOMENA/openapi.json`, uwierzytelnianie *API Key → Bearer*.
   - Claude / inne klienty MCP: URL `https://TWOJA-DOMENA/api/mcp` z nagłówkiem `Authorization: Bearer <API_KEY>`.
   - Inne modele: wskaż `https://TWOJA-DOMENA/llms.txt`.

## Testy

```
npm run typecheck
npm test
```

Testy jednostkowe (vitest) obejmują `lib/query.ts`, `lib/auth.ts`, `lib/warnings.ts`. Zapytania SQL (`lib/law.ts`) przeszły kontrolę składni parserem Postgresa, ale nie były uruchamiane na żywej bazie.

## Uwagi

- `/api/health`, `/openapi.json`, `/llms.txt` są publiczne; reszta wymaga klucza (brak `API_KEY` w env = odmowa wszystkiego).
- CORS `*` jest bezpieczny, bo dostęp chroni klucz; nie umieszczaj klucza w kodzie front-endu.
- Zapytania są parametryzowane (`$1...`); wartości od użytkownika nigdy nie są sklejane z SQL.
