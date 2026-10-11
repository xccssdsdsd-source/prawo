# Jak czytać akt prawny

> **Data weryfikacji: 2026-10-11.** Stan danych: baza Prawo API z dnia 11.10.2026 (przepisy ogłoszone później nie są uwzględnione).
> **To nie jest porada prawna** – to informacja ogólna oparta na tekstach przepisów. Aktualność zawsze sprawdź w ISAP (https://isap.sejm.gov.pl) lub u prawnika.
> Odnośniki w formie `[doc_id art. N]` zostały sprawdzone z tekstem w bazie. **[WO]** = wiedza ogólna, niezweryfikowana w danych – zweryfikuj w ISAP.

## W skrócie

Akt prawny składa się z tytułu, przepisów merytorycznych, ewentualnych przepisów zmieniających, przejściowych i końcowych (z datą wejścia w życie). Podstawową jednostką jest artykuł. W ustawach artykuł dzieli się na ustępy (ust.), w kodeksach na paragrafy (§); dalej są punkty, litery i tiret. Czytając, zawsze sprawdzaj: który to dokument (tekst ujednolicony czy brzmienie z dnia ogłoszenia), czy przepis nie jest „(uchylony)”, i czy nie ma przepisów przejściowych.

## 1. Jednostki redakcyjne

Zasady techniki prawodawczej (ZTP, tekst jednolity: Dz.U. 2026 poz. 300) opisują, jak się redaguje i powołuje przepisy:

- „Podstawową jednostką redakcyjną ustawy jest artykuł.” [DU/2026/300 § 54]
- Jeśli myśl wyraża zespół zdań, artykuł dzieli się na ustępy; w ustawie określanej jako kodeks ustępy oznacza się paragrafami (§) [DU/2026/300 § 55].
- W obrębie artykułu (ustępu) z wyliczeniem wyróżnia się wprowadzenie do wyliczenia i punkty; w punktach można wprowadzić litery, w literach tiret, w tiret podwójne tiret [DU/2026/300 § 56].
- Oznaczenia: artykuł „art.” z cyframi arabskimi; ustęp cyfrą z kropką (przy powoływaniu: ust.); „Punkt oznacza się cyframi arabskimi z nawiasem z prawej strony” (przy powoływaniu: pkt); litera małą literą łacińską z nawiasem (przy powoływaniu: lit.) [DU/2026/300 § 57].
- Systematyka: „Artykuły grupuje się w rozdziały, rozdziały grupuje się w działy, a działy łączy się w tytuły.” W kodeksie „tytuły można grupować w księgi, a księgi łączyć w części.” [DU/2026/300 § 60]

Jak to wygląda w praktyce (obie konwencje w naszych danych):

- Ustawa z ustępami: „Akty normatywne, zawierające przepisy powszechnie obowiązujące, ogłaszane w dziennikach urzędowych wchodzą w życie po upływie czternastu dni od dnia ich ogłoszenia, chyba że dany akt normatywny określi termin dłuższy.” – to art. 4 ust. 1 ustawy o ogłaszaniu aktów normatywnych [DU/2000/718#U art. 4].
- Kodeks z paragrafami: „Bieg przedawnienia przerywa się:” – to art. 123 § 1 k.c., a kolejne punkty to pkt 1, 2, 3 (pkt 3 jest uchylony) [DU/1964/93#U art. 123].
- Artykuł bez podziału: art. 1 k.c. to jedno zdanie: „Kodeks niniejszy reguluje stosunki cywilnoprawne między osobami fizycznymi i osobami prawnymi.” [DU/1964/93#U art. 1]
- Konstytucja używa ustępów (art. 8 ust. 1 i 2) [DU/1997/483#U art. 8].

Zapis w danych: tekst fragmentu zaczyna się od `Art. N.`, a pole `heading` zawiera ścieżkę systematyki (np. `KSIĘGA PIERWSZA > CZĘŚĆ OGÓLNA > TYTUŁ VI Przedawnienie roszczeń` dla art. 118 k.c.) [DU/1964/93#U art. 118].

## 2. Typowa budowa ustawy

Według ZTP ustawa zawiera: tytuł, przepisy merytoryczne i przepisy o wejściu w życie [DU/2026/300 § 14]. Kolejność elementów: tytuł; przepisy merytoryczne (ogólne, szczegółowe); przepisy zmieniające; epizodyczne; przejściowe i dostosowujące; uchylające i o wejściu w życie [DU/2026/300 § 15].

- **Przepisy ogólne** określają zakres regulacji oraz objaśniają użyte w ustawie określenia i skróty [DU/2026/300 § 21]. Czytaj je jako pierwsze – definicje obowiązują w całej ustawie.
- **Przepisy szczegółowe** są uporządkowane: prawo materialne, przepisy ustrojowe, proceduralne, a na końcu przepisy o administracyjnych karach pieniężnych i przepisy karne [DU/2026/300 § 24].
- **Przepisy przejściowe** regulują wpływ nowej albo znowelizowanej ustawy na stosunki powstałe pod działaniem dotychczasowych przepisów [DU/2026/300 § 30].
- **Przepisy o wejściu w życie** to ostatni element ustawy; typowe brzmienia opisuje ZTP, np. wejście w życie po upływie 14 dni od dnia ogłoszenia albo z dniem ogłoszenia [DU/2026/300 § 45].
- Duże kodeksy bywają uzupełnione osobną ustawą wprowadzającą (tytuł zaczyna się od słów Przepisy wprowadzające…), w której są przepisy o wejściu w życie, zmieniające i przejściowe [DU/2026/300 § 47]. Dlatego obok k.c. istnieje ustawa Przepisy wprowadzające kodeks cywilny (Dz.U. 1964 nr 16 poz. 94) **[WO]** – sprawdzaj ją przy sprawach intertemporalnych.

## 3. Tytuł i daty: co oznaczają

- Tytuł zawiera datę aktu: Ustawa z dnia 23 kwietnia 1964 r. – Kodeks cywilny. To data uchwalenia/wydania, a **nie** data ogłoszenia ani wejścia w życie.
- Adres publikacyjny (`display_address`) wskazuje dziennik, rok ogłoszenia i pozycję, np. `Dz.U. 1964 nr 16 poz. 93`. Rok w adresie jest rokiem ogłoszenia, więc może się różnić od roku w tytule: ustawa o Sądzie Najwyższym z 8 grudnia 2017 r. ma adres Dz.U. 2018 poz. 5 [DU/2018/5#U ord 1].
- **Pułapka:** pole `announcement_date` w naszych fragmentach to w praktyce data wydania aktu (ta z tytułu), nie data ogłoszenia. Przykład: ustawa z 23 stycznia 2026 r. o zmianie ustawy o rzeczach znalezionych i Kodeksu cywilnego ma w bazie `announcement_date` 2026-01-23, a nagłówek Dziennika Ustaw w jej tekście brzmi „Warszawa, dnia 18 lutego 2026 r. Poz. 184” [DU/2026/184 ord 1]. Od dnia ogłoszenia liczy się vacatio legis (plik `wejscie-w-zycie-i-vacatio-legis`), więc bierz datę z nagłówka dziennika albo z ELI (pole `promulgation`).
- Dzień ogłoszenia aktu to dzień jego udostępnienia w postaci elektronicznej na stronie wydawcy dziennika [DU/2000/718#U art. 20].

## 4. Co jest w tekście ujednoliconym poza samymi przepisami

Teksty ujednolicone z ISAP (kategoria `ujednolicone`, doc_id z `#U`) to PDF-y zamienione na tekst. Zawierają ślady redakcyjne, które trzeba umieć odczytać:

- **(uchylony)** – przepis został uchylony i nie obowiązuje; numer zostaje, żeby nie przenumerowywać aktu. Przykład: art. 123 § 2 k.c. [DU/1964/93#U art. 123], art. 117 § 3 k.c. [DU/1964/93#U art. 117]. W ustawie o ogłaszaniu aktów normatywnych widnieje też zapis „Art. 30–40. (pominięte)” [DU/2000/718#U art. 29b].
- **Przypisy** – numerowane „1)”, „2)” wklejają się w tekst kolejnych artykułów. Zawierają np. informację o wdrażanych dyrektywach, o utracie mocy przepisu na podstawie wyroku TK (art. 2 k.p.c.) [DU/1964/296#U art. 2] oraz podstawę opracowania. Przykład: koniec art. 1 k.p.a. kończy się zdaniem „Opracowano na podstawie: t.j. Dz. U. z 2025 r. poz. 1691.” [DU/1960/168#U art. 1]. Ta adnotacja mówi, na jakim tekście jednolitym oparto tekst ujednolicony.
- **Przepisy jeszcze niewchodzące w życie** są oznaczane nawiasami (stare brzmienie w `[ ]`, nowe w `< >`). Przykład: w k.p.k. po art. 123 jest wklejona adnotacja „Nowe brzmienie art. 124 wejdzie w życie z dn. 1.10.2029 r.” [DU/1997/555#U art. 123]. Uwaga: ten art. 124 nie ma w bazie osobnego rekordu (tekst jest wklejony w art. 123), więc `get_article art=124` może zwrócić brak wyniku, mimo że przepis istnieje. Tekst bywa poszarpany, bo adnotacja przeplata się ze starym brzmieniem – zawsze zweryfikuj w ISAP. Wyraźniejszy przykład: art. 94³ k.p. (mobbing) ma w tekście stare brzmienie w `[ ]` i nowe w `< >` z adnotacją „Nowe brzmienie art. 94[3] wejdzie w życie z dn. 5.11.2026 r. (Dz. U. z 2026 r. poz. 1046).” – do tego dnia obowiązuje stare [DU/1974/141#U art. 942] (zob. `nadchodzace-zmiany`).
- **Znaczniki przypisów w tekście jednolitym z obwieszczenia** (kategoria `jednolite`) – np. „§ 1.3)” w art. 187 k.c. w obwieszczeniu o tekście jednolitym [DU/2026/795 art. 187]; ten sam artykuł w tekście ujednoliconym nie ma tych znaczników [DU/1964/93#U art. 187].

## 5. Numeracja z indeksami (a, b, ¹, ²)

Artykuły dodawane nowelizacjami dostają indeksy: literowe (art. 9a, art. 13a ustawy o Sądzie Najwyższym) [DU/2018/5#U art. 9a] albo górne cyfrowe (art. 442¹ k.c.) [DU/1964/93#U art. 442¹].

W bazie:

- indeks górny zapisujemy jako `46[1]` (art. 46¹); w wyniku bywa `442[1]`; w URL-ach i parametrach używaj dokładnie takiej postaci,
- indeks literowy jako `9a`,
- **w niektórych dokumentach indeks górny jest spłaszczony**: art. 29¹ k.p. występuje jako „291”, więc zapytanie o art. 291 k.p. zwraca dwa różne przepisy: art. 29¹ (informacja o warunkach zatrudnienia) i właściwy art. 291 (przedawnienie roszczeń ze stosunku pracy) [DU/1974/141#U art. 291]. Zawsze czytaj treść i nagłówek (`heading`), nie sam numer. Ten sam efekt widać w odesłaniach: art. 291 § 2¹ k.p. powołuje „art. 611” i „art. 1011 § 2”, co należy czytać jako artykuły z indeksem górnym (art. 61¹, art. 101¹) **[WO]**.
- art. 1 bywa wchłonięty do pierwszego fragmentu aktu (bez numeru artykułu); w ustawie o Sądzie Najwyższym art. 1 jest w fragmencie wstępnym razem z tytułem [DU/2018/5#U ord 1], więc zapytanie o `art=1` może nic nie zwrócić.

## 6. Odesłania i „stosuje się odpowiednio”

- Odesłania w aktach są domyślnie **dynamiczne**: wskazują przepis w brzmieniu obowiązującym w czasie stosowania przepisu odsyłającego, a odesłanie statyczne (do określonej wersji) musi to wyraźnie zaznaczać „w brzmieniu z dnia…” [DU/2026/300 § 159, 160].
- Zwrot „stosuje się odpowiednio” oznacza stosowanie z uwzględnieniem różnic między sytuacjami, a nie mechaniczne kopiowanie. Przykłady: przepisy o procesie do innych postępowań w kodeksie [DU/1964/296#U art. 13]; przepisy Kodeksu cywilnego do stosunku pracy [DU/1974/141#U art. 300]; art. 116 k.c. – skutki czynności prawnej w terminie jak przy warunku [DU/1964/93#U art. 116].
- Frazy „przepis szczególny”, „chyba że ustawa stanowi inaczej” sygnalizują wyjątki – szukaj ich w innych aktach (por. `hierarchia-zrodel-prawa`, pkt 9).

## 7. Jak czytać ustawę zmieniającą (kategoria `zmieniajace`)

Akt zmieniający nie zawiera pełnego tekstu zmienianej ustawy, tylko polecenia nowelizacyjne. Przykład (ustawa z 23 stycznia 2026 r., Dz.U. 2026 poz. 184):

- art. 1: „W ustawie z dnia 20 lutego 2015 r. o rzeczach znalezionych … wprowadza się następujące zmiany” [DU/2026/184 art. 1],
- art. 2 zmienia Kodeks cywilny („w art. 187 § 1 i 2 otrzymują brzmienie…”) [DU/2026/184 art. 2],
- art. 3 jest przepisem przejściowym: „Do rzeczy znalezionych przed dniem wejścia w życie niniejszej ustawy stosuje się przepisy dotychczasowe.” [DU/2026/184 art. 3],
- art. 4 określa wejście w życie: „Ustawa wchodzi w życie po upływie 3 miesięcy od dnia ogłoszenia.” [DU/2026/184 art. 4].

Treść obowiązującą dla zmienionego art. 187 k.c. czytaj w tekście ujednoliconym albo jednolitym, nie w akcie zmieniającym [DU/1964/93#U art. 187]. Sam akt zmieniający jest źródłem tylko tego, co dotyczy jego własnych przepisów przejściowych i wejścia w życie.

## 8. Lista kontrolna przed zacytowaniem przepisu

1. Czy to tekst ujednolicony/jednolity, a nie brzmienie pierwotne ani akt zmieniający? (`teksty-jednolite-ujednolicone-zmieniajace`)
2. Czy artykuł nie jest „(uchylony)” i czy nie jest przepisem jeszcze niewchodzącym w życie (`< >`)?
3. Czy numer jest właściwy (indeksy, spłaszczone indeksy, art. 1 we fragmencie wstępnym)?
4. Czy nie ma przepisu szczególnego, przepisów przejściowych lub odesłania do innych przepisów?
5. Czy podaję adres publikacyjny i stan danych („Stan danych na dzień 11.10.2026”)?
