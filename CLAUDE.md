# CLAUDE.md - instrukcja dla Claude Code w projekcie „Prawo PL”

Ten plik czytasz na starcie każdej sesji w tym folderze. Właściciel (nie-programista) otwiera folder i mówi **„Uaktualnij to wszystko”**. Masz wtedy sam, bezpiecznie i przyrostowo odświeżyć dane, indeks, bazę i stronę oraz podać czytelne podsumowanie po polsku. Odpowiadaj po polsku, prosto, bez żargonu.

## 1. Co to jest

Otwarte API prawa polskiego dla modeli AI (Dz.U., M.P., teksty ujednolicone z ISAP; opcjonalnie orzecznictwo i prawo UE). Dane z API ELI Sejmu (`api.sejm.gov.pl/eli`) -> pliki w `dane/` -> fragmenty (`chunks.jsonl`) -> Postgres (Neon) -> funkcje Vercel (`/api/search`, `/api/article`, `/api/act`, `/api/mcp`). Model **ma obowiązek podawać „Stan danych na dzień <data_as_of>”**. To nie jest porada prawna.

## 2. Mapa projektu

| Ścieżka | Co to jest | Jak się aktualizuje |
|---|---|---|
| `aktualizuj.py` | orkiestrator „Uaktualnij to wszystko” | **to uruchamiasz** |
| `pipeline/update_data.py` | przyrostowe odświeżanie `dane/` + `stan/manifest.json` | przez `aktualizuj.py` (krok `dane`) |
| `pipeline/export_chunks.py` | PDF/HTML -> fragmenty `pipeline/out/chunks.jsonl` (`--changed` = tylko zmiany) | krok `eksport` |
| `pipeline/load_to_postgres.py` | ładowanie do Postgresa (`--sync` = tylko zmiany, w transakcji) | krok `baza` |
| `pipeline/build_data_info.py` | `vercel/public/data-info.json` + daty w `index.html` i `podlacz.html` | krok `info` |
| `pipeline/tools/lookup_article.py` | tylko odczyt: brzmienie artykułu, `--verify-md`, `--upcoming` | ręcznie po aktualizacji |
| `pipeline/schema.sql`, `pipeline/README_LOAD.md` | schemat bazy, opis ładowania | rzadko |
| `dane/` (**gigabajty, poza repo**) | pobrane akty; `indeks_*.json`; `_wycofane/` (akty, które przestały obowiązywać - przeniesione, nie skasowane) | tylko przez `update_data.py` |
| `stan/` (**poza repo**) | `manifest.json`, `zmiany.json`, `kolejka.json`, `raport_*.md`, `ostatnia_aktualizacja.json`, `kopie/`, logi | tylko przez skrypty |
| `zrodla/` | rejestr źródeł `sources.json` + uśpione fetchery: `saos/` (wyroki), `eurlex/` (prawo UE) | włączasz flagą `enabled` |
| `vercel/` | strona i API (TypeScript): `api/`, `lib/`, `public/` | testy w kroku `testy`, wdrożenie w kroku `wdrozenie` |
| `vercel/public/wiedza/` | baza wiedzy (14 plików md + `index.json`) | **ręcznie weryfikowana**, patrz pkt 8 |
| `vercel/public/podlacz.html` | kreator podłączenia do 37 klientów AI | **ręcznie weryfikowany** co kilka tygodni, patrz pkt 9 |
| `ai/` | instrukcje dla modeli (system prompt, MCP, Gemini, Actions), `ai/SOURCES.md` | ręcznie, patrz pkt 9 |
| `docs/` | `SPEC.md` (kontrakty danych), `UPDATE_SPEC.md` (kontrakty aktualizacji), `DEPLOY.md`, `AKTUALIZACJA.md` (dla właściciela) | ręcznie |
| `.claude/` | skill `uaktualnij`, komenda `/uaktualnij`, `settings.json` (allowlista), `uaktualnij.config.json` (zgody) | ręcznie |
| `tests/` | testy orkiestratora (`python -m unittest discover -s tests`) | - |
| `prawnik.py`, `pobierz_prawo.py`, `pobierz_wiecej.py`, `kategorie.py`, `przeklasyfikuj.py` | starsze skrypty (legacy) - **nie ruszaj** | - |
| `.env.local` (**poza repo, nie czytaj**) | `DATABASE_URL=...` do synchronizacji bazy | tylko właściciel |

Kategorie aktów (`kategorie.py`): `ujednolicone` > `jednolite` > `podstawowe` > `zmieniajace` (+ `mp`, `umowa`, `orzeczenie`, `inne`; dodatkowo `wyrok`, `ue` ze źródeł dodatkowych). Identyfikatory: `DU/2024/1984`, `MP/2026/977`, tekst ujednolicony `DU/1964/93#U`. Szczegóły: `docs/SPEC.md`, `docs/UPDATE_SPEC.md`.

## 3. Zasady bezpieczeństwa (obowiązują zawsze)

1. **Nie wypisuj sekretów.** `DATABASE_URL`, `API_KEY` i zawartość `.env.local` nigdy w odpowiedziach, logach, raportach, commitach. Nie czytaj `.env.local` (blokuje to też `.claude/settings.json`). `aktualizuj.py` sam czyta sekrety i filtruje je z wyjścia.
2. **Nie wypychaj na GitHub i nie wdrażaj na Vercel bez zgody.** Zgoda = `auto_push` / `auto_deploy` w `.claude/uaktualnij.config.json` albo wyraźne „tak” właściciela w tej rozmowie. Domyślnie oba są `false`: zapytaj raz, krótko.
3. **Najpierw `--dry-run`.** Zawsze pokaż plan przed właściwą aktualizacją.
4. **Nie ruszaj ręcznie** `dane/`, `stan/manifest.json`, `stan/kolejka.json`, `pipeline/out/chunks.jsonl`. Nie kasuj `dane/_wycofane/`. Nie uruchamiaj `rm`/`Remove-Item` na tych katalogach.
5. **Uprawnienia w `.claude/settings.json` to druga linia obrony** (`ask` dla `--zgoda`, `--force-removals`, `--tylko commit|wdrozenie|baza`, `update_data.py --full`; `deny` dla plików `.env*`). Nie obchodź ich przez inne polecenie ani nie dodawaj szerszych reguł `allow`.
6. **Nie obchodź zabezpieczenia 3%.** Gdy `update_data.py` odmawia wycofania ponad 3% aktów (kod 3, „ZABLOKOWANY”), to zwykle awaria API, nie prawdziwe wycofanie. Zbadaj przyczynę, powiedz właścicielowi; `--force-removals` tylko za jego zgodą.
7. **Nie uruchamiaj pełnych pobrań** (`update_data.py --full`, pełny `export_chunks.py`, `saos` za `--since 1990`) bez zgody - trwają godzinami.
8. **Nie dopisuj przepisów z pamięci.** Treść artykułów tylko z `lookup_article.py` / API. W bazie wiedzy zero zmyślonych numerów artykułów.
9. **Nie edytuj cudzych, starszych skryptów** (lista „legacy” w mapie).
10. Zmiany tylko w tym folderze. Commity: tylko to, co robi `aktualizuj.py` (3 pliki strony) albo na prośbę właściciela; nie używaj `git add -A`.

## 4. Procedura: Uaktualnij to wszystko

**Krok 0 - orientacja (10 s).** `git status --short` (zapamiętaj, co właściciel miał niezatwierdzone - nie mieszaj tego z aktualizacją). Sprawdź `stan/ostatnia_aktualizacja.json`, jeśli istnieje (kiedy ostatni raz i z jakim wynikiem). Jeśli `stan/aktualizuj.lock` istnieje, a nic nie działa, patrz pkt 10.

**Krok 1 - plan.** `python aktualizuj.py --dry-run` (kilka minut: 2-6, zależnie od szybkości API; odpytuje API, niczego nie zmienia; na świeżym klonie bez `stan/` pokazuje plan pierwszego uruchomienia). Opisz właścicielowi 3-6 zdaniami:
- ile nowych aktów, ile do sprawdzenia (zmiana daty), ile do wycofania, ile bez zmian;
- czy to pierwsze uruchomienie (powstanie tylko manifest, bez pobierania, potem drugi przebieg);
- co będzie pominięte i dlaczego (np. brak `DATABASE_URL` -> baza; `auto_push=false` -> push; źródła uśpione);
- jeśli wycofań jest dużo (kilkanaście i więcej) - podaj przykłady z powodami z wyjścia planu.
Jeśli plan kończy się `ZABLOKOWANY` lub `BŁĄD`, zatrzymaj się i wyjaśnij (pkt 10), nie uruchamiaj dalej.

**Krok 2 - właściwa aktualizacja.** `python aktualizuj.py`. Kroki: `kopia -> dane -> zrodla -> eksport -> info -> testy -> baza -> commit -> wdrozenie`. Pierwszy przebieg po bootstrapie pobiera kilkanaście setek brakujących tekstów (ok. 1,4-1,9 tys.; dokładną liczbę pokazuje plan; kilkanaście minut - godzina); uruchom w tle z dużym limitem czasu i obserwuj wyjście. Opcje: `--bez-bazy`, `--bez-wdrozenia`, `--bez-zrodel`, `--bez-testow`, `--tylko KROK`, `--lata 2026`, `--max-akty N` (ostrożna próba). Pierwsze uruchomienie kończy się po zbudowaniu manifestu: powtórz krok 1 i 2.

**Krok 3 - raport.** Przeczytaj `stan/raport_<dzisiejsza data>.md` (tabela kroków, ostrzeżenia, błędy, „Co dalej”) i `stan/ostatnia_aktualizacja.json`.

**Krok 4 - kontrole po aktualizacji (gdy przebieg coś zmienił).**
- Baza wiedzy: `python pipeline/tools/lookup_article.py --verify-md vercel/public/wiedza/*.md` (w PowerShell: `--verify-md (Get-ChildItem vercel/public/wiedza/*.md | % FullName)`). Błąd = przepis zmienił brzmienie lub zniknął: popraw wpis (pkt 8).
- `vercel/public/data-info.json` ma nowe `data_as_of` (robi to krok `info`).
- Jeśli doszły nowe zapowiedzi zmian: `python pipeline/tools/lookup_article.py --upcoming --out stan/nadchodzace.txt` i odśwież `wiedza/nadchodzace-zmiany.md` (pkt 8) - tylko gdy właściciel chce lub plik ma ponad 2 tygodnie.

**Krok 5 - podsumowanie dla właściciela** (po polsku, krótko, w tej kolejności):
1. wynik (OK / OK z ostrzeżeniami / zatrzymane i dlaczego);
2. **stan danych na dzień** (`data_as_of`) oraz najnowszy Dz.U. i M.P.;
3. liczba aktów: nowych / zmienionych / wycofanych (+ źródła dodatkowe, jeśli włączone);
4. baza: zsynchronizowana czy pominięta (i dlaczego), czy limit rozmiaru nie odciął nowych dokumentów;
5. strona: czy jest commit, czy wypchnięto, czy wdrożono;
6. co pominięto i dlaczego; ostrzeżenia z raportu;
7. co dalej (np. „napisz tak, a wypchnę i wdrożę”).

**Krok 6 - push i wdrożenie (tylko za zgodą).** Gdy `auto_push` / `auto_deploy` są `false`, zapytaj raz. Przed pushem pokaż właścicielowi `git log @{u}..HEAD --oneline`: zwykły `git push` wypycha **wszystkie** niewypchnięte commity z gałęzi (także te, których właściciel nie przejrzał), nie tylko commit aktualizacji (`aktualizuj.py` wypisuje tę listę w raporcie). Po „tak”:
`python aktualizuj.py --tylko commit --zgoda push`, potem `python aktualizuj.py --tylko wdrozenie --zgoda wdrozenie`. Wdrożenie jest wstrzymywane, dopóki baza nie zawiera wszystkich zmian (strona nie może podać daty stanu, której baza nie ma).

## 5. Jak działa aktualizacja (żebyś wiedział, co robisz)

- **Przyrostowo.** `update_data.py` porównuje metadane z API z `stan/manifest.json`. Nowe akty pobiera, przy zmianie `changeDate` pobiera ponownie i porównuje sha256 (sama zmiana daty bez zmiany treści to nie „zmiana”). Akty, które przestały obowiązywać, przenosi do `dane/_wycofane/` (nie kasuje).
- **Kolejka zmian** (`stan/kolejka.json`): co jeszcze nie trafiło do eksportu i do bazy. Dzięki niej przerwany lub nieudany przebieg niczego nie gubi: kolejny przebieg dokończy zaległości, nawet jeśli API nie pokaże już tych samych zmian.
- **`data_as_of`** = data zapisu indeksów `dane/indeks_*.json` (tak liczy `build_data_info.py`). Gdy przebieg był pełny i bez błędów, `aktualizuj.py` odnawia znacznik czasu indeksów, żeby „brak nowości” też oznaczał „sprawdzone dzisiaj”. Przebieg częściowy (`--lata`, `--max-akty`, błędy pobierania) tej daty **nie** przesuwa.
- **Kopia** przed zmianami: tylko małe pliki (indeksy, `stan/*.json`, `data-info.json`, `raport.txt`) do `stan/kopie/<data>/`, 5 ostatnich. Gigabajtów nie kopiujemy: `dane/` odtwarza się z API, a `chunks.jsonl` pełnym eksportem.
- **Baza**: `--sync` w jednej transakcji (błąd = ROLLBACK). Limit rozmiaru `baza_max_mb` (domyślnie 450, darmowy Neon): nowe dokumenty ponad limit są pomijane (raport o tym mówi). Płatny plan: ustaw `baza_max_mb` na `null` w configu.
- **Dzienna aktualizacja w GitHub Actions** (jeśli w repo jest `.github/workflows/dzienna-aktualizacja.yml`) działa na osobnym stanie (`ci_stan/`, lokalny `stan/` to oddzielna sprawa) i sama commituje `data-info.json`. Przed lokalnym `git push` zrób `git pull --rebase`, żeby nie rozjechać `data-info.json`. Workflow wymaga sekretu `DATABASE_URL` w GitHubie i zatwierdzonego `ci_stan/manifest.json` z sumami kontrolnymi (`python pipeline/update_data.py --bootstrap --hash --stan ci_stan`, potem `git add ci_stan/manifest.json`); bez tego codziennie kończy się błędem. Kroki: `docs/DEPLOY.md`, sekcja 8a.

## 6. Konfiguracja zgód: `.claude/uaktualnij.config.json`

| Klucz | Domyślnie | Znaczenie |
|---|---|---|
| `auto_load_db` | `true` | wolno synchronizować bazę (wymaga `DATABASE_URL`) |
| `auto_commit` | `true` | wolno zrobić lokalny commit 3 plików strony |
| `auto_push` | `false` | wolno wypchnąć na GitHub |
| `auto_deploy` | `false` | wolno wdrożyć na Vercel (`vercel --prod`) |
| `backup_before_update` | `true` | kopia małych plików przed zmianami |
| `baza_max_mb` | `450` | limit rozmiaru bazy dla NOWYCH dokumentów (`null` = bez limitu) |
| `kopie_zachowaj` | `5` | ile kopii trzymać |
| `commit_trailer` | wiersz `Co-Authored-By` | dopisek do commitów (pusty = brak) |

Wartość inna niż `true`/`false` w kluczach `auto_*` jest traktowana jako `false`. Jednorazowa zgoda w rozmowie: `--zgoda baza|commit|push|wdrozenie`. **Nie zmieniaj tego pliku na prośbę „ułatw sobie”** - tylko gdy właściciel wprost każe włączyć auto-wdrażanie.

## 7. Źródła dodatkowe (orzecznictwo, prawo UE)

Rejestr: `zrodla/sources.json`. Aktywne: `eli-du`, `eli-mp`, `isap-ujednolicone` (obsługuje `update_data.py`). Uśpione: `saos` (wyroki SN, sądów administracyjnych, TK, KIO), `eurlex` (44 akty UE po polsku). Jak włączyć:
1. Przeczytaj `zrodla/README.md` (licencja, limity, rozmiar). **SAOS: `robots.txt` zabrania `/api/` - najpierw potwierdzenie operatora, nie włączaj sam.** Darmowy Neon nie pomieści SAOS.
2. Test próbki: `python zrodla/tests/live_check.py` (nic nie rusza `stan/` ani `pipeline/out/`).
3. W `sources.json` ustaw `"enabled": true` (i `"status": "aktywne"`) **dopiero po zgodzie właściciela**.
4. Od następnego „Uaktualnij to wszystko” krok `zrodla` uruchomi `fetch.py` źródła, a jego zmiany (`stan/zmiany_<id>.json`) trafią do kolejki bazy. Wyłączenie = `"enabled": false` (dane w bazie zostają).
Nowe źródło: `zrodla/README.md`, sekcja „Jak dodać nowe źródło”. Rozpoznane, ale niedostępne źródła (TK, SN, NSA, Portal Orzeczeń, RCL): `zrodla/niedostepne.json`.

## 8. Baza wiedzy `vercel/public/wiedza/` - co automatyczne, co ręczne

- **Automatyczne:** nic nie jest przepisywane samo. `aktualizuj.py` nie zmienia plików md.
- **Weryfikowane maszynowo (po każdej aktualizacji):** `lookup_article.py --verify-md` sprawdza każdy odnośnik `[DU/1964/93#U art. 118]` i cytat w „…” z tekstem w `chunks.jsonl`. Wyniku nie ignoruj.
- **Odświeżane ręcznie (przez Ciebie, za zgodą właściciela):** `nadchodzace-zmiany.md` (tabela i liczby z `--upcoming`), `kodeksy-i-glowne-ustawy.md` (nowe obwieszczenia), `gdzie-szukac-dalej.md` (adresy i status portali), przykłady z konkretnych rekordów. Pełna lista i zasady rzetelności: `vercel/public/wiedza/README.md` - **przeczytaj przed edycją**. Oznaczenie `[WO]` = wiedza ogólna, niezweryfikowana w danych; nie zamieniaj go na twierdzenie bez odnośnika.
- Po przeglądzie ustaw `zweryfikowano` w `wiedza/index.json` i datę w nagłówku pliku. Nowy temat = nowy `<slug>.md` + wpis w `index.json`.

## 9. Instrukcje podłączenia do klientów AI (`podlacz.html`, `ai/`)

Interfejsy Claude, ChatGPT, Gemini, Cursora itd. zmieniają się co kilka tygodni. Dane `podlacz.html` oparto na dokumentacji sprawdzonej 2026-10-11 (stała `VERIFIED` w skrypcie na dole pliku). To **nie jest** część zwykłej aktualizacji danych. Gdy `VERIFIED` jest starsze niż ok. 30 dni albo właściciel mówi „odśwież instrukcje podłączenia”: zaproponuj przegląd i, po zgodzie, wykonaj procedurę z `ai/SOURCES.md` (WebFetch dokumentacji, zmiana tylko tego, co faktycznie się zmieniło, `python pipeline/build_data_info.py`, `node --check` skryptu strony). Nie dopisuj twierdzeń, których nie widzisz w dokumentacji.

## 10. Błędy i wznawialność

Przebieg jest **wznawialny**: nic nie trzeba cofać ani czyścić; po usunięciu przyczyny uruchom `python aktualizuj.py` jeszcze raz.

| Objaw | Co to znaczy / co robić |
|---|---|
| `ZABLOKOWANO ... zabezpieczenie` (kod 3) | `update_data` odmówił wycofania > 3% aktów, dane nietknięte. Zwykle awaria lub zmiana API Sejmu. Sprawdź `stan/plan_dry_run.json` / log, spróbuj później. `--force-removals` tylko za zgodą właściciela. |
| `BŁĄD na kroku „dane”` | Sieć/API. Ponów po chwili (są ponowienia z backoffem). Przerwane pobieranie wznawia się samo. |
| Ostrzeżenie `Metadane DU/2025: nie pobrano (…ConnectionError…)` | Przejściowa awaria API Sejmu dla danego roku. Faza wycofywania jest wtedy celowo pomijana (bezpieczne zachowanie), nic nie jest usuwane. Wystarczy ponowić po kilku minutach; to nie błąd w danych. |
| `Inna aktualizacja trwa ...` (blokada) | `stan/aktualizuj.lock` lub `stan/update.lock`. Sprawdź, czy proces `python` naprawdę działa; jeśli nie, zapytaj właściciela i usuń plik blokady (przeterminowuje się po 3-6 h). |
| `brak pipeline/out/chunks.jsonl` | Tryb przyrostowy potrzebuje pełnego eksportu (ok. 9 min): `python pipeline/export_chunks.py` (za zgodą). |
| `baza ... brak DATABASE_URL` | Krok pominięty, zmiany czekają w `stan/kolejka.json`. Właściciel wpisuje `DATABASE_URL` do `.env.local` (wzór: `.env.example`); potem `python aktualizuj.py --tylko baza`. |
| `BŁĄD na kroku „baza”` | Transakcja cofnięta, baza bez zmian, kolejka zachowana. Sprawdź połączenie (Neon uśpiony? zły URL?), ponów. |
| `BŁĄD na kroku „testy”` | Tsc/vitest nie przeszły: nic nie jest commitowane ani wdrażane. Pokaż błąd właścicielowi; nie wyłączaj testów na stałe. `--bez-testow` tylko jednorazowo i za zgodą. |
| `nowe dokumenty NIE trafiły do bazy z powodu limitu` | Baza osiągnęła `baza_max_mb`. Powiedz o tym wprost. Rozwiązanie: płatny plan Neon + `baza_max_mb: null`, potem pełne ładowanie brakujących kategorii (`docs/DEPLOY.md`). |
| Ostrzeżenie „Wdrożenie wstrzymane: najpierw zsynchronizuj bazę” | Strona nie zostanie wdrożona z datą stanu, której baza nie ma. Napraw bazę, potem `--tylko wdrozenie --zgoda wdrozenie`. |
| SAOS: „usługa niedostępna (kod 3)” | Przerwa techniczna SAOS; dane zapisane zostają, następny przebieg wznowi. |

## 11. Windows i kodowanie

- Konsola Windows (zwłaszcza cp1250/cp852) **psuje wyświetlanie polskich znaków** (`?`, krzaki), choć dane i pliki są poprawnym UTF-8. To tylko wyświetlanie. Nie „naprawiaj” danych na tej podstawie.
- Weryfikuj poprawność na poziomie kodów: `python -c "print(ascii(open('plik', encoding='utf-8').read()[:80]))"`. Treść artykułów czytaj przez `lookup_article.py --out plik.txt` i `Read`.
- Pliki zapisuj jako **UTF-8 bez BOM**. Skrypty projektu same przełączają stdout na UTF-8 (`aktualizuj.py` ustawia `PYTHONUTF8=1` dla podprocesów). W razie potrzeby: `$env:PYTHONUTF8 = "1"` (PowerShell).
- `aktualizuj.py` używa `sys.executable`: nie zakłada aktywnego środowiska wirtualnego. W bash używaj ścieżek z ukośnikami `/`, w PowerShell można `\`. Przy długich komendach ustawiaj timeouty; przebiegi aktualizacji uruchamiaj w tle.
- W PowerShell używaj `curl.exe` zamiast `curl`.

## 12. Testy i weryfikacja zmian w kodzie

```
python -m unittest discover -s tests                   # orkiestrator (atrapy podprocesów, bez sieci)
python -m unittest discover -s pipeline/tests          # eksport/ładowanie, update_data (część wymaga PRAWO_TEST_DATABASE_URL, bez niej pomijane)
python -m unittest discover -s zrodla/tests            # źródła dodatkowe (mock)
cd vercel; npm run typecheck; npm test                 # tsc + vitest (przez aktualizuj.py: krok `testy`)
```

Po zmianie `aktualizuj.py` zawsze uruchom `python -m unittest discover -s tests` i `python aktualizuj.py --dry-run`; dry-run nie może niczego zmienić (sprawdź `git status` i czasy modyfikacji `dane/indeks_*.json` przed/po).

Dla właściciela: `docs/AKTUALIZACJA.md` (co się dzieje po komendzie, jak cofnąć, harmonogram), `docs/DEPLOY.md` (wdrożenie od zera), `README.md`.
