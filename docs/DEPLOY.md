# Wdrożenie krok po kroku

Efekt: własne API prawa polskiego w internecie (Vercel + baza Neon), do którego podłączysz Claude, ChatGPT itd. Zajmuje ok. 1–2 godzin (głównie ładowanie danych).

## 0. Potrzebujesz
- Konta (darmowe): Neon (neon.tech), Vercel (vercel.com).
- Zainstalowane: Python 3.10+, Node.js 20+, Git (opcjonalnie).
- Folder projektu `prawo` z pobranymi danymi w `dane\`.

## 1. Baza Neon
1. Zaloguj się na neon.tech > Create project (region: Frankfurt, najbliżej Polski).
2. Skopiuj **connection string** (Dashboard > Connect), wygląda jak `postgresql://user:haslo@ep-xxx.eu-central-1.aws.neon.tech/neondb?sslmode=require`. To jest `DATABASE_URL`. Traktuj jak hasło.
3. Rozszerzenia `unaccent` i `pg_trgm` tworzy schemat automatycznie (krok 3). Jeśli zgłosi błąd uprawnień: SQL Editor w Neon > uruchom `create extension if not exists unaccent; create extension if not exists pg_trgm;`.

## 2. Przygotowanie danych (pipeline)
W PowerShell, w folderze projektu:
```powershell
cd C:\Users\kajet\Documents\prawo
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

Po każdym odświeżeniu danych uruchom też:
```powershell
python pipeline\build_data_info.py
```
Aktualizuje `vercel\public\data-info.json` (pole `data_as_of`, najnowsze akty). Następnie wdróż ponownie (`vercel --prod`), inaczej API poda nieaktualną datę stanu danych.

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
Repozytorium lokalne jest już zainicjowane (gałąź `main`, pierwszy commit). Wypchnięcie robisz Ty:
1. Na github.com utwórz **puste** publiczne repozytorium (bez README/licencji), np. `prawo-pl`.
2. Sprawdź, że nic wrażliwego nie jest śledzone: `git ls-files | findstr /i "dane\ .env out\"` nie powinno nic zwrócić.
3. W katalogu projektu:
```powershell
git remote add origin https://github.com/TWOJ-LOGIN-GITHUB/prawo-pl.git
git push -u origin main
```
(`TWOJ-LOGIN-GITHUB` to placeholder.) Katalog `dane\` i plik `pipeline\out\chunks.jsonl` (ok. 956 MB, ponad limit 100 MB GitHub) są w `.gitignore` i nie powinny trafić do repozytorium. Opcjonalnie podłącz repozytorium do Vercel (Import Project, Root Directory: `vercel`) dla wdrożeń po każdym pushu.

## 7. Podłączenie modeli
- Claude Code / Desktop / Cursor: `ai\mcp\README.md`
- Custom GPT / Gemini: `ai\openai-actions\INSTRUCTIONS.md`
- Skill dla Claude: `ai\claude-skill\SKILL.md`; ogólne instrukcje: `ai\AGENTS.md`, `ai\SYSTEM_PROMPT.md`.

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
- Po każdym odświeżeniu danych uruchom `python pipeline\build_data_info.py` i wdróż ponownie, by `data_as_of` było prawdziwe.
- Dane są publiczne (akty prawne z ISAP/Sejm), bez danych osobowych użytkowników. Zapytania użytkowników mogą jednak trafiać do logów Vercel.
- W trybie zamkniętym do Custom GPT / connectorów dawaj klucz tylko w polu uwierzytelniania.
- Modele korzystające z API mają obowiązek podawać „Stan danych na dzień <data_as_of>” (zob. `ai\AGENTS.md`).

## Zastrzeżenie prawne
Projekt dostarcza informacje o przepisach pochodzące z publicznych źródeł; mogą zawierać błędy, braki lub być nieaktualne (np. brak przepisów przejściowych). Nie jest to oficjalne źródło prawa ani porada prawna. Jedynie akty opublikowane w Dzienniku Ustaw i Monitorze Polskim w formie urzędowej są wiążące. Aktualność weryfikuj w ISAP (isap.sejm.gov.pl) lub u prawnika.
