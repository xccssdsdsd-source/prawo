# Jak aktualizować dane (dla właściciela)

**Najkrócej:** otwórz ten folder w Claude Code i napisz **„Uaktualnij to wszystko”**. Claude sam sprawdzi, co nowego ukazało się w Dzienniku Ustaw i Monitorze Polskim, pobierze tylko nowości, odświeży bazę i stronę, a na końcu napisze krótkie podsumowanie. Niczego nie musisz klikać ani kopiować.

Bez Claude'a to samo robi jedna komenda w PowerShell, w folderze projektu:

```powershell
cd <folder-projektu>     # np. cd $HOME\Documents\prawo
python aktualizuj.py --dry-run     # tylko plan - niczego nie zmienia
python aktualizuj.py               # właściwa aktualizacja
```

## Co się dzieje po komendzie

Kroki wykonują się po kolei. Jeśli któryś ważny się nie uda, następne się nie uruchamiają (nic się nie psuje, wystarczy potem uruchomić ponownie).

| Krok | Co robi | Zmienia coś na zewnątrz? |
|---|---|---|
| 1. `kopia` | Zapisuje małą kopię zapasową indeksów i plików stanu (kilkanaście MB, 5 ostatnich kopii) w `stan\kopie\`. | nie |
| 2. `dane` | Pyta API Sejmu o wszystkie akty, porównuje z tym, co już masz, i pobiera **tylko nowe lub zmienione**. Akty, które przestały obowiązywać, są **przenoszone** do `dane\_wycofane\` (nie kasowane). | tylko dysk lokalny |
| 3. `zrodla` | Jeśli włączysz dodatkowe źródła (orzeczenia, prawo UE) - odświeża je. Domyślnie śpią. | nie |
| 4. `eksport` | Zamienia tylko zmienione akty na fragmenty tekstu (do wyszukiwania). | nie |
| 5. `info` | Ustawia „Stan danych na dzień ...” i najnowsze akty na stronie. | nie |
| 6. `testy` | Sprawdza, czy kod strony i API nadal działa (tsc + vitest). | nie |
| 7. `baza` | Wprowadza zmiany do bazy Postgres (Neon) w jednej transakcji: albo wszystko, albo nic. Potrzebuje `DATABASE_URL` w pliku `.env.local`. | **tak - baza** |
| 8. `commit` | Zapisuje zmiany strony w git (lokalnie). Wypchnięcie na GitHub dopiero za Twoją zgodą. | lokalnie |
| 9. `wdrozenie` | Wdraża stronę na Vercel - **tylko jeśli to włączysz** (patrz niżej). | **tak - internet** |

Na końcu dostajesz podsumowanie: stan danych na dzień, najnowszy Dz.U. i M.P., ile aktów nowych / zmienionych / wycofanych, co pominięto i dlaczego. Pełny raport leży w `stan\raport_RRRR-MM-DD.md`.

**Ile to trwa.** Sam plan (`--dry-run`) trwa kilka minut (pomiary z 12.10.2026: od ok. 2 do ok. 6 min, zależnie od szybkości API Sejmu). Zwykła aktualizacja, gdy od ostatniej minęło kilka dni, to z reguły kilka minut. Pierwszy właściwy przebieg po zbudowaniu manifestu pobierze jednorazowo brakujące teksty (ok. 1,4-1,9 tys.; dokładną liczbę pokaże plan) - szacunkowo kilkanaście minut do godziny (nie mierzono).

## Pierwsze uruchomienie

Gdy folder `stan\` jeszcze nie istnieje, aktualizacja najpierw tylko **buduje manifest** z tego, co już jest w `dane\` (bez pobierania, kilka sekund) i kończy. Uruchom ją wtedy jeszcze raz - ten drugi przebieg robi właściwą robotę. Claude zrobi to za Ciebie.

## Bezpieczeństwo: co robi się samo, a co tylko za Twoją zgodą

Ustawienia są w pliku `.claude\uaktualnij.config.json`:

| Ustawienie | Domyślnie | Znaczenie |
|---|---|---|
| `auto_load_db` | `true` | wolno zapisać zmiany w bazie (o ile jest `DATABASE_URL`) |
| `auto_commit` | `true` | wolno zapisać zmiany strony w git (lokalnie) |
| `auto_push` | **`false`** | wolno wypchnąć na GitHub |
| `auto_deploy` | **`false`** | wolno wdrożyć stronę na Vercel |
| `backup_before_update` | `true` | kopia zapasowa przed zmianami |
| `baza_max_mb` | `450` | limit rozmiaru bazy dla nowych dokumentów (darmowy Neon ma ok. 500 MB); `null` = bez limitu |

`false` oznacza, że Claude zapyta Cię przed wypchnięciem i wdrożeniem. Odpowiedz „tak”, a zrobi to jednorazowo.

**Uwaga o pushu:** `git push` wypycha **wszystkie** lokalne, niewypchnięte commity z gałęzi, nie tylko commit aktualizacji. Dlatego Claude pokazuje przed pushem listę (`git log @{u}..HEAD --oneline`), a raport wypisuje, co wyszło. Jeśli masz własne, nieprzejrzane commity, sprawdź je przed zgodą.

### Jak włączyć automatyczne wdrażanie

1. Zainstaluj i zaloguj Vercel CLI (raz): `npm i -g vercel`, potem `vercel login`; w folderze `vercel\` wykonaj `vercel` i podłącz projekt (zob. `docs\DEPLOY.md`).
2. W `.claude\uaktualnij.config.json` zmień `"auto_deploy": false` na `"auto_deploy": true`. Analogicznie `auto_push` dla GitHuba (wymaga skonfigurowanego `git remote`).
3. Od tej pory „Uaktualnij to wszystko” kończy się wdrożeniem. Wdrożenie jest **wstrzymywane**, dopóki baza nie ma wszystkich zmian - strona nie poda daty stanu, której baza nie zna.

Wyłączasz tak samo: `false`.

## Gdzie wpisać hasło do bazy

Skopiuj `.env.example` jako `.env.local` i wpisz swój `DATABASE_URL` z panelu Neon (Dashboard > Connect). Plik `.env.local` nie trafia do GitHuba, a skrypty nigdy nie wypisują jego zawartości. Bez niego aktualizacja działa, tylko pomija bazę (zmiany czekają w kolejce i trafią do bazy przy następnym uruchomieniu z hasłem).

## Co zrobić, gdy coś się nie uda

Najczęściej: **uruchom ponownie**. Aktualizacja jest wznawialna - przerwane pobieranie, zerwane połączenie czy zamknięty komputer niczego nie psują, a niezapisane zmiany czekają w `stan\kolejka.json`.

| Komunikat | Co zrobić |
|---|---|
| `ZABLOKOWANO przez zabezpieczenie` | Program odmówił wycofania ponad 3% aktów naraz (zwykle awaria API, nie prawdziwe uchylenie). Dane są nietknięte. Spróbuj później albo poproś Claude'a o zbadanie przyczyny. Nie wymuszaj na ślepo. |
| `Metadane DU/…: nie pobrano (ConnectionError…)` | Chwilowa awaria API Sejmu dla jednego roku. Program celowo pomija wtedy wycofywanie aktów (nic nie jest usuwane). Uruchom ponownie za kilka minut. |
| `BŁĄD na kroku „baza”` | Baza wróciła do poprzedniego stanu. Sprawdź połączenie (Neon bywa uśpiony) i ponów. |
| `brak DATABASE_URL` | Uzupełnij `.env.local`, uruchom `python aktualizuj.py --tylko baza`. |
| `Inna aktualizacja trwa ...` | Poprzednia została przerwana awaryjnie. Jeśli na pewno nic nie działa, usuń plik `stan\aktualizuj.lock` (lub `stan\update.lock`). |
| Polskie znaki wyglądają dziwnie w konsoli | To tylko wyświetlanie w oknie Windows; pliki są poprawne. |

## Jak cofnąć

Nic nie jest kasowane bez śladu. Do wyboru:

- **Akt przeniesiony do `dane\_wycofane\`** - przenieś plik z powrotem do `dane\<kategoria>\`.
- **Indeksy i manifest sprzed aktualizacji** - skopiuj pliki z `stan\kopie\<data>\` w to samo miejsce (`dane\indeks_*.json`, `stan\manifest.json`). Kolejne uruchomienie uzna nowsze akty za do pobrania i naprawi stan.
- **Strona (git)** - `git log` pokazuje commity `Aktualizacja danych: stan na ...`. Cofnięcie: `git revert <numer>`.
- **Strona (Vercel)** - w panelu Vercel > Deployments wybierz poprzednie wdrożenie > Promote to Production.
- **Baza** - zmiany ładują się w transakcji, więc nigdy nie zostaje „pół”. Automatycznej kopii bazy nie robimy (to dziesiątki GB ruchu). Neon umożliwia przywrócenie stanu z przeszłości lub gałąź - zakres zależy od planu, sprawdź w panelu Neon. Alternatywa: przywróć `dane` i `chunks.jsonl` i przeładuj bazę (`docs\DEPLOY.md`).

## Aktualizacja według harmonogramu

Prawo zmienia się codziennie, ale dla większości zastosowań wystarczy **raz w tygodniu**. Trzy sposoby:

1. **Ręcznie z przypomnieniem.** Dodaj w kalendarzu cykliczne wydarzenie „Uaktualnij prawo” (poniedziałek, rano). W Claude Code napisz „Uaktualnij to wszystko”.
2. **Automatycznie w tle (Harmonogram zadań Windows).** Raz w tygodniu uruchamia aktualizację bez wdrażania i bez pytań (komputer musi być włączony). PowerShell jako administrator niepotrzebny:

   ```powershell
   schtasks /Create /SC WEEKLY /D MON /ST 08:00 /TN "Prawo PL aktualizacja" `
     /TR "cmd /c cd /d <PELNA-SCIEZKA-DO-FOLDERU-PROJEKTU> && python aktualizuj.py --bez-wdrozenia >> stan\harmonogram.log 2>&1"
   ```

   Wynik: `stan\raport_RRRR-MM-DD.md` oraz podsumowanie w `stan\harmonogram.log`. Wdrożenie i push zostają na Ciebie (przy `--bez-wdrozenia` nie wykonują się nigdy). Usunięcie: `schtasks /Delete /TN "Prawo PL aktualizacja" /F`.
3. **Co dzień w chmurze (GitHub Actions).** Jeśli w repozytorium jest plik `.github\workflows\dzienna-aktualizacja.yml`, GitHub może sam odświeżać dane i bazę co noc (wymaga sekretu `DATABASE_URL` w ustawieniach repozytorium). Działa na osobnym stanie (`ci_stan\`; lokalny `stan\` to oddzielna sprawa) i sam commituje `data-info.json`. Przed własnym `git push` zrób wtedy `git pull --rebase`. **Żeby nie kończył się błędem, trzeba przed pierwszym pushem:** dodać sekret `DATABASE_URL`, zbudować manifest (`python pipeline\update_data.py --bootstrap --hash --stan ci_stan`) i zatwierdzić `ci_stan\manifest.json`. Pełne kroki: `docs\DEPLOY.md`, sekcja 8a.

### Lokalnie i w chmurze naraz: jedno źródło prawdy

Lokalna aktualizacja (`python aktualizuj.py`: `stan\manifest.json`, `pipeline\out\chunks.jsonl`) i dzienna w chmurze (`ci_daily.py`: `ci_stan\manifest.json`, brak pełnego `chunks.jsonl`) mają **osobne manifesty**. Obie zapisują do tej samej bazy, ale żadna nie widzi zmian drugiej. Zasady:

- **Najprościej wybrać jedną ścieżkę** dla bazy. Jeśli ufasz chmurze, lokalnie możesz używać `python aktualizuj.py --bez-bazy` (odświeża tylko pliki, `chunks.jsonl` i stronę).
- **Gdy działają obie**, synchronizacja bazy jest przyrostowa i idempotentna (usuwa i ładuje ponownie tylko zmienione dokumenty), więc lokalny przebieg po prostu jeszcze raz wykryje to, co zrobiła chmura, i bezpiecznie nadpisze te same dokumenty. Kolejność: `git pull --rebase` (zabiera `ci_stan\manifest.json` i `data-info.json`), potem `python aktualizuj.py`, potem `git push`.
- **Nigdy nie rób pełnego przeładowania bazy** (`load_to_postgres.py` bez `--sync`, z `--truncate`) z lokalnego `chunks.jsonl`, jeśli lokalna aktualizacja nie była uruchomiona tuż przed. Lokalny plik nie zawiera tego, co dodała lub wycofała chmura, a manifest chmury uważa te dokumenty za już załadowane, więc po takim przeładowaniu baza zostałaby nieaktualna do czasu ręcznego naprawienia. Najpierw `python aktualizuj.py`, dopiero potem pełne przeładowanie.
- Dokumenty odrzucone przez limit rozmiaru bazy (`baza_max_mb`) lokalnie wracają do kolejki (`stan\pominiete_limit.json`). W chmurze takiej pamięci nie ma (`ci_stan\` poza manifestem nie jest wersjonowany), więc przy zapełnionej bazie ostrzeżenie widać tylko w logu GitHub Actions.

Przypomnienie o instrukcjach podłączenia (strona `/podlacz.html`): programy AI zmieniają menu co kilka tygodni. Raz na miesiąc napisz Claude'owi „odśwież instrukcje podłączenia” - sprawdzi dokumentację producentów (`ai\SOURCES.md`).

## Baza wiedzy o prawie

Pliki w `vercel\public\wiedza\` (poradniki dla modeli AI, serwowane jako `/wiedza/*.md`) **nie aktualizują się same**, bo każde twierdzenie jest sprawdzone ręcznie z tekstem ustawy. Po każdej aktualizacji Claude uruchamia automatyczną kontrolę (`lookup_article.py --verify-md`): jeśli jakiś przepis zmienił brzmienie, zgłosi to i zaproponuje poprawkę. Co jakiś czas odświeżane są też `nadchodzace-zmiany.md` i `kodeksy-i-glowne-ustawy.md`. Szczegóły: `vercel\public\wiedza\README.md`.

## Dodatkowe źródła (orzeczenia sądów, prawo UE)

Są gotowe, ale wyłączone. Włącza się je w `zrodla\sources.json` (`"enabled": true`) - patrz `zrodla\README.md`. Uwaga: orzeczenia z SAOS wymagają najpierw potwierdzenia warunków z operatorem serwisu i nie zmieszczą się w darmowej bazie Neon; prawo UE (RODO, prawa konsumenta, ok. 44 akty) zajmuje niewiele.

## Gdzie co leży

| Plik / folder | Do czego |
|---|---|
| `aktualizuj.py` | komenda „Uaktualnij to wszystko” |
| `stan\raport_*.md` | raport z każdej aktualizacji |
| `stan\ostatnia_aktualizacja.json` | skrót ostatniego wyniku |
| `stan\kopie\` | kopie zapasowe małych plików |
| `dane\_wycofane\` | akty, które przestały obowiązywać |
| `.claude\uaktualnij.config.json` | Twoje zgody (push, wdrożenie, baza) |
| `.env.local` | hasło do bazy (tworzysz sam z `.env.example`) |
| `CLAUDE.md` | instrukcja dla Claude'a (nie musisz jej czytać) |
