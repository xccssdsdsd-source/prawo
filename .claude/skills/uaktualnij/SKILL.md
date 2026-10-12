---
name: uaktualnij
description: Aktualizuje cały projekt prawa polskiego (dane z Dz.U. i M.P., teksty ujednolicone, fragmenty, baza Postgres, strona i data stanu danych) jednym bezpiecznym, przyrostowym przebiegiem z raportem. Użyj, gdy właściciel mówi "uaktualnij to wszystko", "zaktualizuj", "zaktualizuj dane", "odśwież dane prawa", "odśwież prawo", "sprawdź nowe przepisy", "czy są nowe ustawy", "pobierz nowości", "aktualizacja bazy prawa", "update the law data".
---

# Uaktualnij to wszystko

Pełne zasady, mapa projektu i tabela błędów są w `CLAUDE.md` (sekcje „Zasady bezpieczeństwa” i „Procedura: Uaktualnij to wszystko”). Ten skill to lista kontrolna. Wszystko robi `aktualizuj.py` - nie składaj kroków ręcznie, chyba że przebieg się zatrzymał.

## Kolejność

1. **Plan.** `python aktualizuj.py --dry-run` (kilka minut, 2-6 zależnie od API; niczego nie zmienia). Opisz właścicielowi po polsku 3-6 zdaniami: ile nowych / zmienionych / wycofanych aktów, czy to pierwsze uruchomienie (wtedy powstaje tylko manifest, bez pobierania), które kroki zostaną pominięte (np. brak `DATABASE_URL`), co z commit / push / wdrożeniem wg `.claude/uaktualnij.config.json`.
   - Wynik `ZABLOKOWANY` albo `BŁĄD`: zatrzymaj się i wyjaśnij przyczynę zamiast uruchamiać dalej.
2. **Uruchomienie.** `python aktualizuj.py` (przy długim przebiegu w tle, bez limitu czasu; jest wznawialne). Opcje: `--bez-bazy`, `--bez-wdrozenia`, `--bez-zrodel`, `--bez-testow`, `--tylko KROK`.
   - Pierwsze uruchomienie kończy się na budowie manifestu. Wtedy powtórz krok 1 i 2.
3. **Raport.** Przeczytaj `stan/raport_<data>.md` i `stan/ostatnia_aktualizacja.json`.
4. **Kontrola bazy wiedzy** (po przebiegu, który coś zmienił):
   `python pipeline/tools/lookup_article.py --verify-md vercel/public/wiedza/*.md`
   Błąd = przepis zmienił brzmienie lub zniknął z tekstu ujednoliconego: popraw wpis w `vercel/public/wiedza/` (zasady w `vercel/public/wiedza/README.md`), ustaw `zweryfikowano` w `index.json`. Nie zgaduj brzmienia przepisów - czytaj artykuł przez `lookup_article.py`.
5. **Podsumowanie dla właściciela** (po polsku, krótko): stan danych na dzień (`data_as_of`), najnowszy Dz.U. i M.P., liczba nowych / zmienionych / wycofanych, status bazy i strony, co pominięto i dlaczego, ostrzeżenia, co dalej.
6. **Push i wdrożenie** tylko za zgodą: gdy `auto_push` / `auto_deploy` są `false`, zapytaj raz. Po „tak”: `python aktualizuj.py --tylko commit --zgoda push`, potem `python aktualizuj.py --tylko wdrozenie --zgoda wdrozenie`.

## Zakazy

- Nie wypisuj `DATABASE_URL`, `API_KEY` ani zawartości `.env.local`.
- Nie uruchamiaj `git push`, `vercel`, `rm`, `load_to_postgres.py` (bez `--dry-run`) poza `aktualizuj.py` bez wyraźnej zgody właściciela.
- Nie edytuj `dane/`, `stan/manifest.json` ani `stan/kolejka.json` ręcznie.
- Nie obchodź zabezpieczenia 3% (`--force-removals`) bez ustalenia przyczyny z właścicielem.
- Konsola Windows psuje wyświetlanie polskich znaków - to tylko wyświetlanie. Weryfikuj kody znaków, pliki zapisuj jako UTF-8.
