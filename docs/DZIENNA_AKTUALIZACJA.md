# Dzienna, automatyczna aktualizacja (GitHub Actions)

Raz dziennie GitHub sam uruchamia zwykły skrypt Pythona (`pipeline/ci_daily.py`). **Bez AI, bez kosztów Claude.**

## Co robi
1. `update_data.py --ci` – porównuje API Sejmu z `ci_stan/manifest.json`, pobiera **tylko nowe i zmienione** akty (zwykle kilkadziesiąt dziennie).
2. `export_chunks.py --changed` – dzieli je na artykuły.
3. `load_to_postgres.py --sync` – w bazie Neon usuwa zmienione/wycofane akty i ładuje nowe wersje.
4. `build_data_info.py` – odświeża `vercel/public/data-info.json` oraz daty na stronie.
5. Commit + push `ci_stan/manifest.json` i plików strony → Vercel sam wdraża nową wersję ze świeżą datą „Stan danych na dzień …”.

Commit następuje **dopiero po sukcesie wszystkich kroków**, więc manifest nigdy nie wyprzedza bazy. Przy błędzie nic nie jest zatwierdzane, a następny przebieg powtarza pracę (operacje są idempotentne). Ochrona: jeśli API zawiedzie lub plan wycofania obejmuje >3% aktów, aktualizacja się zatrzymuje (kod 3) bez zmian.

## Jednorazowa konfiguracja
1. **Załaduj bazę w całości u siebie** (komendy w `docs/DEPLOY.md`, krok 3). Manifest startowy `ci_stan/manifest.json` odpowiada stanowi danych z 11.10.2026 – pierwszy przebieg dogoni różnicę (dziesiątki nowych/zmienionych aktów).
2. W repozytorium GitHub: **Settings → Secrets and variables → Actions → New repository secret** → nazwa `DATABASE_URL`, wartość: connection string z Neon.
3. (opcjonalnie) **Variables → New repository variable** → `DB_MAX_MB` (domyślnie 450 = limit rozmiaru bazy dla NOWYCH dokumentów).
4. Wypchnij repozytorium (`git push`), razem z `ci_stan/manifest.json` i `.github/workflows/`.
5. Pierwsze uruchomienie ręcznie: **Actions → Dzienna aktualizacja danych → Run workflow**. Pierwszy przebieg trwa dłużej (ok. 20–30 min): sprawdza ~2000 pozycji, w tym warianty „tekst ujednolicony” starych aktów, których manifest startowy nie znał. Kolejne są szybkie.

Harmonogram: codziennie 03:17 UTC (`cron` w `.github/workflows/dzienna-aktualizacja.yml`). GitHub potrafi opóźnić start. W repozytoriach bez aktywności GitHub wyłącza harmonogram po 60 dniach – commity z aktualizacji liczą się jako aktywność.

## Błędy
Przy błędzie GitHub wysyła maila (domyślnie na adres konta). Log: Actions → ostatni przebieg. Typowe przyczyny:
- `brak sekretu DATABASE_URL` – dodaj sekret (krok 2).
- `brak ci_stan/manifest.json` – wypchnij plik (krok 4).
- kod 3 (`PRZERWANO (bezpieczenstwo danych)`) – API Sejmu zwróciło podejrzanie mało aktów. Zwykle mija samo. Jeśli uchylono masowo prawdziwe akty, uruchom ręcznie z opcją `force_removals`.
- Brak miejsca w bazie – zwiększ plan Neon albo ogranicz `DB_MAX_MB`.

## Uwagi
- Świeżo ogłoszony akt czasem nie ma jeszcze tekstu (API zwraca pustą odpowiedź). Skrypt ponawia pobranie przez 30 dni.
- Lokalne „Uaktualnij to wszystko” używa osobnego stanu (`stan/`, pełny folder `dane/`); nie koliduje z `ci_stan/`.
- Po zmianie reguł klasyfikacji w `kategorie.py` zbuduj manifest ponownie lokalnie: `python pipeline/update_data.py --bootstrap --stan ci_stan`.
