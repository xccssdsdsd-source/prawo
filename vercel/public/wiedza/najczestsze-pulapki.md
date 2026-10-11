# Najczęstsze pułapki przy czytaniu i stosowaniu polskiego prawa

> **Data weryfikacji: 2026-10-11.** Stan danych: baza Prawo API z dnia 11.10.2026 (przepisy ogłoszone później nie są uwzględnione).
> **To nie jest porada prawna** – to informacja ogólna oparta na tekstach przepisów. Aktualność zawsze sprawdź w ISAP (https://isap.sejm.gov.pl) lub u prawnika.
> Odnośniki w formie `[doc_id art. N]` zostały sprawdzone z tekstem w bazie. **[WO]** = wiedza ogólna, niezweryfikowana w danych. Pułapki techniczne danych (numeracja, przypisy) są też w `jak-czytac-prawo-dla-agentow-ai`.

## W skrócie

Najwięcej błędów bierze się z pięciu rzeczy: (1) cytowania nieobowiązującej lub niewłaściwej wersji przepisu, (2) pominięcia przepisu szczególnego, (3) pominięcia przepisów przejściowych, (4) błędnego liczenia terminów, (5) braku informacji o stanie danych. Poniżej lista ze sprawdzonymi przykładami.

## A. Wersja i aktualność przepisu

### 1. Akt zmieniający to nie obowiązująca treść
Ustawa o zmianie… zawiera polecenia nowelizacyjne, nie pełny tekst. Przykład: ustawa z 23 stycznia 2026 r. mówi „W ustawie z dnia 20 lutego 2015 r. o rzeczach znalezionych … wprowadza się następujące zmiany” [DU/2026/184 art. 1], a art. 187 k.c. otrzymuje w niej nowe brzmienie [DU/2026/184 art. 2]. Aktualną treść art. 187 czytaj w tekście ujednoliconym [DU/1964/93#U art. 187]. **Co robić:** kategoria `zmieniajace` → szukaj `#U`.

### 2. Brzmienie z dnia ogłoszenia (`podstawowe`) może być nieaktualne
Rozporządzenia i wiele ustaw bez tekstu jednolitego jest w bazie tylko w brzmieniu pierwotnym. **Co robić:** poszukaj aktów `zmieniajace` o tym samym przedmiocie; ostrzeż użytkownika (pole `warnings`).

### 3. „(uchylony)” to brak przepisu
Numer pozostaje, treści nie ma: art. 442 k.c. to „(uchylony)” [DU/1964/93#U art. 442]; art. 123 § 2 k.c. również [DU/1964/93#U art. 123]. Odpowiedź ma opierać się na przepisie, który obowiązuje w tej materii (np. dla szkód z czynów niedozwolonych – art. 442¹ k.c.) [DU/1964/93#U art. 442¹].

### 4. Przyszłe brzmienie (`< >`) jeszcze nie obowiązuje
W k.p. nowe brzmienie art. 94³ (definicja mobbingu) jest już w tekście w nawiasach `< >`, ale „wejdzie w życie z dn. 5.11.2026 r.” [DU/1974/141#U art. 942]; w k.p.k. wklejono adnotację o nowym brzmieniu art. 124 od 1.10.2029 r. [DU/1997/555#U art. 123]. **Co robić:** nie cytuj przyszłego brzmienia jako obowiązującego; zestawienie zapowiedzianych zmian: `nadchodzace-zmiany`.

### 5. Tekst jednolity ≠ najnowszy stan
Obwieszczenie opisuje stan prawny na wskazany dzień i listę zmian; zmiany po tej dacie nie są w nim ujęte. Przykład: t.j. k.c. uwzględnia stan na 19 maja 2026 r. [DU/2026/795 ord 1]. **Co robić:** sprawdź `#U` i akty `zmieniajace` z późniejszych miesięcy.

### 6. Dane są na dzień `data_as_of`
Przepisy ogłoszone później nie są w bazie, a ELI pokazywało w dniu weryfikacji nowsze pozycje (patrz `gdzie-szukac-dalej`). **Co robić:** zawsze „Stan danych na dzień …”.

### 7. Orzeczenie TK może uchylić przepis, a tekst ujednolicony tylko to odnotować w przypisie
Wyroki TK mają moc powszechnie obowiązującą i są ostateczne [DU/1997/483#U art. 190]. W tekstach widać to w przypisach, np. utrata mocy przepisu k.p.c. na podstawie wyroku TK [DU/1964/296#U art. 2] albo k.c. na podstawie obwieszczenia Prezesa TK: „Zdanie drugie utraciło moc z dniem 23 grudnia 1997 r.” [DU/1964/93#U art. 448]. **Co robić:** czytaj przypisy w treści artykułu; kategoria `orzeczenie` (wyroki TK) sama nie jest przepisem.

## B. Który przepis stosować

### 8. Przepis szczególny wypiera ogólny
- Ogólne terminy przedawnienia (6/3 lata) ustępują przepisom szczególnym [DU/1964/93#U art. 118]: umowa o dzieło – 2 lata [DU/1964/93#U art. 646]; sprzedaż w działalności przedsiębiorstwa – 2 lata [DU/1964/93#U art. 554]; rachunek bankowy – 2 lata [DU/1964/93#U art. 731]; szkoda z czynu niedozwolonego – 3 lata od dowiedzenia się, najpóźniej 10 lat od zdarzenia [DU/1964/93#U art. 442¹]; w prawie pracy – 3 lata [DU/1974/141#U art. 291].
- Odpowiedzialność odszkodowawcza: ogólna zasada „Kto z winy swej wyrządził drugiemu szkodę, obowiązany jest do jej naprawienia.” [DU/1964/93#U art. 415] ma wyjątki w przepisach szczególnych.
- W prawie pracy K.c. stosuje się tylko odpowiednio i gdy nie jest sprzeczny z zasadami prawa pracy [DU/1974/141#U art. 300].

### 9. „Stosuje się odpowiednio” i odesłania
Przepisy o procesie stosuje się odpowiednio do innych postępowań w kodeksie [DU/1964/296#U art. 13]. Odesłania są dynamiczne [DU/2026/300 § 159] – przy zmianie przepisu, do którego odsyła przepis, zmienia się też efekt odesłania.

### 10. Konsument a przedsiębiorca
Konsument to osoba fizyczna dokonująca z przedsiębiorcą czynności niezwiązanej bezpośrednio z jej działalnością [DU/1964/93#U art. 22¹]; przedsiębiorca – osoba prowadząca we własnym imieniu działalność gospodarczą lub zawodową [DU/1964/93#U art. 43¹]. Status wpływa np. na przedawnienie: po upływie terminu „nie można domagać się zaspokojenia roszczenia przysługującego przeciwko konsumentowi” [DU/1964/93#U art. 117], a roszczenia związane z działalnością gospodarczą mają 3 lata [DU/1964/93#U art. 118]. Do umów z konsumentami zajrzyj też do ustawy o prawach konsumenta (`kodeksy-i-glowne-ustawy`).

### 11. Prawo pracy: „korzystniejsze dla pracownika”
Postanowienia umowy o pracę nie mogą być mniej korzystne niż przepisy prawa pracy, a mniej korzystne są nieważne [DU/1974/141#U art. 18]; układy zbiorowe, regulaminy i statuty też nie mogą być mniej korzystne niż kodeks [DU/1974/141#U art. 9]. **Co robić:** nie stosuj mechanicznie zasady swobody umów z k.c. [DU/1964/93#U art. 353¹] do stosunku pracy.

### 12. Rozporządzenia, uchwały i zarządzenia – różna siła
Rozporządzenie jest źródłem prawa na podstawie upoważnienia ustawy [DU/1997/483#U art. 92]; zarządzenia i uchwały RM obowiązują tylko jednostki podległe i nie mogą stanowić podstawy decyzji wobec obywateli [DU/1997/483#U art. 93]. Akty z Monitora Polskiego (kategoria `mp`) są często wewnętrzne [DU/2000/718#U art. 10].

### 13. Rozporządzenie wykonawcze po zmianie ustawy
Gdy zmienia się upoważnienie, los rozporządzenia reguluje się w przepisach przejściowych [DU/2026/300 § 32, 33]. W praktyce zdarza się zachowanie mocy na czas określony: „niedłużej niż przez 36 miesięcy” [DU/2026/516 art. 36]. **Co robić:** nie zakładaj, że stare rozporządzenie nadal obowiązuje po zmianie ustawy.

### 14. Podobne nazwy aktów
Ustawa o ochronie danych osobowych z 10 maja 2018 r. i ustawa z 14 grudnia 2018 r. o ochronie danych osobowych przetwarzanych w związku z zapobieganiem i zwalczaniem przestępczości to różne akty (`kodeksy-i-glowne-ustawy`); pierwsza odnosi się do RODO [DU/2018/1000#U art. 1]. Podobnie Prawo upadłościowe i Prawo restrukturyzacyjne.

## C. Czas: wejście w życie, przepisy przejściowe, terminy

### 15. Data aktu, data ogłoszenia, data wejścia w życie to trzy różne daty
`announcement_date` w bazie to data wydania aktu; ogłoszenie i wejście w życie liczy się osobno. Ustawa z 23.01.2026 została ogłoszona 18.02.2026 [DU/2026/184 ord 1] i weszła w życie po 3 miesiącach [DU/2026/184 art. 4], tj. 19 maja 2026 r. (obliczenie wg art. 6 ustawy o ogłaszaniu aktów) [DU/2000/718#U art. 6].

### 16. Vacatio legis i wejście etapami
Domyślnie 14 dni od ogłoszenia [DU/2000/718#U art. 4], ale ustawy często różnicują terminy: „Ustawa wchodzi w życie po upływie 14 dni od dnia ogłoszenia, z wyjątkiem:” [DU/2026/516 art. 38]; nowelizacja k.p.c. i innych ustaw (Dz.U. 2025 poz. 1172): od 1 marca 2026 r. z wyjątkami [DU/2025/1172 art. 16].

### 17. Przepisy przejściowe przesądzają, co się stosuje
Do rzeczy znalezionych przed zmianą – przepisy dotychczasowe [DU/2026/184 art. 3]; do spraw w toku – dotychczasowe albo nowe, zależnie od zapisu [DU/2026/516 art. 15] [DU/2026/516 art. 25]; do umów zawartych przed zmianą – dotychczasowe [DU/2025/1172 art. 13]. **Co robić:** nigdy nie kończ analizy na tekście ujednoliconym, jeśli zdarzenie jest sprzed zmiany.

### 18. Prawo karne: ustawa z czasu czynu i ustawa względniejsza
Odpowiedzialność karna tylko za czyn zabroniony przez ustawę obowiązującą w czasie jego popełnienia [DU/1997/483#U art. 42] [DU/1997/553#U art. 1]; jeżeli w czasie orzekania obowiązuje inna ustawa, stosuje się nową, chyba że poprzednia jest względniejsza dla sprawcy [DU/1997/553#U art. 4]. **Co robić:** ustal datę czynu.

### 19. Terminy: doręczenie, sobota, zawitość
- Termin liczy się często od doręczenia z uzasadnieniem, np. apelacja cywilna – 2 tygodnie od doręczenia wyroku z uzasadnieniem [DU/1964/296#U art. 369], apelacja karna – 14 dni [DU/1997/555#U art. 445].
- Sobota i dzień wolny przesuwają koniec terminu [DU/1964/93#U art. 115] [DU/1960/168#U art. 57].
- Terminy zawite: czynność po terminie jest bezskuteczna, a zawite są terminy do wnoszenia środków zaskarżenia [DU/1997/555#U art. 122].
- Termin 7 dni na wniosek o uzasadnienie wyroku karnego jest zawity [DU/1997/555#U art. 422]; przywrócenie – w 7 dni od ustania przeszkody [DU/1997/555#U art. 126].
- Termin „tydzień” a „7 dni” – używaj zapisu z przepisu.

### 20. Terminy mogły się zmieniać
Odwołanie od wypowiedzenia umowy o pracę – dzisiaj 21 dni [DU/1974/141#U art. 264]; dla starszych zdarzeń sprawdź przepisy przejściowe ustaw, które zmieniały termin. Baza nie zawiera historii brzmień.

### 21. Przepisy epizodyczne wygasają
Przepisy czasowe obowiązują tylko przez określony okres [DU/2026/300 § 29b]; dla dat przyszłych sprawdź, czy nie wygasły.

## D. Zakres i sposób użycia bazy

### 22. Brak wyniku ≠ brak przepisu
Baza obejmuje obowiązujące Dz.U. i M.P. oraz teksty ujednolicone; nie ma aktów prawa miejscowego, prawa UE, orzecznictwa sądów, projektów ustaw (`gdzie-szukac-dalej`).

### 23. Fragment ≠ cały przepis
Wynik wyszukiwarki to fragment; długie artykuły są dzielone, a wyjątki bywają w kolejnych paragrafach i artykułach. Przeczytaj cały artykuł `get_article`.

### 24. Pomyłki w numeracji
Spłaszczone indeksy (art. 29¹ k.p. jako „291”, art. 25¹ k.s.h. jako „251”) i wchłonięte artykuły (art. 446¹ k.c. w treści art. 446) wymagają czytania nagłówka i treści [DU/1974/141#U art. 291] [DU/2000/1037#U art. 251] [DU/1964/93#U art. 446]. Szczegóły: `jak-czytac-prawo-dla-agentow-ai`, pkt 3.

### 25. Kwoty, stawki, progi
Zmieniają się często i bywają w rozporządzeniach lub ustawach rocznych; nie podawaj ich z pamięci **[WO]**. Przykład progu w tekście przepisu: właściwość sądu okręgowego przy wartości przedmiotu sporu powyżej stu tysięcy złotych [DU/1964/296#U art. 17].

### 26. Pewność i porada
Nie używaj sformułowań typu na pewno, wygrasz; wysokości zadośćuczynienia (np. za krzywdę najbliższych zmarłego) ocenia sąd [DU/1964/93#U art. 446]. Zawsze podkreśl, że to informacja ogólna, nie porada prawna.

## E. Szybka lista kontrolna

1. Którą wersję czytam (ujednolicony / jednolity / podstawowy / zmieniający)?
2. Czy artykuł nie jest „(uchylony)” ani przyszłym brzmieniem?
3. Czy jest przepis szczególny?
4. Czy są odesłania / „odpowiednio”?
5. Jakie jest wejście w życie i przepisy przejściowe dla daty zdarzenia?
6. Jaki termin i od kiedy się liczy?
7. Czy mam dostęp do tego rodzaju źródła (UE, orzecznictwo)?
8. „Stan danych na dzień …” + zastrzeżenie.
