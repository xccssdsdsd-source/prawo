# Wejście w życie, vacatio legis i przepisy przejściowe

> **Data weryfikacji: 2026-10-11.** Stan danych: baza Prawo API z dnia 11.10.2026 (przepisy ogłoszone później nie są uwzględnione).
> **To nie jest porada prawna** – to informacja ogólna oparta na tekstach przepisów. Aktualność zawsze sprawdź w ISAP (https://isap.sejm.gov.pl) lub u prawnika.
> Odnośniki w formie `[doc_id art. N]` zostały sprawdzone z tekstem w bazie. **[WO]** = wiedza ogólna, niezweryfikowana w danych – zweryfikuj w ISAP.

## W skrócie

Przepis zaczyna obowiązywać po ogłoszeniu i po upływie vacatio legis (zwykle 14 dni), chyba że akt stanowi inaczej. Termin liczy się od **dnia ogłoszenia w dzienniku** (nie od daty podpisania czy uchwalenia). Stare sprawy bywają nadal rozstrzygane według starych przepisów – to rozstrzygają przepisy przejściowe w akcie zmieniającym. Nasza baza zawiera tylko obecne brzmienia, więc dla zdarzeń z przeszłości trzeba osobno ustalić, jaki przepis obowiązywał wtedy.

## 1. Zasada ogólna: ogłoszenie i 14 dni

- Ogłoszenie jest warunkiem wejścia w życie ustaw, rozporządzeń i aktów prawa miejscowego [DU/1997/483#U art. 88].
- Ogłoszenie aktu normatywnego w dzienniku urzędowym jest obowiązkowe [DU/2000/718#U art. 2].
- „Akty normatywne, zawierające przepisy powszechnie obowiązujące, ogłaszane w dziennikach urzędowych wchodzą w życie po upływie czternastu dni od dnia ich ogłoszenia, chyba że dany akt normatywny określi termin dłuższy.” [DU/2000/718#U art. 4]
- W uzasadnionych przypadkach akt może wejść w życie w terminie krótszym niż 14 dni; gdy „ważny interes państwa” wymaga natychmiastowego wejścia w życie (i zasady demokratycznego państwa prawnego nie stoją temu na przeszkodzie), dniem wejścia w życie może być dzień ogłoszenia [DU/2000/718#U art. 4].
- Przepisy porządkowe wchodzą w życie po upływie trzech dni od ogłoszenia (z możliwością skrócenia w razie zagrożenia życia, zdrowia lub mienia) [DU/2000/718#U art. 4]. Ogłasza się je w drodze obwieszczeń, a za dzień ogłoszenia uważa się dzień wskazany w obwieszczeniu [DU/2000/718#U art. 14].
- Zasady techniki prawodawczej zalecają, by ustawa wchodziła w życie w całości w jednym terminie; różne terminy są wyjątkiem [DU/2026/300 § 44]. Typowe brzmienia przepisu o wejściu w życie (14 dni, z dniem następującym po ogłoszeniu, pierwszego dnia miesiąca, z dniem oznaczonym kalendarzowo, z dniem ogłoszenia, z wyjątkami) wylicza § 45 ZTP [DU/2026/300 § 45].

## 2. Dzień ogłoszenia – skąd go wziąć

- Dniem ogłoszenia aktu jest dzień jego ogłoszenia w postaci elektronicznej na stronie internetowej organu wydającego dziennik urzędowy; ten dzień umieszcza się w obrębie nagłówka strony [DU/2000/718#U art. 20].
- Dzienniki Ustaw i Monitor Polski wydaje Prezes Rady Ministrów przy pomocy Rządowego Centrum Legislacji [DU/2000/718#U art. 21]. Są dostępne nieodpłatnie na stronach RCL [DU/2000/718#U art. 28b].
- **Pułapka w naszych danych:** pole `announcement_date` w fragmentach to data wydania/uchwalenia aktu (z tytułu), nie data ogłoszenia. Przykład: ustawa z 23 stycznia 2026 r. ma nagłówek „Warszawa, dnia 18 lutego 2026 r. Poz. 184” [DU/2026/184 ord 1]. Datę ogłoszenia czytaj z nagłówka Dziennika Ustaw w pierwszym fragmencie tekstu aktu (dla aktów z kategorii `zmieniajace`/`jednolite`) albo z ELI (pole `promulgation`).
- Rok w adresie publikacyjnym (np. Dz.U. 2018 poz. 5) to rok ogłoszenia – ustawa o Sądzie Najwyższym z 8.12.2017 r. została ogłoszona w 2018 r. [DU/2018/5#U ord 1].

## 3. Jak liczyć termin wejścia w życie

Ustawa o ogłaszaniu aktów normatywnych: przy obliczaniu terminu określonego w dniach nie uwzględnia się dnia ogłoszenia (z wyjątkiem aktów wchodzących w życie z dniem ogłoszenia); terminy w tygodniach, miesiącach i latach kończą się z upływem dnia, który nazwą lub datą odpowiada dniowi ogłoszenia, a gdyby takiego dnia w ostatnim miesiącu nie było – z upływem ostatniego dnia miesiąca [DU/2000/718#U art. 6].

Przykłady (obliczenia własne, 2026-10-11, zgodne z art. 6):

1. **14 dni.** Akt ogłoszony 8 października 2026 r.: dzień ogłoszenia się nie liczy, 14. dzień to 22 października, więc akt wchodzi w życie po upływie tego dnia – **23 października 2026 r.** Sobota czy dzień wolny na końcu vacatio legis nie przesuwają terminu **[WO]** (reguła art. 115 k.c. dotyczy terminów do wykonania czynności, nie wejścia w życie aktu) [DU/1964/93#U art. 115].
2. **3 miesiące.** Ustawa z 23 stycznia 2026 r. o zmianie ustawy o rzeczach znalezionych i Kodeksu cywilnego (Dz.U. 2026 poz. 184): „Ustawa wchodzi w życie po upływie 3 miesięcy od dnia ogłoszenia.” [DU/2026/184 art. 4] Ogłoszona 18 lutego 2026 r. [DU/2026/184 ord 1]; termin 3 miesięcy kończy się z upływem 18 maja, więc ustawa weszła w życie **19 maja 2026 r.** Zgadza się to z obwieszczeniem o tekście jednolitym k.c., które uwzględnia stan prawny na dzień 19 maja 2026 r. i zmiany wprowadzone tą ustawą [DU/2026/795 ord 1].
3. **Wejście etapami.** Ustawa z 13 marca 2026 r. (Dz.U. 2026 poz. 516) przewiduje 14 dni, z wyjątkami: niektóre przepisy wchodzą w życie z dniem następującym po dniu ogłoszenia, inne po upływie sześciu miesięcy [DU/2026/516 art. 38]. Stan obowiązywania trzeba więc ustalać osobno dla każdego przepisu.
4. **Data kalendarzowa i etapy.** Ustawa nowelizująca k.p.c. i inne akty: wejście w życie „z dniem 1 marca 2026 r.” z wyjątkami (1 czerwca 2026 r., 1 marca 2027 r., po 14 dniach, po 3 miesiącach) [DU/2025/1172 art. 16].

## 4. Moc wsteczna i zasada lex retro non agit

- Ustawa o ogłaszaniu aktów nie wyłącza możliwości nadania mocy wstecznej, jeżeli zasady demokratycznego państwa prawnego nie stoją temu na przeszkodzie [DU/2000/718#U art. 5]. ZTP opisują zapis „z mocą od dnia…” [DU/2026/300 § 51].
- Kodeks cywilny: „Ustawa nie ma mocy wstecznej, chyba że to wynika z jej brzmienia lub celu.” [DU/1964/93#U art. 3]
- Prawo karne: odpowiedzialności karnej podlega tylko ten, kto dopuścił się czynu zabronionego pod groźbą kary przez ustawę obowiązującą w czasie jego popełnienia [DU/1997/483#U art. 42] [DU/1997/553#U art. 1]. Jeśli w czasie orzekania obowiązuje inna ustawa, stosuje się nową, chyba że poprzednia jest względniejsza dla sprawcy [DU/1997/553#U art. 4].
- Rozporządzenia wykonawcze można ogłosić po ogłoszeniu ustawy, a przed jej wejściem w życie, ale nie mogą wejść w życie wcześniej niż ustawa [DU/2000/718#U art. 7].

## 5. Przepisy przejściowe i dostosowujące

Co to jest: przepisy, które regulują wpływ nowej albo znowelizowanej ustawy na stosunki powstałe pod działaniem dotychczasowych przepisów – w tym, że do nich stosuje się przepisy dotychczasowe [DU/2026/300 § 30]. Rozstrzygają m.in. los postępowań w toku, czynności dokonanych pod starym prawem oraz to, czy i na jak długo zachowują moc dotychczasowe przepisy wykonawcze [DU/2026/300 § 30]. Rozwiązania przejściowe i dostosowujące mają być ukształtowane w sposób nieuciążliwy dla adresatów [DU/2026/300 § 36]; przepisy dostosowujące nakazują np. dostosowanie się do nowych wymogów w wyznaczonym terminie [DU/2026/300 § 35].

Typowe sformułowania w praktyce (sprawdzone na aktach 2025–2026):

- Stare przepisy dla starych zdarzeń: „Do rzeczy znalezionych przed dniem wejścia w życie niniejszej ustawy stosuje się przepisy dotychczasowe.” [DU/2026/184 art. 3]
- Stare przepisy dla spraw w toku: „Do spraw spornych dotyczących odmowy zawarcia umowy o przyłączenie do sieci … wszczętych i niezakończonych przed dniem wejścia w życie niniejszej ustawy stosuje się przepisy ustawy zmienianej w art. 1 w brzmieniu dotychczasowym.” [DU/2026/516 art. 15]
- Nowe przepisy dla spraw w toku: „Do postępowań w sprawach … wszczętych i niezakończonych przed dniem wejścia w życie niniejszej ustawy stosuje się przepisy ustawy zmienianej w art. 1 w brzmieniu nadanym niniejszą ustawą.” [DU/2026/516 art. 25]; podobnie dla k.p.c.: do spraw wszczętych i niezakończonych stosuje się przepisy w brzmieniu nadanym ustawą [DU/2025/1172 art. 14].
- Stare umowy: „Do umów zawartych przed dniem wejścia w życie niniejszego przepisu stosuje się przepisy ustaw zmienianych … w brzmieniu dotychczasowym.” [DU/2025/1172 art. 13]
- Rozporządzenia wykonawcze: „Dotychczasowe przepisy wykonawcze … zachowują moc … jednak niedłużej niż przez 36 miesięcy od dnia wejścia w życie niniejszej ustawy” [DU/2026/516 art. 36]; analogicznie 12 miesięcy w innym akcie [DU/2025/1172 art. 15].

**Gdzie te przepisy znaleźć:** w ostatnich artykułach **aktu zmieniającego** (kategoria `zmieniajace`) albo ustawy wprowadzającej. W tekście ujednoliconym kodeksu ich zwykle nie ma – zostają w akcie zmieniającym [DU/2026/184 art. 3]. Dlatego pytając o zdarzenie sprzed zmiany, sprawdź akt zmieniający tej zmiany, a nie tylko tekst ujednolicony.

## 6. Procedura: co się stosuje do spraw w toku

**[WO]** Nowe przepisy procesowe co do zasady stosuje się do spraw w toku, o ile ustawodawca nie zastrzegł inaczej; przepisy materialne – do zdarzeń po wejściu w życie (zasada niedziałania wstecz, art. 3 k.c.). Wyjątki wprowadzają przepisy przejściowe (pkt 5) – zawsze je sprawdź, np. w nowelizacji k.p.c. [DU/2025/1172 art. 14].

## 7. Przepisy epizodyczne i czasowe

Przepisy, które obowiązują tylko przez określony czas, nazywa się epizodycznymi; ZTP przewidują, że okres obowiązywania określa się kalendarzowo albo liczbą dni/tygodni/miesięcy/lat od wejścia w życie [DU/2026/300 § 29b]. Ustawa może też mieć wyznaczony termin utraty mocy [DU/2026/300 § 52]. Takie przepisy znikają bez osobnej nowelizacji – przy odpowiedzi na dzień z przyszłości sprawdź, czy nie wygasły.

## 8. Przepisy, które „już uchwalono”, a jeszcze nie obowiązują

- W tekstach ujednoliconych przyszłe brzmienia bywają oznaczone nawiasami `< >` z adnotacją o dacie wejścia w życie (patrz `jak-czytac-akt-prawny`, pkt 4); przykłady: nowe brzmienie art. 94³ k.p. od 5.11.2026 r. [DU/1974/141#U art. 942] oraz art. 124 k.p.k. od 1.10.2029 r. [DU/1997/555#U art. 123]. Zestawienie zapowiedzianych zmian głównych aktów: `nadchodzace-zmiany`.
- Wykaz aktów podpisanych, a jeszcze nieogłoszonych, prowadzi RCL (rcl.gov.pl) – nie ma ich w tej bazie (patrz `gdzie-szukac-dalej`).
- Akty ogłoszone po dacie `data_as_of` w ogóle nie są w bazie, nawet jeśli już obowiązują. W odpowiedzi podawaj „Stan danych na dzień …” i zastrzeżenie.

## 9. Procedura odpowiedzi „czy przepis obowiązuje / od kiedy”

1. Ustal akt i artykuł (`search_law`, `get_article`) oraz kategorię tekstu (`ujednolicone` / `jednolite`).
2. Sprawdź, czy w treści nie ma adnotacji o przyszłym brzmieniu (`< >`) lub „(uchylony)”.
3. Znajdź akt zmieniający (kategoria `zmieniajace`) i przeczytaj jego ostatnie artykuły: wejście w życie i przepisy przejściowe.
4. Weź datę ogłoszenia z nagłówka Dziennika Ustaw, nie z `announcement_date`; policz termin według art. 6 ustawy o ogłaszaniu aktów.
5. Zapytaj użytkownika o datę zdarzenia/wszczęcia sprawy, jeśli ma znaczenie.
6. Odpowiedz z zastrzeżeniem: „Stan danych na dzień 11.10.2026; sprawdź w ISAP”.
