# Wdrożenie krok po kroku

Efekt: własne API prawa polskiego w internecie (Vercel + baza Neon), do którego podłączysz Claude, ChatGPT itd. Zajmuje ok. 1–2 godzin (głównie ładowanie danych).

## 0. Potrzebujesz
- Konta (darmowe): Neon (neon.tech), Vercel (vercel.com).
- Zainstalowane: Python 3.10+, Node.js (lokalnie do testów wystarczy 20+; wdrożenie na Vercel wymaga Node 24.x, ustawionego w `vercel/package.json`), Git (opcjonalnie).
- Folder projektu `prawo` z pobranymi danymi w `dane\`.

## 1. Baza Neon
1. Zaloguj się na neon.tech > Create project (region: Frankfurt, najbliżej Polski).
2. Skopiuj **connection string** (Dashboard > Connect), wygląda jak `postgresql://user:haslo@ep-xxx.eu-central-1.aws.neon.tech/neondb?sslmode=require`. To jest `DATABASE_URL`. Traktuj jak hasło.
3. Rozszerzenia `unaccent` i `pg_trgm` tworzy schemat automatycznie (krok 3). Jeśli zgłosi błąd uprawnień: SQL Editor w Neon > uruchom `create extension if not exists unaccent; create extension if not exists pg_trgm;`.

## 2. Przygotowanie danych (pipeline)
W PowerShell, w folderze projektu:
```powershell
cd <folder-projektu>        # np. cd $HOME\Documents\prawo
pip install -r pipeline\requirements.txt
python pipeline\export_chunks.py
```
Powstanie `pipeline\out\chunks.jsonl`. Skrypt wypisze statystyki (liczba aktów, fragmentów, znaków zastępczych). Pełny eksport trwa ok. 9 minut.
Stan na 11.10.2026: eksport był już wykonany (22 113 aktów, 423 149 fragmentów, ok. 956 MB, 0 znaków zastępczych), więc ten krok możesz pominąć, dopóki nie pobierzesz nowych danych.

**Rozmiar a plan Neon.** Czysty tekst to ok. 680 MB, a w bazie z indeksami szacunkowo 1,5–1,7 GB. Darmowy plan (~0,5 GB) mieści praktycznie tylko kategorię `ujednolicone` (1586 z 1688 aktów, w tym Kodeks cywilny i Kodeks pracy). Żeby załadować wszystko, potrzebny jest płatny plan Neon. Szacunek rozmiaru (`--overhead 2.5`) jest założeniem; sprawdź go po pierwszym ładowaniu w wyniku `pg_database_size`. Podgląd bez bazy: `python pipeline\load_to_postgres.py --dry-run --max-mb 450`.

## 3. Załadowanie do Postgresa
```powershell
$env:DATABASE_URL = "postgresql://...twoj-connection-string..."
python pipeline\load_to_postgres.py --schema --max-mb 450
```
- `--schema` tworzy tabele i indeksy; `--max-mb 450` zatrzymuje ładowanie przed limitem darmowego Neon (~0,5 GB).
- Ładowanie idzie w kolejności ważności: najpierw kategorie `ujednolicone`, `jednolite`, potem pozostałe. Sprawdź `python pipeline\load_to_postgres.py --help` dla opcji (np. wybór kategorii).
- Można je przerwać i uruchomić ponownie.

Po załadowaniu (i po każdym odświeżeniu danych) trzeba też zaktualizować datę stanu danych: `python pipeline\build_data_info.py` odświeża `vercel\public\data-info.json` (pole `data_as_of`, najnowsze akty) i daty w `index.html` oraz `podlacz.html`; potem wdrożenie (`vercel --prod`), inaczej API poda nieaktualną datę. **Przy późniejszych aktualizacjach robi to za Ciebie `python aktualizuj.py`** (sekcja „Aktualizacja danych po wdrożeniu” niżej).

## 4. Klucz API (opcjonalny)
API jest domyślnie **publiczne i otwarte** – nie musisz ustawiać żadnego klucza. Tryb zamknięty włącza się tylko wtedy, gdy ustawisz zmienną `API_KEY`; wtedy zapytania bez klucza dostają 401. Aby go użyć, wygeneruj losowy klucz (PowerShell):
```powershell
-join ((48..57)+(97..122) | Get-Random -Count 40 | % {[char]$_})
```
Zapisz go w menedżerze haseł. To `API_KEY` – każdy, kto go ma, korzysta z Twojego API.

## 5. Wdrożenie na Vercel
```powershell
npm i -g vercel
cd vercel
vercel login
vercel                       # pierwsze wdrożenie; odpowiedz na pytania, nazwa np. prawo-api
vercel env add DATABASE_URL  # wklej connection string; zaznacz Production (i Preview)
vercel env add API_KEY       # OPCJONALNIE (tryb zamknięty); pomiń, by API było otwarte
vercel --prod                # wdrożenie produkcyjne; zanotuj adres https://xxx.vercel.app
```
Zmienne środowiskowe działają dopiero po ponownym wdrożeniu (`vercel --prod`).

## 6. Test
```powershell
curl https://TWOJA-DOMENA.vercel.app/api/health
curl "https://TWOJA-DOMENA.vercel.app/api/search?q=zadośćuczynienie%20śmierć"
curl "https://TWOJA-DOMENA.vercel.app/api/article?id=DU/1964/93&art=446"
```
`/api/health` powinno zwrócić `ok: true`, liczbę dokumentów i fragmentów oraz `data_as_of`. W PowerShell użyj `curl.exe` zamiast `curl`.
Tryb otwarty: zapytania bez klucza działają. Tryb zamknięty (ustawiony `API_KEY`): dodaj `-H "Authorization: Bearer KLUCZ"`; bez klucza `/api/search` zwraca 401.

## 6a. Publikacja kodu na GitHub
Repozytorium już istnieje: lokalna gałąź `main` jest powiązana z `origin` (sprawdź `git remote -v`; obecnie `https://github.com/xccssdsdsd-source/prawo.git`). Wypchnięcie robisz Ty (albo Claude za Twoją zgodą):
1. Sprawdź, że nic wrażliwego nie jest śledzone. Pierwsza komenda powinna nic nie wypisać, druga może pokazać tylko wzory `.env.example` (celowo śledzone, bez haseł):
```powershell
git ls-files dane pipeline/out stan
git ls-files | findstr /i /r "\.sqlite \.jsonl$ \.env"
```
2. Zobacz, co wyjdzie: `git log @{u}..HEAD --oneline`. **`git push` wypycha wszystkie lokalne, niewypchnięte commity z gałęzi, nie tylko ostatni**, więc przejrzyj tę listę przed pushem.
3. `git pull --rebase` (dzienna aktualizacja z GitHub Actions, sekcja 8a, sama commituje `data-info.json`), potem `git push`.

Gdybyś zakładał repozytorium od zera: utwórz na github.com **puste** repozytorium (bez README/licencji), `git remote add origin https://github.com/<TWOJ-LOGIN>/<nazwa>.git`, `git push -u origin main` i podmień adres repozytorium w `README.md` oraz `vercel/public/index.html`.

Katalog `dane\` i plik `pipeline\out\chunks.jsonl` (ok. 956 MB, ponad limit 100 MB GitHub) są w `.gitignore` i nie mogą trafić do repozytorium. Opcjonalnie podłącz repozytorium do Vercel (Import Project, Root Directory: `vercel`) dla wdrożeń po każdym pushu.

Prywatność: metadane commitów zawierają adres e-mail autora (`git log -1 --format=%ae`) i po upublicznieniu repozytorium będą widoczne. Jeśli nie chcesz go ujawniać, ustaw przed kolejnymi commitami adres noreply z GitHuba: `git config user.email "<ID>+<login>@users.noreply.github.com"`. Historii nie przepisuj bez przemyślenia.

## 7. Podłączenie modeli
- **Najłatwiej:** otwórz `https://TWOJA-DOMENA.vercel.app/podlacz.html` - kreator krok po kroku dla 37 klientów AI (Claude, ChatGPT, Gemini, Cursor, VS Code ...) z przyciskiem „Testuj połączenie”.
- Claude Code / Desktop / Cursor: `ai\mcp\README.md`
- Custom GPT: `ai\openai-actions\INSTRUCTIONS.md`; Gemini: `ai\gemini\INSTRUCTIONS.md`
- Skill dla Claude: `ai\claude-skill\SKILL.md`; ogólne instrukcje: `ai\AGENTS.md`, `ai\SYSTEM_PROMPT.md`.
- Baza wiedzy o prawie (poradniki dla modeli): `https://TWOJA-DOMENA.vercel.app/wiedza/index.json` oraz `/llms.txt`; pliki w `vercel\public\wiedza\`.

## 8. Aktualizacja danych po wdrożeniu
Gdy wszystko stoi, nie powtarzasz kroków 2-5. Otwórz folder w Claude Code i napisz **„Uaktualnij to wszystko”** (albo uruchom `python aktualizuj.py`). Komenda przyrostowo pobiera nowości z API Sejmu, eksportuje tylko zmienione akty, synchronizuje bazę (`load_to_postgres.py --sync`, w transakcji), odświeża `data-info.json` i na końcu - zgodnie z `.claude\uaktualnij.config.json` - robi commit, push i wdrożenie.
- Hasło do bazy: skopiuj `.env.example` jako `.env.local` i wpisz `DATABASE_URL`. Bez niego krok bazy jest pomijany, a zmiany czekają w `stan\kolejka.json`.
- Domyślnie `auto_push` i `auto_deploy` są `false`: wypchnięcie na GitHub i `vercel --prod` dzieją się dopiero po Twojej zgodzie. Włączenie: ustaw `true` w `.claude\uaktualnij.config.json` (wdrożenie wymaga zainstalowanego i zalogowanego Vercel CLI, krok 5).
- Wdrożenie jest wstrzymywane, dopóki baza nie ma wszystkich zmian (strona nie poda daty stanu, której baza nie zna).
- Limit rozmiaru: `baza_max_mb` (domyślnie 450 dla darmowego Neon). Na planie płatnym ustaw `null`.
- Opis dla właściciela, cofanie zmian i harmonogram: `docs\AKTUALIZACJA.md`.

### 8a. Dzienna aktualizacja w chmurze (GitHub Actions) - opcjonalna

Plik `.github/workflows/dzienna-aktualizacja.yml` co noc (03:17 UTC) odświeża dane i bazę, a potem commituje `data-info.json` (Vercel wdraża zmianę sam, jeśli repozytorium jest do niego podłączone). Działa na **osobnym stanie** `ci_stan/` (w repozytorium jest tylko `ci_stan/manifest.json`). Lokalny `stan/`, którego używa `python aktualizuj.py`, to osobny stan. Oba tryby zapisują `data-info.json`, więc przed lokalnym pushem rób `git pull --rebase`.

Dopóki poniższe warunki nie są spełnione, workflow kończy się błędem (czerwony, z mailem o awarii). **Przed pierwszym pushem wykonaj kroki 1-3 albo usuń sekcję `schedule` z pliku workflow** (zostanie ręczne uruchamianie `workflow_dispatch`):
1. GitHub > Settings > Secrets and variables > Actions: dodaj sekret `DATABASE_URL` (opcjonalnie zmienną `DB_MAX_MB`, domyślnie 450).
2. Zbuduj manifest CI z sumami kontrolnymi (lokalnie, z danymi w `dane/`, bez pobierania, kilka minut): `python pipeline/update_data.py --bootstrap --hash --stan ci_stan`.
3. Zatwierdź go: `git add ci_stan/manifest.json`, `git commit` (ok. 9 MB; reszta `ci_stan/` jest w `.gitignore`).

Manifest CI powinien odpowiadać stanowi bazy. Jeśli po lokalnej aktualizacji (`aktualizuj.py`) baza dostała nowsze dane niż manifest CI, kolejny przebieg CI zrobi część pracy drugi raz (jest idempotentny, więc to tylko zbędny ruch). Wtedy odśwież manifest tak jak w kroku 2 i zatwierdź.

## Rozwiązywanie problemów
| Objaw | Przyczyna / rozwiązanie |
|---|---|
| `/api/health`: `db: false` | zły `DATABASE_URL` (brak `?sslmode=require`, literówka); dodaj ponownie i `vercel --prod` |
| 401 | tryb zamknięty: zły/brak nagłówka `Authorization: Bearer KLUCZ`. W trybie otwarym 401 nie powinno się zdarzać – usuń `API_KEY` z Vercel i wdróż ponownie |
| Puste wyniki, `chunks: 0` | dane nie załadowane (krok 3) |
| `extension "unaccent" ... permission` | uruchom `create extension` w SQL Editor Neon |
| Ładowanie: `could not extend file` / pełny dysk | przekroczono limit Neon; zmniejsz `--max-mb` lub usuń słabsze kategorie, albo plan płatny |
| Pierwsze zapytanie wolne | zimny start Neon/Vercel; ponów |
| `pip` / `python` nie znaleziono | zainstaluj Python z python.org, zaznacz "Add to PATH" |
| Polskie znaki w curl źle | użyj `curl.exe -G --data-urlencode "q=..."` |

## Koszty i limity
- Neon Free: ok. 0,5 GB danych, baza usypia przy bezczynności (pierwsze zapytanie wolniejsze). Dlatego ładuj najpierw `ujednolicone`, `jednolite`; pełny zbiór może wymagać planu płatnego (kilka–kilkanaście USD/mies.).
- Vercel Hobby: darmowy do użytku niekomercyjnego, z limitami funkcji (czas wykonania, liczba wywołań). Do większego ruchu – plan Pro.
- Koszty zmieniają się; sprawdź aktualne cenniki.

## Bezpieczeństwo i ochrona przed nadużyciem (otwarte API)
- `DATABASE_URL` (i ewentualny `API_KEY`) trzymaj tylko w zmiennych środowiskowych Vercel i menedżerze haseł. Nie umieszczaj w kodzie, repozytorium, czacie, zrzutach ekranu.
- **Otwarte API = ryzyko nadużycia** (boty, masowe zapytania zużywające limity Neon i Vercel). Zalecenia:
  - Vercel: włącz **Firewall / Rate Limiting** (Project > Firewall; reguła limitu zapytań na IP dla ścieżki `/api/*`) i Bot Protection.
  - Neon: ustaw **autosuspend** (scale to zero), limit **compute** (max CU) oraz **spending limit** / alerty kosztów w ustawieniach rozliczeń; na planie darmowym wyczerpanie limitu zatrzyma bazę zamiast generować rachunek.
  - Vercel: włącz **Spend Management** (limit wydatków) i obserwuj Usage.
  - Jeśli nadużycia się pojawią, przełącz na tryb zamknięty: ustaw `API_KEY` i wdróż ponownie (`vercel --prod`). Klucz wyciekł? `vercel env rm API_KEY`, dodaj nowy, `vercel --prod`.
- Po każdym odświeżeniu danych `data_as_of` musi być prawdziwe: robi to `python aktualizuj.py` (krok `info`), a wdrożenie następuje za Twoją zgodą (sekcja 8). Ręcznie: `python pipeline\build_data_info.py` i `vercel --prod`.
- Dane są publiczne (akty prawne z ISAP/Sejm), bez danych osobowych użytkowników. Zapytania użytkowników mogą jednak trafiać do logów Vercel.
- W trybie zamkniętym do Custom GPT / connectorów dawaj klucz tylko w polu uwierzytelniania.
- Modele korzystające z API mają obowiązek podawać „Stan danych na dzień <data_as_of>” (zob. `ai\AGENTS.md`).

## Zastrzeżenie prawne
Projekt dostarcza informacje o przepisach pochodzące z publicznych źródeł; mogą zawierać błędy, braki lub być nieaktualne (np. brak przepisów przejściowych). Nie jest to oficjalne źródło prawa ani porada prawna. Jedynie akty opublikowane w Dzienniku Ustaw i Monitorze Polskim w formie urzędowej są wiążące. Aktualność weryfikuj w ISAP (isap.sejm.gov.pl) lub u prawnika.
