# Tekst jednolity, ujednolicony, zmieniający i pierwotny – różnice i kategorie w API

> **Data weryfikacji: 2026-10-11.** Stan danych: baza Prawo API z dnia 11.10.2026 (przepisy ogłoszone później nie są uwzględnione).
> **To nie jest porada prawna** – to informacja ogólna oparta na tekstach przepisów. Aktualność zawsze sprawdź w ISAP (https://isap.sejm.gov.pl) lub u prawnika.
> Odnośniki w formie `[doc_id art. N]` zostały sprawdzone z tekstem w bazie. **[WO]** = wiedza ogólna, niezweryfikowana w danych – zweryfikuj w ISAP.

## W skrócie

Jedna ustawa występuje w praktyce w kilku „wersjach”: tekst pierwotny (ogłoszony), akty zmieniające, obwieszczenie z tekstem jednolitym oraz tekst ujednolicony z ISAP. Tylko ogłoszone w dzienniku (pierwotny, zmieniające, jednolity) są aktami urzędowymi; tekst ujednolicony jest pomocą informacyjną. W naszej bazie każda wersja ma osobną **kategorię**, a kategoria mówi, jak ufać treści. Najczęściej odpowiadaj na podstawie tekstu `ujednolicone` (doc_id kończy się na `#U`) i sprawdzaj go z najnowszym `jednolite`.

## 1. Cztery rodzaje tekstu

| Rodzaj | Co to jest | Kategoria w API | Charakter |
|---|---|---|---|
| Tekst pierwotny (ogłoszony) | akt w brzmieniu z dnia ogłoszenia w Dz.U./M.P. | `podstawowe` | urzędowy, ale może być nieaktualny po nowelizacjach |
| Akt zmieniający (nowelizacja) | polecenia „w art. X wprowadza się zmiany…” | `zmieniajace` | urzędowy, ale NIE zawiera pełnej treści obowiązującej |
| Tekst jednolity | obwieszczenie z ujednoliconą treścią ustawy lub rozporządzenia, ogłoszone w dzienniku | `jednolite` | urzędowy (obwieszczenie) |
| Tekst ujednolicony | tekst opracowany w ISAP po każdej nowelizacji | `ujednolicone` (`doc_id` z `#U`) | informacyjny, nie źródło prawa |

### Tekst jednolity (urzędowy)

- Marszałek Sejmu ogłasza tekst jednolity ustawy „nie rzadziej niż raz na 12 miesięcy, jeżeli była ona nowelizowana” (ustawa może określić termin ogłoszenia) [DU/2000/718#U art. 16].
- Teksty jednolite aktów innych niż ustawa ogłasza organ właściwy do wydania aktu (np. Prezes Rady Ministrów dla swoich rozporządzeń), również nie rzadziej niż raz na 12 miesięcy, jeśli akt był nowelizowany [DU/2000/718#U art. 16].
- Tekst jednolity ogłasza się „w formie obwieszczenia w dzienniku urzędowym, w którym dany akt normatywny ogłoszono” [DU/2000/718#U art. 16].
- W Dzienniku Ustaw i Monitorze Polskim ogłasza się teksty jednolite aktów wymienionych w tych dziennikach [DU/2000/718#U art. 9, 10].
- Błędy w tekście jednolitym prostuje się obwieszczeniem organu, który ogłosił tekst jednolity [DU/2000/718#U art. 18].
- Nagłówek obwieszczenia mówi, na jakim stanie prawnym oparto tekst i jakie zmiany uwzględniono. Przykład: tekst jednolity Kodeksu cywilnego (Dz.U. 2026 poz. 795, obwieszczenie z 27 maja 2026 r.) uwzględnia stan prawny na dzień 19 maja 2026 r. oraz zmiany wprowadzone m.in. ustawą z 23 stycznia 2026 r. (Dz.U. 2026 poz. 184) [DU/2026/795 ord 1]. Zmiany wprowadzone po tej dacie nie są w tym tekście.

### Tekst ujednolicony (informacyjny)

- Ustawa o ogłaszaniu aktów normatywnych nie przewiduje pojęcia tekstu ujednoliconego – mówi tylko o tekście jednolitym [DU/2000/718#U art. 16]. Tekst ujednolicony to produkt Biura Legislacyjnego Kancelarii Sejmu w ISAP, który ma pomagać w czytaniu prawa. **[WO]** Według pomocy ISAP (potwierdzone tylko w streszczeniu wyszukiwarki, nie w pełnym tekście strony) ISAP nie jest źródłem prawa, a elektroniczne teksty ujednolicone mają charakter informacyjny i pomocniczy – zweryfikuj w ISAP.
- W naszej bazie ujednolicone teksty to PDF-y z ELI/ISAP (`source_url` typu `…/text/U/D19640093Lj.pdf`) zamienione na tekst; pole `is_consolidated` = true dotyczy tylko takich dokumentów. **Pułapka:** dla kategorii `jednolite` pole `is_consolidated` ma wartość false, mimo że to tekst jednolity – decyduje kategoria, nie ta flaga.
- Tekst ujednolicony jest zwykle świeższy niż ostatnie obwieszczenie o tekście jednolitym: ISAP przygotowuje go po kolejnych nowelizacjach. Dla k.p.c. indeks ELI pokazuje datę zmiany rekordu 2026-10-06, a ostatnie obwieszczenie o tekście jednolitym k.p.c. jest z 27 marca 2026 r. (tabela w `kodeksy-i-glowne-ustawy`). Ale: świeżość pliku ≠ stan prawny, więc dopisuj zastrzeżenie.
- Podstawa opracowania bywa zapisana na końcu pierwszego artykułu: „Opracowano na podstawie: t.j. Dz. U. z 2025 r. poz. 1691.” (k.p.a.) [DU/1960/168#U art. 1]; analogicznie dla k.c. „t.j. Dz. U. z 2026 r. poz. 795” [DU/1964/93#U art. 5].

## 2. Jak to się ma do doc_id w naszej bazie

- Akty ze statusem „akt posiada tekst jednolity” (np. k.c., k.p.c., k.k., k.r.o., k.p. – sprawdzono 2026-10-11) nie są w bazie jako samodzielny dokument `DU/1964/93`; wszystkie dokumenty bazowe mają status „obowiązujący”; w bazie jest ich tekst ujednolicony `DU/1964/93#U` (zapytanie o sam `DU/1964/93` zwraca brak dokumentu). Z kolei obwieszczenie z tekstem jednolitym ma własny doc_id bez `#U`, np. `DU/2026/795`.
- Dla wielu aktów istnieją **trzy równoległe widoki**: `DU/1964/296#U` (tekst ujednolicony aktu pierwotnego), `DU/2026/468` (tekst z obwieszczenia o tekście jednolitym, kategoria `jednolite`) i `DU/2026/468#U` (tekst ujednolicony powiązany z obwieszczeniem). Porównanie k.p.c. (2026-10-11): oba teksty ujednolicone mają ten sam zestaw 1950 artykułów i różnią się w 3 z nich – w praktyce to duplikat, więc wyniki wyszukiwania mogą się powtarzać.
- Tekst z obwieszczenia (`jednolite`) jest wyciągnięty z PDF Dziennika Ustaw i zawiera śmieci typograficzne: nagłówki stron („Dziennik Ustaw – 10 – Poz. 795”) i przypisy wklejone w treść artykułów [DU/2026/795 art. 60]. W tekście ujednoliconym ten sam artykuł jest czysty [DU/1964/93#U art. 60]. Dlatego do cytowania wygodniej brać `#U`, a obwieszczenie traktować jako potwierdzenie urzędowego źródła.
- Numeracja z indeksem górnym bywa różna w różnych widokach: w k.p. tekst ujednolicony ma `1011`, `1012` (spłaszczone), a tekst jednolity `101[1]`, `101[2]` (porównanie własne 2026-10-11). Jeśli artykułu z indeksem nie ma, spróbuj drugiego zapisu (`29[1]` i `291`) i drugiego widoku.
- Akty bez tekstu jednolitego: rozporządzenia i wiele ustaw ma w bazie tylko tekst `podstawowe` (brzmienie z ogłoszenia). Zmiany tych aktów szukaj w kategorii `zmieniajace` (np. „zmianie rozporządzenia … <tytuł>”). W bazie wszystkie ujednolicone teksty to dokumenty typu `#U`.

## 3. Jak klasyfikuje dokumenty nasz potok danych

Kategorię nadaje heurystyka na podstawie typu i tytułu dokumentu z ELI (plik `kategorie.py`), a nie ręczna ocena:

- typ „Orzeczenie” → `orzeczenie` (w bazie to wyroki TK ogłoszone w Dz.U.),
- typy „Umowa międzynarodowa”, „Konwencja”, „Protokół”, „Układ”, „Porozumienie”, „Traktat” → `umowa`,
- obwieszczenie „w sprawie ogłoszenia jednolitego tekstu” → `jednolite`; obwieszczenie o utracie mocy, sprostowaniu lub wynikach → `inne`,
- tytuł zaczynający się od ustawy/rozporządzenia/dekretu/uchwały z wyrażeniem typu o zmianie ustawy…, zmieniające… → `zmieniajace`,
- wszystko inne → `podstawowe`,
- `ujednolicone` pochodzą z osobnego indeksu tekstów ujednoliconych ISAP (`#U`).

Ponieważ to heurystyka, bywają pomyłki, a ustawa o zmianie… może jednocześnie zawierać nowe, samodzielne przepisy (np. art. 3 i 4 aktu zmieniającego: przepis przejściowy i termin wejścia w życie) [DU/2026/184 art. 3, 4]. Czytaj treść, nie sam szyld kategorii.

## 4. Którą wersję wybrać – praktyczny przepis

1. Pytanie o treść obowiązującego przepisu ustawy/kodeksu → `ELI#U` (np. `DU/1964/93#U`). Potwierdź w najnowszym `jednolite`, czy brak oczywistej rozbieżności.
2. Rozporządzenie z tekstem jednolitym (np. ZTP: Dz.U. 2026 poz. 300) → obwieszczenie `jednolite` (tu nie ma wersji `#U`) [DU/2026/300 ord 1].
3. Rozporządzenie lub ustawa bez tekstu jednolitego → `podstawowe` + wyszukaj akty `zmieniajace`; zaznacz niepewność.
4. Pytanie od kiedy przepis obowiązuje i co się stanie ze sprawami w toku → akt zmieniający (przepisy przejściowe i wejścia w życie): np. art. 3 i 4 ustawy z 23.01.2026 r. [DU/2026/184 art. 3, 4].
5. Pytanie o historię zmian jednego przepisu → akty zmieniające + przypisy w tekście ujednoliconym (przypisy wskazują m.in. utratę mocy przepisu na podstawie obwieszczenia Prezesa TK) [DU/1964/93#U art. 448].

## 5. Daty i aktualność

- `changeDate` w ELI/indeksach to data ostatniej zmiany rekordu w ELI – wskazuje, że plik odświeżono, nie na jaki dzień zawiera stan prawny.
- Stan prawny tekstu jednolitego jest w obwieszczeniu (jw. dla k.c.: 19 maja 2026 r.). Tekst ujednolicony nie ma w treści jawnej daty stanu; opieraj się na podstawie opracowania z przypisu (jeśli jest) i na dacie `changeDate`.
- Cała baza ma stan na dzień `data_as_of` (obecnie 2026-10-11). Przepisy ogłoszone później, a także wchodzące w życie później niż `data_as_of`, mogą nie być w tekście ujednoliconym albo mogą być oznaczone jako przyszłe brzmienie w nawiasach `< >` (patrz `jak-czytac-akt-prawny`, pkt 4).
- Czasem w tym samym tekście są dwa brzmienia przepisu (obecne i przyszłe) – zawsze pytaj, na jaki dzień ma być odpowiedź.

## 6. Szybka tabela decyzyjna

| Pytanie użytkownika | Gdzie szukać | Czego nie robić |
|---|---|---|
| „Co mówi art. X kodeksu?” | `ELI#U` → `get_article` | nie cytuj `zmieniajace` jako obowiązującej treści |
| „Czy ten przepis się zmienił w 2026 r.?” | akty `zmieniajace` z 2026 + przypisy w `#U` | nie zakładaj, że tekst jednolity jest najnowszy |
| „Czy przepis już obowiązuje?” | akt zmieniający: art. o wejściu w życie + data ogłoszenia z nagłówka | nie używaj `announcement_date` jako daty ogłoszenia |
| „Rozporządzenie wykonawcze do ustawy” | `podstawowe`/`jednolite` + `zmieniajace` | nie zakładaj, że rozporządzenie zachowało moc po zmianie ustawy |
