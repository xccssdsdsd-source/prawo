# Hierarchia źródeł prawa w Polsce

> **Data weryfikacji: 2026-10-11.** Stan danych: baza Prawo API z dnia 11.10.2026 (przepisy ogłoszone później nie są uwzględnione).
> **To nie jest porada prawna** – to informacja ogólna oparta na tekstach przepisów. Aktualność zawsze sprawdź w ISAP (https://isap.sejm.gov.pl) lub u prawnika.
> Odnośniki w formie `[doc_id art. N]` (identyfikator dokumentu w naszej bazie + numer artykułu) zostały sprawdzone z tekstem w bazie. Oznaczenie **[WO]** = wiedza ogólna, niezweryfikowana w danych – zweryfikuj w ISAP.

## W skrócie

Najwyżej stoi Konstytucja. Pod nią: ustawy oraz ratyfikowane umowy międzynarodowe (te za zgodą wyrażoną w ustawie mają pierwszeństwo przed ustawą). Niżej rozporządzenia (wykonują ustawy), a na poziomie lokalnym akty prawa miejscowego. Osobną kategorią są akty wewnętrzne (uchwały i zarządzenia), które nie tworzą praw ani obowiązków obywateli. Orzeczenia sądów nie są wymienione wśród źródeł powszechnie obowiązującego prawa.

## 1. Zamknięty katalog źródeł powszechnie obowiązującego prawa

- Konstytucja wylicza je wprost: „Źródłami powszechnie obowiązującego prawa Rzeczypospolitej Polskiej są: Konstytucja, ustawy, ratyfikowane umowy międzynarodowe oraz rozporządzenia.” [DU/1997/483#U art. 87]
- Na obszarze działania organów, które je ustanowiły, źródłem prawa są także akty prawa miejscowego [DU/1997/483#U art. 87].
- Katalog nie wymienia orzeczeń sądowych, uchwał Rady Ministrów ani zarządzeń. Orzecznictwo ma duże znaczenie praktyczne, ale nie jest ustawą – sędziowie „podlegają tylko Konstytucji oraz ustawom” [DU/1997/483#U art. 178].

## 2. Konstytucja – najwyższe prawo

- „Konstytucja jest najwyższym prawem Rzeczypospolitej Polskiej.” Jej przepisy stosuje się bezpośrednio, chyba że Konstytucja stanowi inaczej [DU/1997/483#U art. 8].
- Zasada legalizmu: „Organy władzy publicznej działają na podstawie i w granicach prawa.” [DU/1997/483#U art. 7] W postępowaniu administracyjnym powtarza ją kodeks: „Organy administracji publicznej działają na podstawie przepisów prawa.” [DU/1960/168#U art. 6]
- Rzeczpospolita przestrzega wiążącego ją prawa międzynarodowego [DU/1997/483#U art. 9].
- Ogłoszenie jest warunkiem wejścia w życie ustaw, rozporządzeń i aktów prawa miejscowego [DU/1997/483#U art. 88]. Zasady ogłaszania opisuje osobna ustawa (patrz plik `wejscie-w-zycie-i-vacatio-legis`).
- Kontrola zgodności z Konstytucją należy do Trybunału Konstytucyjnego – zob. pkt 7 poniżej.

## 3. Umowy międzynarodowe i prawo Unii Europejskiej

- Ratyfikowana umowa międzynarodowa po ogłoszeniu w Dzienniku Ustaw jest częścią krajowego porządku prawnego i co do zasady stosuje się ją bezpośrednio [DU/1997/483#U art. 91].
- Umowa ratyfikowana za uprzednią zgodą wyrażoną w ustawie „ma pierwszeństwo przed ustawą, jeżeli ustawy tej nie da się pogodzić z umową.” [DU/1997/483#U art. 91]
- Gdy wynika to z umowy konstytuującej organizację międzynarodową, prawo przez nią stanowione stosuje się bezpośrednio, z pierwszeństwem w razie kolizji z ustawami [DU/1997/483#U art. 91]. To konstytucyjna podstawa pierwszeństwa prawa UE przed ustawami krajowymi.
- **[WO]** Rozporządzenia UE (np. RODO) obowiązują bezpośrednio, dyrektywy wymagają wdrożenia ustawą krajową. W naszych danych kategoria `ue` jest uśpiona (patrz plik `gdzie-szukac-dalej`), a ślad wdrożenia dyrektyw widać w przypisach tekstów ujednoliconych (np. przypis do art. 5 k.c. wymienia wdrażane dyrektywy) [DU/1964/93#U art. 5].
- Umowy międzynarodowe są w bazie jako kategoria `umowa` – to nie są przepisy krajowe w rozumieniu zwykłych ustaw; sprawdzaj, czy umowa jest ratyfikowana i ogłoszona.

## 4. Ustawy (w tym kodeksy)

- Prezydent podpisuje ustawę w ciągu 21 dni od przedstawienia i zarządza jej ogłoszenie w Dzienniku Ustaw; może skierować ją do Trybunału Konstytucyjnego albo zwrócić Sejmowi do ponownego rozpatrzenia [DU/1997/483#U art. 122].
- Kodeks to ustawa. Zasady techniki prawodawczej przewidują, że określenie przedmiotu rozpoczynające się od „Kodeks”, „Prawo” albo „Ordynacja” stosuje się, gdy ustawa wyczerpująco reguluje obszerną dziedzinę spraw [DU/2026/300 § 19]. Nie czyni to kodeksu aktem wyższej rangi niż inna ustawa **[WO]**, ale ustawy szczegółowe mają posługiwać się określeniami z ustawy podstawowej danej dziedziny [DU/2026/300 § 9].
- W razie sporu, który przepis stosować, sprawdź najpierw, czy przepis szczególny wyłącza ogólny (pkt 9).

## 5. Rozporządzenia

- Rozporządzenia wydają organy wskazane w Konstytucji „na podstawie szczegółowego upoważnienia zawartego w ustawie i w celu jej wykonania”. Upoważnienie ma wskazywać organ, zakres spraw i wytyczne; organ nie może przekazać kompetencji innemu organowi [DU/1997/483#U art. 92].
- Zasady techniki prawodawczej wymagają, by przepis upoważniający wskazywał organ, rodzaj aktu, zakres spraw i wytyczne dotyczące treści [DU/2026/300 § 63], a stopień szczegółowości wytycznych zależał od rodzaju spraw [DU/2026/300 § 66].
- Przykład delegacji w ustawie: „Prezes Rady Ministrów określi, w drodze rozporządzenia, wymagania techniczne” dla dzienników urzędowych [DU/2000/718#U art. 28c].
- Rozporządzenie jest podporządkowane ustawie, na której się opiera. Los rozporządzeń wykonawczych przy zmianie lub uchyleniu ustawy ustawodawca ma regulować w przepisach przejściowych [DU/2026/300 § 32, 33]. Dlatego pytając o obowiązujące rozporządzenie, sprawdzaj nie tylko jego tekst, ale i to, czy ustawa upoważniająca nie zmieniła się (i czy przepisy przejściowe nie utrzymały starego rozporządzenia w mocy).
- Rozporządzenia ogłasza się w Dzienniku Ustaw (organy z art. 9 ust. 1 pkt 4 ustawy o ogłaszaniu aktów normatywnych) [DU/2000/718#U art. 9].

## 6. Akty prawa miejscowego

- Organy samorządu terytorialnego oraz terenowe organy administracji rządowej ustanawiają je „na podstawie i w granicach upoważnień zawartych w ustawie” [DU/1997/483#U art. 94].
- Ogłasza się je w wojewódzkim dzienniku urzędowym (m.in. akty wojewody, sejmiku, rady powiatu i rady gminy) [DU/2000/718#U art. 13]. Przepisy porządkowe ogłasza się w drodze obwieszczeń, a także w sposób zwyczajowo przyjęty na danym terenie [DU/2000/718#U art. 14].
- **Zakres bazy:** akty prawa miejscowego i dzienniki wojewódzkie nie są objęte naszą bazą (Dz.U. + M.P.). Dla uchwał gminy czy rozporządzeń wojewody szukaj w wojewódzkim dzienniku urzędowym lub BIP.

## 7. Akty wewnętrzne i Monitor Polski

- Uchwały Rady Ministrów oraz zarządzenia Prezesa Rady Ministrów i ministrów „mają charakter wewnętrzny i obowiązują tylko jednostki organizacyjnie podległe organowi wydającemu te akty.” Zarządzenia nie mogą stanowić podstawy decyzji wobec obywateli i innych podmiotów [DU/1997/483#U art. 93].
- Uchwały RM i zarządzenia PRM wydane na podstawie ustawy ogłasza się w Monitorze Polskim [DU/2000/718#U art. 10]. W bazie to kategoria `mp` – traktuj ją jako kontekst, nie jako ustawę.

## 8. Orzeczenia Trybunału Konstytucyjnego

- „Orzeczenia Trybunału Konstytucyjnego mają moc powszechnie obowiązującą i są ostateczne.” [DU/1997/483#U art. 190]
- Orzeczenie wchodzi w życie z dniem ogłoszenia, ale TK może odroczyć utratę mocy aktu: do 18 miesięcy dla ustawy, do 12 miesięcy dla innego aktu normatywnego [DU/1997/483#U art. 190].
- Orzeczenie o niezgodności aktu, na podstawie którego wydano prawomocne orzeczenie lub ostateczną decyzję, jest podstawą do wznowienia postępowania lub uchylenia decyzji [DU/1997/483#U art. 190].
- TK orzeka m.in. o zgodności ustaw z Konstytucją i o skardze konstytucyjnej [DU/1997/483#U art. 188]. Skargę konstytucyjną wnosi ten, czyje konstytucyjne wolności lub prawa zostały naruszone, po ostatecznym rozstrzygnięciu sądu lub organu [DU/1997/483#U art. 79]. Każdy sąd może przedstawić TK pytanie prawne [DU/1997/483#U art. 193].
- Orzeczenia TK dotyczące aktów ogłoszonych w Dz.U. ogłasza się w Dz.U., a dotyczące aktów z Monitora Polskiego – w Monitorze Polskim [DU/2000/718#U art. 9, 10].
- **W bazie** kategoria `orzeczenie` to wyroki TK ogłoszone w Dz.U., a obwieszczenia Prezesa TK o utracie mocy przepisów trafiają do kategorii `inne`. Nie są przepisem – wskazują, że przepis utracił lub traci moc. Zawsze sprawdź, czy dany artykuł w tekście ujednoliconym nie ma przypisu o utracie mocy (przykład: przypis do art. 2 k.p.c. o wyroku TK) [DU/1964/296#U art. 2].
- Pełne orzecznictwo TK jest poza bazą – patrz `gdzie-szukac-dalej`.

## 9. Kolizje przepisów: jak je rozstrzygać

Trzy klasyczne reguły kolizyjne **[WO]**: akt wyższej rangi ma pierwszeństwo przed niższym (lex superior), przepis szczególny przed ogólnym (lex specialis), nowszy przed starszym (lex posterior). Same przepisy często wprost wskazują relację:

- Kodeks cywilny sam zastrzega pierwszeństwo przepisu szczególnego: „Jeżeli przepis szczególny nie stanowi inaczej, termin przedawnienia wynosi sześć lat…” [DU/1964/93#U art. 118]. Dlatego dla umowy o dzieło liczy się art. 646 (2 lata) [DU/1964/93#U art. 646], a nie ogólne 6/3 lata.
- Kodeks karny: „Przepisy części ogólnej tego kodeksu stosuje się do innych ustaw przewidujących odpowiedzialność karną, chyba że ustawy te wyraźnie wyłączają ich zastosowanie.” [DU/1997/553#U art. 116]
- Prawo pracy: w sprawach nieunormowanych przepisami prawa pracy „stosuje się odpowiednio przepisy Kodeksu cywilnego, jeżeli nie są one sprzeczne z zasadami prawa pracy.” [DU/1974/141#U art. 300] Postanowienia umów o pracę „nie mogą być mniej korzystne dla pracownika niż przepisy prawa pracy” [DU/1974/141#U art. 18]; podobnie układy zbiorowe, regulaminy i statuty względem kodeksu [DU/1974/141#U art. 9].
- Procedura cywilna: przepisy o procesie stosuje się odpowiednio do innych rodzajów postępowań w kodeksie, „chyba że przepisy szczególne stanowią inaczej” [DU/1964/296#U art. 13].
- Pamiętaj o intertemporalności: który z dwóch przepisów jest „nowszy”, nie rozstrzyga sprawy, jeżeli przepisy przejściowe każą dalej stosować stare brzmienie (plik `wejscie-w-zycie-i-vacatio-legis`).

## 10. Gdzie ogłasza się które akty

| Dziennik | Co w nim ogłoszono (wg ustawy o ogłaszaniu aktów normatywnych) |
|---|---|
| Dziennik Ustaw | Konstytucja, ustawy, rozporządzenia z mocą ustawy, rozporządzenia (Prezydenta, RM, PRM, ministrów, KRRiT), teksty jednolite, orzeczenia TK dot. aktów z Dz.U. [DU/2000/718#U art. 9] |
| Monitor Polski | zarządzenia Prezydenta i uchwały RM / zarządzenia PRM wydane na podstawie ustawy, uchwały Sejmu i Senatu w określonych sprawach, teksty jednolite tych aktów [DU/2000/718#U art. 10] |
| Dzienniki ministrów i urzędów centralnych | akty normatywne organu wydającego dziennik [DU/2000/718#U art. 12] |
| Wojewódzki dziennik urzędowy | akty prawa miejscowego i inne [DU/2000/718#U art. 13] |

## 11. Przełożenie na kategorie w API

| Kategoria w API | Miejsce w hierarchii / znaczenie |
|---|---|
| `ujednolicone`, `jednolite` | treść ustaw, rozporządzeń i Konstytucji – podstawowe źródło odpowiedzi |
| `podstawowe` | akt w brzmieniu z dnia ogłoszenia (może być nieaktualny) |
| `zmieniajace` | nowelizacja – nie jest źródłem obowiązującej treści |
| `mp` | akty z Monitora Polskiego (uchwały Sejmu i Senatu, postanowienia Prezydenta, uchwały PKW, zarządzenia, umowy itd.) – często wewnętrzne lub jednostkowe |
| `orzeczenie` | wyroki Trybunału Konstytucyjnego ogłoszone w Dz.U. – nie przepis |
| `inne` | obwieszczenia (np. Prezesa TK o utracie mocy przepisu, PKW) – informacja, nie przepis |
| `umowa` | umowy międzynarodowe – sprawdź ratyfikację |
| `wyrok`, `ue` | uśpione źródła dodatkowe |

Szczegóły kategorii: plik `teksty-jednolite-ujednolicone-zmieniajace`.
