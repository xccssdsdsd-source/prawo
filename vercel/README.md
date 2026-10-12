# Prawo API (Vercel + Postgres)

Funkcje Vercel (Node 24, TypeScript, bez Next.js) udostępniające polskie przepisy modelom AI: `/api/search`, `/api/article`, `/api/act`, `/api/health`, `/api/mcp`, statyczne `/openapi.json` i `/llms.txt`. Kontrakt: `../docs/SPEC.md`.

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

- **Tryb otwarty/zamknięty:** `API_KEY` jest opcjonalny. Brak/pusty = API publiczne bez klucza (domyślnie; odpowiedzi z `Cache-Control: public, s-maxage=...` – 3600 s dla article/act, 300 s dla search – więc CDN Vercela odciąża bazę). `API_KEY` ustawiony = wymagany Bearer / `x-api-key`, odpowiedzi `private, no-store`. Dotyczy też `/api/mcp`. `/api/health`, `/openapi.json`, `/llms.txt` zawsze publiczne.
- **Ochrona przed nadużyciem:** limit w pamięci instancji per IP (60/min search, 120/min article/act, 600/min mcp (domyślnie; env `MCP_RATE_LIMIT`, bo konektory chmurowe dzielą IP)), nagłówki `X-RateLimit-*`, 429 + `Retry-After`. To best-effort i PER-INSTANCJA (serverless) – docelowo włącz Vercel Firewall / Rate Limiting. Twarde limity: `q` ≤ 300 znaków, `limit` ≤ 20, artykuł ≤ 12 000 znaków.
- **Aktualność danych:** `public/data-info.json` (generowany skryptem) jest wbudowany w funkcje; `/api/health` zwraca `data_as_of` i `data_info`, każda odpowiedź ma nagłówek `X-Data-As-Of`, a search/article/act pole `data_as_of`. Po odświeżeniu danych zrób redeploy.
- Przy otwartym API CORS `*` jest zamierzony; w trybie zamkniętym nie umieszczaj klucza w kodzie front-endu.
- Zapytania są parametryzowane (`$1...`); wartości od użytkownika nigdy nie są sklejane z SQL.
