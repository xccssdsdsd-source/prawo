# Jak cytować przepisy prawa

> **Data weryfikacji: 2026-10-11.** Stan danych: baza Prawo API z dnia 11.10.2026 (przepisy ogłoszone później nie są uwzględnione).
> **To nie jest porada prawna** – to informacja ogólna oparta na tekstach przepisów. Aktualność zawsze sprawdź w ISAP (https://isap.sejm.gov.pl) lub u prawnika.
> Odnośniki w formie `[doc_id art. N]` zostały sprawdzone z tekstem w bazie. **[WO]** = wiedza ogólna, niezweryfikowana w danych – zweryfikuj w ISAP.

## W skrócie

Poprawne powołanie przepisu = najmniejsza jednostka (art., ust./§, pkt, lit.) + skrót lub tytuł aktu + oznaczenie dziennika urzędowego (rocznik i pozycja). W odpowiedziach opartych na naszym API dodaj jeszcze: kategorię tekstu (ujednolicony / jednolity), `source_url` oraz linię „Stan danych na dzień …”.

## 1. Powoływanie jednostek w obrębie aktu

Kolejność od największej do najmniejszej: artykuł – ustęp (w kodeksach paragraf) – punkt – litera – tiret. Zapis: `art. 4 ust. 1 pkt 2 lit. a`, w kodeksie `art. 123 § 1 pkt 1`. Skróty „art.”, „ust.”, „pkt”, „lit.” nie zmieniają się w liczbie ani przypadku, a numer podaje się cyframi arabskimi bez kropki [DU/2026/300 § 57].

Przykłady sprawdzone w tekście:

- art. 8 ust. 1 Konstytucji RP: „Konstytucja jest najwyższym prawem Rzeczypospolitej Polskiej.” [DU/1997/483#U art. 8]
- art. 4 ust. 1 ustawy o ogłaszaniu aktów normatywnych: wejście w życie po upływie czternastu dni od ogłoszenia [DU/2000/718#U art. 4]
- art. 118 k.c.: ogólne terminy przedawnienia [DU/1964/93#U art. 118]
- art. 123 § 1 pkt 1 k.c.: przerwanie biegu przedawnienia czynnością przed sądem [DU/1964/93#U art. 123]
- art. 264 § 1 k.p.: odwołanie od wypowiedzenia w ciągu 21 dni [DU/1974/141#U art. 264]
- art. 129 § 2 k.p.a.: odwołanie w terminie czternastu dni [DU/1960/168#U art. 129]
- art. 53 § 1 p.p.s.a.: skarga w terminie trzydziestu dni [DU/2002/1270#U art. 53]
- art. 445 § 1 k.p.k.: apelacja w terminie 14 dni [DU/1997/555#U art. 445]

Artykuły z indeksem zapisuj jak w ustawie: art. 442¹ k.c. [DU/1964/93#U art. 442¹], a w danych i parametrach API: `442[1]`. Uwaga: w niektórych tekstach ujednoliconych indeks górny jest spłaszczony i art. 29¹ k.p. pojawia się jako „291” (patrz `jak-czytac-akt-prawny`, pkt 5).

## 2. Oznaczanie aktu: tytuł + dziennik

Zasady techniki prawodawczej (§ 158) przewidują, że przy odesłaniu do innego aktu normatywnego przytacza się w całości aktualny tytuł oraz oznaczenie dziennika urzędowego [DU/2026/300 § 158]:

1. akt, który nie był nowelizowany: pozycja (i w razie potrzeby rocznik) dziennika, w którym go ogłoszono;
2. akt nowelizowany, bez tekstu jednolitego: pozycja i rocznik ogłoszenia tekstu pierwotnego oraz aktów zmieniających;
3. akt z tekstem jednolitym: rocznik i pozycja ostatniego tekstu jednolitego;
4. tekst jednolity, który był nowelizowany: rocznik i pozycja tekstu jednolitego oraz aktów zmieniających ten tekst.

Gdy zmian jest więcej niż pięć, można podać tylko pozycję tekstu pierwotnego albo ostatniego tekstu jednolitego z dopiskiem „z późn. zm.”, a pełny wykaz zmian dać w odnośniku [DU/2026/300 § 158]. Przy kolejnym odesłaniu do tego samego aktu w tym samym akcie wystarczy sam tytuł [DU/2026/300 § 158].

Odesłania w tekście aktu są dynamiczne (do przepisu w brzmieniu obowiązującym w danym czasie) [DU/2026/300 § 159]; odesłanie do określonej wersji (statyczne) musi to zaznaczać dopiskiem „w brzmieniu z dnia…” [DU/2026/300 § 160].

**Jak to wygląda w żywych tekstach:**

- Kodeks cywilny z tekstem jednolitym i późniejszymi zmianami: „Kodeks cywilny (Dz. U. z 2025 r. poz. 1071, 1172 i 1508 oraz z 2026 r. poz. 184)” [DU/2026/184 art. 1]. Zwróć uwagę: najpierw rocznik i pozycja tekstu jednolitego (z 2025 r. poz. 1071), potem kolejne zmiany. Kolejny tekst jednolity k.c. ogłoszono w Dz.U. 2026 poz. 795 (Obwieszczenie z 27 maja 2026 r.) [DU/2026/795 ord 1].
- Ustawa o ogłaszaniu aktów normatywnych: tekst jednolity z 2019 r. i późniejsza zmiana: „Dz. U. z 2019 r. poz. 1461, z 2026 r. poz. 912.” [DU/2000/718#U art. 3]
- Ustawa powołana z rocznikiem i pozycją swojego tekstu jednolitego: „ustawie z dnia 20 lutego 2015 r. o rzeczach znalezionych (Dz. U. z 2023 r. poz. 501)” [DU/2026/184 art. 1].

Wniosek praktyczny: w odpowiedzi dla użytkownika podawaj najnowszy tekst jednolity, który widzisz w bazie (kategoria `jednolite`), a w razie wątpliwości adres publikacyjny z pola `display_address` i `source_url` – nie przepisuj adresów z pamięci.

## 3. Skróty dzienników urzędowych

Według ZTP nazwy dzienników oznacza się skrótami: Dziennik Ustaw – „Dz. U.”, Monitor Polski – „M.P.”, Dziennik Urzędowy UE – „Dz. Urz. UE”, Dziennik Urzędowy Wspólnot Europejskich – „Dz. Urz. WE”, Monitor Sądowy i Gospodarczy – „M.S.G.” [DU/2026/300 § 162]. Formę z kropkami i spacją („Dz. U.”) stosuje się w tekstach urzędowych; baza zapisuje adres maszynowo jako `Dz.U. 2026 poz. 1307` (bez spacji, bez „z … r.”). To dwa różne zapisy tego samego – nie myl ich i nie licz na to, że wyszukiwarka dopasuje oba.

Przykład powołania aktu unijnego w przypisie do k.c.: „Dz. Urz. UE L 409 z 04.12.2020, str. 1” [DU/1964/93#U art. 5]. Dla aktów UE ZTP wymagają podania rodzaju aktu, organu, numeru, daty i przedmiotu oraz oznaczenia dziennika (seria, numer, data) [DU/2026/300 § 161a].

## 4. Skróty aktów (zwyczajowe)

**[WO]** Skróty typu k.c., k.p.c., k.p., k.k., k.p.k., k.p.a., p.p.s.a., o.p. są zwyczajowe, nie ustawowe. Przy pierwszym użyciu rozwiń nazwę, a skrót wprowadź w nawiasie. Tabela skrótów razem z doc_id znajduje się w pliku `kodeksy-i-glowne-ustawy`. Dla własnych skrótów w aktach ZTP przewidują zapis: pełna nazwa, a po niej „zwane dalej …” [DU/2026/300 § 154].

## 5. Cytowanie z użyciem naszego API

Wzór (zgodny z `ai/AGENTS.md`):

`art. 446 § 4 k.c. (Dz.U. 1964 nr 16 poz. 93, tekst ujednolicony) – <source_url>`

Sprawdzona treść tego przepisu: „Sąd może także przyznać najbliższym członkom rodziny zmarłego odpowiednią sumę tytułem zadośćuczynienia pieniężnego za doznaną krzywdę.” [DU/1964/93#U art. 446]

Zasady:

1. Cytat dosłowny w cudzysłowie; parafraza osobno i oznaczona jako parafraza.
2. Podaj: skrót/tytuł aktu, numer jednostki, `display_address`, rodzaj tekstu (ujednolicony / jednolity / brzmienie z dnia ogłoszenia), `source_url`.
3. Identyfikatory techniczne: `eli` = `DU/1964/93`; `doc_id` = `eli` albo `eli#U` (tekst ujednolicony; w URL `#` jako `%23`). Nie używaj ich w tekście dla człowieka zamiast adresu publikacyjnego.
4. Zawsze dopisz: „Stan danych na dzień <data_as_of>” i zastrzeżenie, że to nie jest porada prawna.
5. Nie cytuj numeru artykułu z pamięci – zweryfikuj przez `get_article`. Przykład ryzyka: art. 36 § 1 k.p. podaje okresy wypowiedzenia 2 tygodnie / 1 miesiąc / 3 miesiące zależnie od okresu zatrudnienia [DU/1974/141#U art. 36], ale paragraf z indeksem jest tam zapisany jako „§ 11” (spłaszczony § 1¹).

## 6. Cytowanie orzeczeń

**[WO]** (wzory zweryfikuj w ISAP / bazach orzeczeń; poniżej tylko konwencje):

- Trybunał Konstytucyjny: sygnatura z literą rodzaju sprawy, np. K (kontrola abstrakcyjna), SK (skarga konstytucyjna), P (pytanie prawne); w danych (tytuły wyroków TK) występują zapisy z kropką i bez (`K 13/97`, `K. 2/97`, `U. 3/97`) – przy wyszukiwaniu spróbuj obu postaci. Tytuły wyroków TK ogłoszonych w Dz.U. mają formę `Wyrok Trybunału Konstytucyjnego z dnia … r. - sygn. akt …`. Przypis do art. 2 k.p.c. powołuje wyrok TK „sygn. akt SK. 12/99” [DU/1964/296#U art. 2].
- Sąd Najwyższy, sądy powszechne, NSA/WSA: sygnatura (np. III CZP 61/05, I FSK 123/21) + data + sąd. Orzeczenia sądów nie są w bazie (kategoria `wyrok` jest uśpiona).
- TSUE: numer sprawy (C-123/20, T-456/21); ETPCz: numer skargi (12345/10).
- Orzeczenia TK o niezgodności aktu ogłasza się w dzienniku, w którym był ogłoszony akt [DU/1997/483#U art. 190] – przy powołaniu przepisu, który TK uznał za niezgodny, ZTP każą podać także pozycję dziennika z tym orzeczeniem [DU/2026/300 § 158].

## 7. Najczęstsze błędy w cytowaniu

- Podanie adresu publikacyjnego aktu pierwotnego, gdy obowiązuje już tekst jednolity (patrz pkt 2).
- Pomylenie daty aktu z datą ogłoszenia: rok w adresie publikacyjnym to rok ogłoszenia (np. ustawa z 8.12.2017 – Dz.U. 2018 poz. 5) [DU/2018/5#U ord 1].
- Powołanie aktu zmieniającego jako źródła treści obowiązującej.
- Zapis „art. 4.1” lub „art. 4, 1” zamiast `art. 4 ust. 1`.
- Brak adnotacji o stanie danych.
