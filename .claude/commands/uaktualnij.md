---
description: Uaktualnij to wszystko - przyrostowa aktualizacja danych prawa, bazy i strony (z raportem)
argument-hint: "[opcjonalnie: tylko plan | bez bazy | bez wdrozenia]"
---

Wykonaj procedurę „Uaktualnij to wszystko” z pliku `CLAUDE.md` (sekcja „Procedura: Uaktualnij to wszystko”) albo ze skilla `uaktualnij`.

Dodatkowe wskazówki od właściciela: $ARGUMENTS

Skrót:

1. `python aktualizuj.py --dry-run` i krótki opis planu po polsku (ile nowych / zmienionych / wycofanych, co zostanie pominięte).
2. Jeśli plan jest sensowny i wskazówki nie mówią „tylko plan”: `python aktualizuj.py` (dopisz `--bez-bazy` / `--bez-wdrozenia`, jeśli o to prosił właściciel).
3. Przeczytaj `stan/raport_<dzisiejsza data>.md`, uruchom kontrolę bazy wiedzy (`--verify-md`) i podsumuj: stan danych (`data_as_of`), najnowszy Dz.U. i M.P., liczba zmian, co pominięto i dlaczego.
4. Nie wypychaj na GitHub i nie wdrażaj bez zgody (chyba że `.claude/uaktualnij.config.json` pozwala: `auto_push`, `auto_deploy`). Nigdy nie wypisuj `DATABASE_URL` ani `API_KEY`.
