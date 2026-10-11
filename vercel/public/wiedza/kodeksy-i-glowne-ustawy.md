# Kodeksy i główne ustawy – adresy publikacyjne, ELI i doc_id w bazie

> **Data weryfikacji: 2026-10-11.** Stan danych: baza Prawo API z dnia 11.10.2026 (przepisy ogłoszone później nie są uwzględnione).
> **To nie jest porada prawna** – to informacja ogólna oparta na tekstach przepisów. Aktualność zawsze sprawdź w ISAP (https://isap.sejm.gov.pl) lub u prawnika.
> Odnośniki w formie `[doc_id art. N]` zostały sprawdzone z tekstem w bazie. **[WO]** = wiedza ogólna, niezweryfikowana w danych – zweryfikuj w ISAP.
> Tabele poniżej wygenerowano z `dane/indeks_ujednolicone.json`, `dane/indeks_obowiazujacych.json` i `pipeline/out/chunks.jsonl` (każdy doc_id istnieje w bazie). Po aktualizacji danych przejrzyj je ponownie – zob. pkt 5.

## W skrócie

Aby pobrać przepis z kodeksu, użyj `doc_id` z kolumny „tekst ujednolicony” (kończy się na `#U`) w wywołaniu `get_article` (`id` = `DU/1964/93`, `art` = `118`, ewentualnie `variant=U`). Kolumna „Najnowszy tekst jednolity” wskazuje obwieszczenie ogłoszone w Dzienniku Ustaw – urzędowe potwierdzenie treści (patrz `teksty-jednolite-ujednolicone-zmieniajace`).

## 1. Jak czytać tabele

- **Adres publikacyjny** (`display_address`) to oznaczenie aktu pierwotnego w Dzienniku Ustaw: rok ogłoszenia i pozycja (starsze akty mają też numer: „nr 16 poz. 93”).
- **ELI** (`eli`) to techniczny identyfikator `DU/<rok>/<poz>`; `doc_id` to `eli` albo `eli#U` (tekst ujednolicony). W URL znak `#` zapisujemy jako `%23`.
- **Zmiana rekordu w ELI** to pole `changeDate` z indeksu: data ostatniej zmiany rekordu w systemie ELI. Nie jest to data stanu prawnego tekstu – służy tylko do porównania świeżości plików.
- **Najnowszy tekst jednolity** to obwieszczenie (kategoria `jednolite`) o najpóźniejszej dacie w bazie. Tekst ujednolicony `#U` jest zwykle świeższy niż ostatnie obwieszczenie, bo ISAP opracowuje go po każdej nowelizacji; obwieszczenie jest za to źródłem urzędowym.
- Akty o statusie „akt posiada tekst jednolity” nie są w bazie jako samodzielne dokumenty bez `#U` (np. `DU/1964/93` nie istnieje w bazie, istnieje `DU/1964/93#U`).
- **Skróty** w kolumnie „Skrót” są zwyczajowe (nie ustawowe) **[WO]**. Kolumna `–` oznacza brak powszechnie przyjętego skrótu.

## 2. Tabela: kodeksy i główne ustawy

| Nazwa aktu | Skrót (zwyczajowy) | Akt podstawowy: adres publikacyjny / ELI | doc_id tekstu ujednoliconego | Zmiana rekordu w ELI | Najnowszy tekst jednolity (obwieszczenie) w bazie |
|---|---|---|---|---|---|
| **Konstytucja i podstawowe kodeksy** | | | | | |
| Konstytucja Rzeczypospolitej Polskiej | Konstytucja | Dz.U. 1997 nr 78 poz. 483 / `DU/1997/483` | `DU/1997/483#U` | 2026-09-28 | – |
| Kodeks cywilny | k.c. | Dz.U. 1964 nr 16 poz. 93 / `DU/1964/93` | `DU/1964/93#U` | 2026-06-25 | Dz.U. 2026 poz. 795 (`DU/2026/795`) |
| Kodeks postępowania cywilnego | k.p.c. | Dz.U. 1964 nr 43 poz. 296 / `DU/1964/296` | `DU/1964/296#U` | 2026-10-06 | Dz.U. 2026 poz. 468 (`DU/2026/468`) |
| Kodeks rodzinny i opiekuńczy | k.r.o. | Dz.U. 1964 nr 9 poz. 59 / `DU/1964/59` | `DU/1964/59#U` | 2026-07-10 | Dz.U. 2026 poz. 236 (`DU/2026/236`) |
| Kodeks pracy | k.p. | Dz.U. 1974 nr 24 poz. 141 / `DU/1974/141` | `DU/1974/141#U` | 2026-09-25 | Dz.U. 2026 poz. 1245 (`DU/2026/1245`) |
| Kodeks karny | k.k. | Dz.U. 1997 nr 88 poz. 553 / `DU/1997/553` | `DU/1997/553#U` | 2026-08-28 | Dz.U. 2025 poz. 383 (`DU/2025/383`) |
| Kodeks postępowania karnego | k.p.k. | Dz.U. 1997 nr 89 poz. 555 / `DU/1997/555` | `DU/1997/555#U` | 2026-07-17 | Dz.U. 2026 poz. 490 (`DU/2026/490`) |
| Kodeks karny wykonawczy | k.k.w. | Dz.U. 1997 nr 90 poz. 557 / `DU/1997/557` | `DU/1997/557#U` | 2026-10-08 | Dz.U. 2026 poz. 1307 (`DU/2026/1307`) |
| Kodeks karny skarbowy | k.k.s. | Dz.U. 1999 nr 83 poz. 930 / `DU/1999/930` | `DU/1999/930#U` | 2026-10-08 | Dz.U. 2025 poz. 633 (`DU/2025/633`) |
| Kodeks wykroczeń | k.w. | Dz.U. 1971 nr 12 poz. 114 / `DU/1971/114` | `DU/1971/114#U` | 2026-05-05 | Dz.U. 2025 poz. 734 (`DU/2025/734`) |
| Kodeks postępowania w sprawach o wykroczenia | k.p.w. | Dz.U. 2001 nr 106 poz. 1148 / `DU/2001/1148` | `DU/2001/1148#U` | 2026-08-31 | Dz.U. 2025 poz. 860 (`DU/2025/860`) |
| Kodeks spółek handlowych | k.s.h. | Dz.U. 2000 nr 94 poz. 1037 / `DU/2000/1037` | `DU/2000/1037#U` | 2026-06-03 | Dz.U. 2024 poz. 18 (`DU/2024/18`) |
| Kodeks postępowania administracyjnego | k.p.a. | Dz.U. 1960 nr 30 poz. 168 / `DU/1960/168` | `DU/1960/168#U` | 2025-12-12 | Dz.U. 2025 poz. 1691 (`DU/2025/1691`) |
| Prawo o postępowaniu przed sądami administracyjnymi | p.p.s.a. | Dz.U. 2002 nr 153 poz. 1270 / `DU/2002/1270` | `DU/2002/1270#U` | 2026-10-09 | Dz.U. 2026 poz. 143 (`DU/2026/143`) |
| Ordynacja podatkowa | o.p. | Dz.U. 1997 nr 137 poz. 926 / `DU/1997/926` | `DU/1997/926#U` | 2026-10-08 | Dz.U. 2026 poz. 622 (`DU/2026/622`) |
| Kodeks wyborczy | – | Dz.U. 2011 nr 21 poz. 112 / `DU/2011/112` | `DU/2011/112#U` | 2026-10-08 | Dz.U. 2026 poz. 1261 (`DU/2026/1261`) |
| Kodeks morski | – | Dz.U. 2001 nr 138 poz. 1545 / `DU/2001/1545` | `DU/2001/1545#U` | 2026-08-19 | Dz.U. 2023 poz. 1309 (`DU/2023/1309`) |
| **Ustawy gospodarcze, konsumenckie i majątkowe** | | | | | |
| Prawo upadłościowe | – | Dz.U. 2003 nr 60 poz. 535 / `DU/2003/535` | `DU/2003/535#U` | 2026-10-09 | Dz.U. 2026 poz. 913 (`DU/2026/913`) |
| Prawo restrukturyzacyjne | – | Dz.U. 2015 poz. 978 / `DU/2015/978` | `DU/2015/978#U` | 2026-10-08 | Dz.U. 2026 poz. 533 (`DU/2026/533`) |
| Ustawa o prawach konsumenta | – | Dz.U. 2014 poz. 827 / `DU/2014/827` | `DU/2014/827#U` | 2026-10-08 | Dz.U. 2026 poz. 1244 (`DU/2026/1244`) |
| Ustawa o ochronie konkurencji i konsumentów | u.o.k.i.k. | Dz.U. 2007 nr 50 poz. 331 / `DU/2007/331` | `DU/2007/331#U` | 2026-10-06 | Dz.U. 2025 poz. 1714 (`DU/2025/1714`) |
| Ustawa o zwalczaniu nieuczciwej konkurencji | u.z.n.k. | Dz.U. 1993 nr 47 poz. 211 / `DU/1993/211` | `DU/1993/211#U` | 2026-01-30 | Dz.U. 2026 poz. 85 (`DU/2026/85`) |
| Ustawa o świadczeniu usług drogą elektroniczną | – | Dz.U. 2002 nr 144 poz. 1204 / `DU/2002/1204` | `DU/2002/1204#U` | 2026-10-06 | Dz.U. 2024 poz. 1513 (`DU/2024/1513`) |
| Prawo przedsiębiorców | – | Dz.U. 2018 poz. 646 / `DU/2018/646` | `DU/2018/646#U` | 2026-05-06 | Dz.U. 2025 poz. 1480 (`DU/2025/1480`) |
| Prawo zamówień publicznych | p.z.p. | Dz.U. 2019 poz. 2019 / `DU/2019/2019` | `DU/2019/2019#U` | 2026-07-28 | Dz.U. 2026 poz. 793 (`DU/2026/793`) |
| Prawo bankowe | – | Dz.U. 1997 nr 140 poz. 939 / `DU/1997/939` | `DU/1997/939#U` | 2026-10-08 | Dz.U. 2026 poz. 38 (`DU/2026/38`) |
| Ustawa o rachunkowości | – | Dz.U. 1994 nr 121 poz. 591 / `DU/1994/591` | `DU/1994/591#U` | 2026-10-08 | Dz.U. 2026 poz. 522 (`DU/2026/522`) |
| Ustawa o księgach wieczystych i hipotece | u.k.w.h. | Dz.U. 1982 nr 19 poz. 147 / `DU/1982/147` | `DU/1982/147#U` | 2026-08-21 | Dz.U. 2026 poz. 1066 (`DU/2026/1066`) |
| Ustawa o własności lokali | – | Dz.U. 1994 nr 85 poz. 388 / `DU/1994/388` | `DU/1994/388#U` | 2026-07-16 | Dz.U. 2026 poz. 232 (`DU/2026/232`) |
| Ustawa o ochronie praw lokatorów, mieszkaniowym zasobie gminy i o zmianie Kodeksu cywilnego | – | Dz.U. 2001 nr 71 poz. 733 / `DU/2001/733` | `DU/2001/733#U` | 2024-03-15 | Dz.U. 2023 poz. 725 (`DU/2023/725`) |
| Prawo budowlane | – | Dz.U. 1994 nr 89 poz. 414 / `DU/1994/414` | `DU/1994/414#U` | 2026-10-08 | Dz.U. 2026 poz. 524 (`DU/2026/524`) |
| Ustawa o kosztach sądowych w sprawach cywilnych | u.k.s.c. | Dz.U. 2005 nr 167 poz. 1398 / `DU/2005/1398` | `DU/2005/1398#U` | 2026-08-18 | Dz.U. 2025 poz. 1228 (`DU/2025/1228`) |
| Prawo autorskie (ustawa o prawie autorskim i prawach pokrewnych) | – | Dz.U. 1994 nr 24 poz. 83 / `DU/1994/83` | `DU/1994/83#U` | 2026-10-06 | Dz.U. 2025 poz. 24 (`DU/2025/24`) |
| Prawo własności przemysłowej | – | Dz.U. 2001 nr 49 poz. 508 / `DU/2001/508` | `DU/2001/508#U` | 2026-10-06 | Dz.U. 2023 poz. 1170 (`DU/2023/1170`) |
| **Podatki, ubezpieczenia, dane osobowe, ruch drogowy** | | | | | |
| Ustawa o podatku dochodowym od osób fizycznych | u.p.d.o.f. (PIT) | Dz.U. 1991 nr 80 poz. 350 / `DU/1991/350` | `DU/1991/350#U` | 2026-10-01 | Dz.U. 2026 poz. 592 (`DU/2026/592`) |
| Ustawa o podatku dochodowym od osób prawnych | u.p.d.o.p. (CIT) | Dz.U. 1992 nr 21 poz. 86 / `DU/1992/86` | `DU/1992/86#U` | 2026-10-08 | Dz.U. 2026 poz. 554 (`DU/2026/554`) |
| Ustawa o podatku od towarów i usług | u.p.t.u. (VAT) | Dz.U. 2004 nr 54 poz. 535 / `DU/2004/535` | `DU/2004/535#U` | 2026-10-02 | Dz.U. 2026 poz. 1263 (`DU/2026/1263`) |
| Ustawa o systemie ubezpieczeń społecznych | – | Dz.U. 1998 nr 137 poz. 887 / `DU/1998/887` | `DU/1998/887#U` | 2026-10-07 | Dz.U. 2026 poz. 199 (`DU/2026/199`) |
| Ustawa o emeryturach i rentach z Funduszu Ubezpieczeń Społecznych | – | Dz.U. 1998 nr 162 poz. 1118 / `DU/1998/1118` | `DU/1998/1118#U` | 2026-09-09 | Dz.U. 2025 poz. 1749 (`DU/2025/1749`) |
| Ustawa o ochronie danych osobowych (2018; uzupełnia RODO) | u.o.d.o. | Dz.U. 2018 poz. 1000 / `DU/2018/1000` | `DU/2018/1000#U` | 2026-08-18 | Dz.U. 2019 poz. 1781 (`DU/2019/1781`) |
| Prawo o ruchu drogowym | p.r.d. | Dz.U. 1997 nr 98 poz. 602 / `DU/1997/602` | `DU/1997/602#U` | 2026-09-04 | Dz.U. 2024 poz. 1251 (`DU/2024/1251`) |
| Ustawa o cudzoziemcach | – | Dz.U. 2013 poz. 1650 / `DU/2013/1650` | `DU/2013/1650#U` | 2026-08-12 | Dz.U. 2025 poz. 1079 (`DU/2025/1079`) |
| **Ustrój sądów, organów i prawa wykonywania zawodów** | | | | | |
| Prawo o ustroju sądów powszechnych | u.s.p. | Dz.U. 2001 nr 98 poz. 1070 / `DU/2001/1070` | `DU/2001/1070#U` | 2026-10-08 | Dz.U. 2024 poz. 334 (`DU/2024/334`) |
| Ustawa o Sądzie Najwyższym | u.s.n. | Dz.U. 2018 poz. 5 / `DU/2018/5` | `DU/2018/5#U` | 2026-09-16 | Dz.U. 2024 poz. 622 (`DU/2024/622`) |
| Prawo o ustroju sądów administracyjnych | p.u.s.a. | Dz.U. 2002 nr 153 poz. 1269 / `DU/2002/1269` | `DU/2002/1269#U` | 2026-09-09 | Dz.U. 2024 poz. 1267 (`DU/2024/1267`) |
| Prawo o adwokaturze | – | Dz.U. 1982 nr 16 poz. 124 / `DU/1982/124` | `DU/1982/124#U` | 2026-10-08 | Dz.U. 2024 poz. 1564 (`DU/2024/1564`) |
| Prawo o notariacie | – | Dz.U. 1991 nr 22 poz. 91 / `DU/1991/91` | `DU/1991/91#U` | 2026-08-21 | Dz.U. 2026 poz. 614 (`DU/2026/614`) |
| Ustawa o samorządzie gminnym | u.s.g. | Dz.U. 1990 nr 16 poz. 95 / `DU/1990/95` | `DU/1990/95#U` | 2026-10-08 | Dz.U. 2026 poz. 662 (`DU/2026/662`) |
| **Prawo o prawie (publikowanie i redagowanie)** | | | | | |
| Ustawa o ogłaszaniu aktów normatywnych i niektórych innych aktów prawnych | u.o.a.n. | Dz.U. 2000 nr 62 poz. 718 / `DU/2000/718` | `DU/2000/718#U` | 2026-10-08 | Dz.U. 2019 poz. 1461 (`DU/2019/1461`) |
| Zasady techniki prawodawczej (rozporządzenie PRM, tekst jednolity) | ZTP | – | – | – | Dz.U. 2026 poz. 300 (`DU/2026/300`) |

Zasada z art. 1 większości z tych aktów pokazuje, czego dotyczą (sprawdzone cytaty):

- Kodeks cywilny: „Kodeks niniejszy reguluje stosunki cywilnoprawne między osobami fizycznymi i osobami prawnymi.” [DU/1964/93#U art. 1]
- Kodeks postępowania cywilnego: do rozpoznawania spraw cywilnych powołane są sądy powszechne i Sąd Najwyższy [DU/1964/296#U art. 2].
- Kodeks pracy: „Kodeks pracy określa prawa i obowiązki pracowników i pracodawców.” [DU/1974/141#U art. 1]
- Kodeks karny: „Odpowiedzialności karnej podlega ten tylko, kto popełnia czyn zabroniony pod groźbą kary przez ustawę obowiązującą w czasie jego popełnienia.” [DU/1997/553#U art. 1]
- Kodeks postępowania karnego: „Postępowanie karne w sprawach należących do właściwości sądów toczy się według przepisów niniejszego kodeksu.” [DU/1997/555#U art. 1]
- Kodeks wykroczeń: odpowiedzialności za wykroczenie podlega ten, kto popełnia czyn społecznie szkodliwy, zabroniony przez ustawę pod groźbą kary aresztu, ograniczenia wolności, grzywny lub nagany [DU/1971/114#U art. 1].
- Kodeks karny wykonawczy: reguluje wykonywanie orzeczeń w postępowaniu karnym i w sprawach o wykroczenia [DU/1997/557#U art. 1].
- Kodeks karny skarbowy: odpowiedzialność za przestępstwa i wykroczenia skarbowe [DU/1999/930#U art. 1].
- Kodeks spółek handlowych: „Ustawa reguluje tworzenie, organizację, funkcjonowanie, rozwiązywanie, łączenie, podział i przekształcanie spółek handlowych.” [DU/2000/1037#U art. 1]
- Kodeks postępowania administracyjnego: normuje postępowanie przed organami administracji publicznej w sprawach indywidualnych rozstrzyganych decyzjami [DU/1960/168#U art. 1].
- Prawo o postępowaniu przed sądami administracyjnymi: „normuje postępowanie sądowe w sprawach z zakresu kontroli działalności administracji publicznej” [DU/2002/1270#U art. 1].
- Ordynacja podatkowa: normuje zobowiązania podatkowe, informacje podatkowe, postępowanie podatkowe, kontrolę podatkową i tajemnicę skarbową [DU/1997/926#U art. 1].
- Prawo przedsiębiorców: „Ustawa określa zasady podejmowania, wykonywania i zakończenia działalności gospodarczej na terytorium Rzeczypospolitej Polskiej” [DU/2018/646#U art. 1].
- Ustawa o prawach konsumenta: określa prawa przysługujące konsumentowi, w tym obowiązki przedsiębiorcy zawierającego umowę z konsumentem [DU/2014/827#U art. 1].
- Ustawa o ochronie konkurencji i konsumentów: „Ustawa określa warunki rozwoju i ochrony konkurencji” [DU/2007/331#U art. 1].
- Ustawa o księgach wieczystych i hipotece: „Księgi wieczyste prowadzi się w celu ustalenia stanu prawnego nieruchomości.” [DU/1982/147#U art. 1]
- Ustawa o ochronie danych osobowych (2018): „Ustawę stosuje się do ochrony osób fizycznych w związku z przetwarzaniem danych osobowych” w zakresie określonym w RODO [DU/2018/1000#U art. 1].
- Ustawa o cudzoziemcach: „Ustawa określa zasady i warunki wjazdu cudzoziemców na terytorium Rzeczypospolitej Polskiej” [DU/2013/1650#U art. 1].
- Prawo o ustroju sądów powszechnych: sądami powszechnymi są sądy rejonowe, okręgowe i apelacyjne [DU/2001/1070#U art. 1].

Kodeks rodzinny i opiekuńczy (art. 1 dotyczy zawarcia małżeństwa) [DU/1964/59#U art. 1] oraz pozostałe akty z tabeli – opis przedmiotu ustawy sprawdź w ich art. 1 lub w spisie treści (`get_act`, `include_toc=1`).

## 3. Ustawy wprowadzające (ważne przy przepisach przejściowych)

Przepisy wprowadzające kodeksy to osobne ustawy z przepisami przejściowymi i o wejściu kodeksu w życie. Są w bazie jako zwykłe akty (kategoria `podstawowe`, bez `#U`):

| Nazwa | Adres publikacyjny | doc_id | Kategoria w bazie |
|---|---|---|---|
| Przepisy wprowadzające Kodeks cywilny | Dz.U. 1964 nr 16 poz. 94 | `DU/1964/94` | podstawowe |
| Przepisy wprowadzające Kodeks postępowania cywilnego | Dz.U. 1964 nr 43 poz. 297 | `DU/1964/297` | podstawowe |
| Przepisy wprowadzające Kodeks pracy | Dz.U. 1974 nr 24 poz. 142 | `DU/1974/142` | podstawowe |
| Przepisy wprowadzające Kodeks karny | Dz.U. 1997 nr 88 poz. 554 | `DU/1997/554` | podstawowe |
| Przepisy wprowadzające Kodeks postępowania karnego | Dz.U. 1997 nr 89 poz. 556 | `DU/1997/556` | podstawowe |
| Przepisy wprowadzające Kodeks karny skarbowy | Dz.U. 1999 nr 83 poz. 931 | `DU/1999/931` | podstawowe |
| Przepisy wprowadzające Kodeks wykroczeń | Dz.U. 1971 nr 12 poz. 115 | `DU/1971/115` | podstawowe |
| Przepisy wprowadzające Kodeks postępowania w sprawach o wykroczenia | Dz.U. 2001 nr 106 poz. 1149 | `DU/2001/1149` | podstawowe |
| Przepisy wprowadzające ustawę – Prawo zamówień publicznych | Dz.U. 2019 poz. 2020 | `DU/2019/2020` | podstawowe |
| Przepisy wprowadzające ustawę – Kodeks wyborczy | Dz.U. 2011 nr 21 poz. 113 | `DU/2011/113` | podstawowe |

## 4. Pozostałe akty często wyszukiwane (tekst ujednolicony w bazie)

| Nazwa aktu | Adres publikacyjny | doc_id tekstu ujednoliconego | Zmiana rekordu w ELI |
|---|---|---|---|
| Prawo o prokuraturze | Dz.U. 2016 poz. 177 | `DU/2016/177#U` | 2026-09-30 |
| Przepisy wprowadzające ustawę – Prawo o prokuraturze | Dz.U. 2016 poz. 178 | `DU/2016/178#U` | 2024-04-25 |
| Ustawa o radcach prawnych | Dz.U. 1982 nr 19 poz. 145 | `DU/1982/145#U` | 2026-10-08 |
| Ustawa o komornikach sądowych | Dz.U. 2018 poz. 771 | `DU/2018/771#U` | 2026-07-14 |
| Ustawa o Krajowej Radzie Sądownictwa | Dz.U. 2011 nr 126 poz. 714 | `DU/2011/714#U` | 2026-05-20 |
| Ustawa o Rzeczniku Praw Obywatelskich | Dz.U. 1987 nr 21 poz. 123 | `DU/1987/123#U` | 2026-07-28 |
| Ustawa o organizacji i trybie postępowania przed Trybunałem Konstytucyjnym | Dz.U. 2016 poz. 2072 | `DU/2016/2072#U` | 2024-03-14 |
| Ustawa o statusie sędziów Trybunału Konstytucyjnego | Dz.U. 2016 poz. 2073 | `DU/2016/2073#U` | 2026-04-17 |
| Prawo o ustroju sądów wojskowych | Dz.U. 1997 nr 117 poz. 753 | `DU/1997/753#U` | 2026-09-25 |
| Ustawa o Radzie Ministrów | Dz.U. 1996 nr 106 poz. 492 | `DU/1996/492#U` | 2026-10-02 |
| Ustawa o Policji | Dz.U. 1990 nr 30 poz. 179 | `DU/1990/179#U` | 2026-10-05 |
| Ustawa o Straży Granicznej | Dz.U. 1990 nr 78 poz. 462 | `DU/1990/462#U` | 2026-09-30 |
| Ustawa o Krajowej Administracji Skarbowej | Dz.U. 2016 poz. 1947 | `DU/2016/1947#U` | 2026-10-08 |
| Ustawa o dostępie do informacji publicznej | Dz.U. 2001 nr 112 poz. 1198 | `DU/2001/1198#U` | 2026-07-28 |
| Ustawa o informatyzacji działalności podmiotów realizujących zadania publiczne | Dz.U. 2005 nr 64 poz. 565 | `DU/2005/565#U` | 2026-09-25 |
| Ustawa o krajowym systemie cyberbezpieczeństwa | Dz.U. 2018 poz. 1560 | `DU/2018/1560#U` | 2026-10-08 |
| Ustawa o ochronie danych osobowych przetwarzanych w związku z zapobieganiem i zwalczaniem przestępczości | Dz.U. 2019 poz. 125 | `DU/2019/125#U` | 2024-03-14 |
| Ustawa o usługach płatniczych | Dz.U. 2011 nr 199 poz. 1175 | `DU/2011/1175#U` | 2026-10-08 |
| Ustawa o kredycie konsumenckim | Dz.U. 2011 nr 126 poz. 715 | `DU/2011/715#U` | 2026-10-08 |
| Ustawa o opłacie skarbowej | Dz.U. 2006 nr 225 poz. 1635 | `DU/2006/1635#U` | 2026-10-08 |
| Ustawa o podatkach i opłatach lokalnych | Dz.U. 1991 nr 9 poz. 31 | `DU/1991/31#U` | 2026-07-28 |
| Ustawa o podatku od spadków i darowizn | Dz.U. 1983 nr 45 poz. 207 | `DU/1983/207#U` | 2026-07-16 |
| Ustawa o fundacjach | Dz.U. 1984 nr 21 poz. 97 | `DU/1984/97#U` | 2026-03-25 |
| Prawo o stowarzyszeniach | Dz.U. 1989 nr 20 poz. 104 | `DU/1989/104#U` | 2026-03-25 |
| Ustawa o związkach zawodowych | Dz.U. 1991 nr 55 poz. 234 | `DU/1991/234#U` | 2026-04-29 |
| Ustawa o minimalnym wynagrodzeniu za pracę | Dz.U. 2002 nr 200 poz. 1679 | `DU/2002/1679#U` | 2026-09-15 |
| Ustawa o przeciwdziałaniu przemocy domowej | Dz.U. 2005 nr 180 poz. 1493 | `DU/2005/1493#U` | 2026-09-16 |
| Prawo energetyczne | Dz.U. 1997 nr 54 poz. 348 | `DU/1997/348#U` | 2026-09-04 |
| Prawo ochrony środowiska | Dz.U. 2001 nr 62 poz. 627 | `DU/2001/627#U` | 2026-09-30 |
| Ustawa o odpadach | Dz.U. 2013 poz. 21 | `DU/2013/21#U` | 2026-10-09 |
| Prawo wodne | Dz.U. 2017 poz. 1566 | `DU/2017/1566#U` | 2026-09-10 |
| Ustawa o gospodarce nieruchomościami | Dz.U. 1997 nr 115 poz. 741 | `DU/1997/741#U` | 2026-10-06 |
| Prawo prasowe | Dz.U. 1984 nr 5 poz. 24 | `DU/1984/24#U` | 2024-03-15 |
| Ustawa o odpowiedzialności podmiotów zbiorowych za czyny zabronione pod groźbą kary | Dz.U. 2002 nr 197 poz. 1661 | `DU/2002/1661#U` | 2026-05-08 |
| Ustawa o postępowaniu egzekucyjnym w administracji | Dz.U. 1966 nr 24 poz. 151 | `DU/1966/151#U` | 2026-08-18 |
| Ustawa o ochronie zwierząt | Dz.U. 1997 nr 111 poz. 724 | `DU/1997/724#U` | 2026-07-31 |
| Ustawa o ochronie ludności i obronie cywilnej | Dz.U. 2024 poz. 1907 | `DU/2024/1907#U` | 2026-09-04 |

## 5. Uwagi i pułapki

- **Nie kopiuj adresów z pamięci.** Adres publikacyjny, ELI i doc_id bierz z tej tabeli lub z odpowiedzi API (`display_address`, `eli`, `doc_id`).
- **Kilka ustaw o podobnej nazwie.** „Ustawa o ochronie danych osobowych” z 10 maja 2018 r. (Dz.U. 2018 poz. 1000) to inny akt niż ustawa z 14 grudnia 2018 r. o ochronie danych osobowych przetwarzanych w związku z zapobieganiem i zwalczaniem przestępczości (Dz.U. 2019 poz. 125); RODO jest rozporządzeniem UE, nie ustawą krajową **[WO]**. Podobnie osobne są Prawo upadłościowe i Prawo restrukturyzacyjne.
- **Ustawy, które „zmieniają kodeks”.** Tytuł typu „o zmianie ustawy – Kodeks cywilny” to akt zmieniający (kategoria `zmieniajace`), nie kodeks. Obowiązującą treść czytaj w `ELI#U`.
- **Podatki.** Ordynacja podatkowa normuje zobowiązania, informacje, postępowanie i tajemnicę skarbową [DU/1997/926#U art. 1]; stawki i zasady poszczególnych podatków są w osobnych ustawach podatkowych (PIT, CIT, VAT, podatki lokalne – tabele wyżej) **[WO]**. Stawki i limity zmieniają się często, więc zawsze sprawdzaj stan na dzień zdarzenia.
- **Ustawy nie w bazie.** Akty prawa miejscowego, dzienniki wojewódzkie, akty UE i orzecznictwo sądów są poza zakresem (patrz `gdzie-szukac-dalej`). Obwieszczenia o tekstach jednolitych wielu mniej znanych ustaw także są w bazie – wyszukaj po tytule.
- **Po „Uaktualnij to wszystko”.** Tekst ujednolicony i obwieszczenia się zmieniają, a z nimi kolumny „Zmiana rekordu w ELI” i „Najnowszy tekst jednolity”. Tabela powstała na danych z 2026-10-11 i wymaga odświeżenia (procedura w `docs/AKTUALIZACJA.md`; sprawdzanie odnośników: `python pipeline/tools/lookup_article.py --verify-md vercel/public/wiedza/*.md`).
- **Odświeżanie tej tabeli (instrukcja dla agenta).** Dla każdego ELI z kolumny „Akt podstawowy” odczytaj `changeDate` z `dane/indeks_ujednolicone.json`; najnowszy tekst jednolity znajdź w `pipeline/out/chunks.jsonl` jako dokument kategorii `jednolite`, którego tytuł zawiera „w sprawie ogłoszenia jednolitego tekstu” i nazwę aktu (najpóźniejsza data); sprawdź, czy istnieją doc_id `ELI#U` i obwieszczenia (`python pipeline/tools/lookup_article.py DOC_ID --list-articles`). Nowe nazwy aktów dopisz w tym samym układzie.
