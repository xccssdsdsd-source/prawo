# Jak czytać prawo: metodyka dla agentów AI (search_law, get_article, get_act)

> **Data weryfikacji: 2026-10-11.** Stan danych: baza Prawo API z dnia 11.10.2026 (przepisy ogłoszone później nie są uwzględnione).
> **To nie jest porada prawna.** Ten plik opisuje, jak rzetelnie odpowiadać na pytania prawne narzędziami API; nie zastępuje prawnika ani ISAP (https://isap.sejm.gov.pl).
> Przykłady są oparte na rzeczywistych tekstach w bazie, a odnośniki w formie `[doc_id art. N]` zweryfikowano z tekstem. **[WO]** = wiedza ogólna, niezweryfikowana w danych. Uzupełnia `ai/AGENTS.md` (zasady, scenariusze), nie zastępuje go.

## W skrócie

Odpowiadaj tylko na podstawie tekstu pobranego `get_article`, nie z pamięci. Najpierw ustal, **który akt** i **jaka wersja** (ujednolicony / jednolity / z dnia ogłoszenia), potem **który przepis**, a na końcu sprawdź cztery rzeczy, które najczęściej zmieniają wynik: przepis szczególny, odesłania, przepisy przejściowe i nieaktualność. Zawsze dopisz „Stan danych na dzień <data_as_of>” i zastrzeżenie, że to nie jest porada prawna.

## 1. Narzędzia i ich parametry (zgodnie z serwerem MCP)

| Narzędzie | Parametry | Do czego |
|---|---|---|
| `search_law` | `query` (po polsku, krótko), `kategoria`, `act` (ELI aktu, np. `DU/1964/93`), `limit` (1–20, domyślnie 8) | znaleźć akt i artykuł; domyślnie nie zwraca kategorii `orzeczenie`, `umowa`, `inne` |
| `get_article` | `id` (ELI lub doc_id), `art` (np. `445` lub `46[1]`, przyjmuje też `art. 46¹`), `variant` (`U`) | dokładne brzmienie artykułu; bez `variant` preferuje `#U`, potem sam ELI |
| `get_act` | `id`, `variant`, `include_toc` | metadane aktu i spis artykułów z nagłówkami |

Każdy wynik niesie `kategoria`, `display_address`, `source_url`, `warnings` i `data_as_of`. Treść jest obcinana do 12 000 znaków (`truncated`).

## 2. Procedura odpowiedzi (krok po kroku)

1. **Zrozum pytanie.** Dziedzina (cywilne / pracy / karne / administracyjne / podatkowe), data zdarzenia, status stron (konsument, przedsiębiorca, pracownik), rodzaj sprawy. Gdy odpowiedź zależy od daty zdarzenia lub rodzaju stosunku – dopytaj (1–2 pytania) albo wyraźnie napisz założenia.
2. **Wyszukaj krótko.** 2–4 słowa kluczowe, nie całe pytanie: `przedawnienie umowa o dzieło`. Znasz artykuł i akt? Wpisz `art. 646 kodeks cywilny` albo zawęź `act=DU/1964/93`. Brak wyniku ≠ brak przepisu; spróbuj synonimów i innych kategorii.
3. **Wybierz właściwą wersję aktu.** Patrz `kategoria` i `doc_id`: `…#U` (ujednolicony) → najlepszy do cytowania; `jednolite` → obwieszczenie; `podstawowe` → brzmienie z dnia ogłoszenia (może być nieaktualne); `zmieniajace` → tylko polecenia nowelizacyjne (`teksty-jednolite-ujednolicone-zmieniajace`).
4. **Pobierz artykuł** `get_article`. Przeczytaj cały artykuł (wszystkie paragrafy, punkty), nie sam snippet z wyszukiwarki.
5. **Sprawdź sąsiedztwo.** Wyjątki i uściślenia ustawodawca ma umieszczać bezpośrednio po przepisie szczegółowym, którego dotyczą [DU/2026/300 § 23]; definicje bywają w przepisach ogólnych [DU/2026/300 § 21]. Czytaj kolejne artykuły i spis treści (`get_act`, `include_toc`).
6. **Przepis szczególny (lex specialis).** Przykład: ogólny termin przedawnienia to 6 lat lub 3 lata, ale „Jeżeli przepis szczególny nie stanowi inaczej…” [DU/1964/93#U art. 118], a dla umowy o dzieło przepis szczególny daje 2 lata [DU/1964/93#U art. 646]. Szukaj więc przepisów szczególnych dla swojego stanu faktycznego, zanim podasz regułę ogólną.
7. **Odesłania i „stosuje się odpowiednio”.** Przeczytaj przepisy, do których odsyła tekst. Przykłady: przepisy o procesie stosuje się odpowiednio do innych postępowań [DU/1964/296#U art. 13]; w sprawach nieunormowanych w prawie pracy stosuje się odpowiednio k.c. [DU/1974/141#U art. 300]. Odesłania są dynamiczne – dotyczą przepisu w brzmieniu obowiązującym w danym czasie, chyba że zaznaczono statyczne „w brzmieniu z dnia…” [DU/2026/300 § 159, 160].
8. **Delegacje do rozporządzeń.** Jeśli ustawa mówi, że szczegóły określi minister lub Prezes Rady Ministrów „w drodze rozporządzenia”, szczegóły są poza ustawą (przykład: wymagania techniczne dzienników urzędowych) [DU/2000/718#U art. 28c]. Znajdź rozporządzenie w bazie (kategorie `jednolite` lub `podstawowe`) i sprawdź, czy nie zmieniono go ani jego podstawy prawnej. Rozporządzenia wykonawcze mogą być wprost utrzymane w mocy przepisami przejściowymi na czas ograniczony, np. „jednak niedłużej niż przez 36 miesięcy od dnia wejścia w życie niniejszej ustawy” [DU/2026/516 art. 36].
9. **Przepisy przejściowe i intertemporalne.** Jeśli zdarzenie lub sprawa zaczęły się przed zmianą przepisów, nowe brzmienie może się nie stosować. Szukaj w akcie zmieniającym, np. „Do rzeczy znalezionych przed dniem wejścia w życie niniejszej ustawy stosuje się przepisy dotychczasowe.” [DU/2026/184 art. 3]. Szczegóły: `wejscie-w-zycie-i-vacatio-legis`.
10. **Nieaktualność.** Sprawdź: (a) czy to tekst ujednolicony, (b) przypis „Opracowano na podstawie: t.j. …” z listą ostatnich nowelizacji, np. przy ustroju sądów powszechnych: „Dz. U. z 2024 r. poz. 334, 1907, z 2025 r. poz. 526, 820, 1172, 1178, 1609, z 2026 r. poz. 26, 370, 1123.” [DU/2001/1070#U art. 2], (c) `data_as_of` – akty ogłoszone później nie są w bazie. Dla gorących tematów poszukaj aktów `zmieniajace` z bieżącego roku.
11. **Odpowiedz.** Użyj struktury z pkt 6 poniżej.

## 3. Pułapki w danych (z przykładami)

| Pułapka | Co się dzieje | Przykład w bazie |
|---|---|---|
| Spłaszczony indeks górny | art. 29¹ zapisany jako `291`; kolizja z właściwym art. 291 | k.p.: dwa różne rekordy `291` (informacja o warunkach zatrudnienia i przedawnienie) [DU/1974/141#U art. 291]; k.s.h.: art. 25¹ i art. 251 [DU/2000/1037#U art. 251]; wewnątrz paragrafu: „§ 11. Do okresu zatrudnienia, o którym mowa w § 1” oznacza § 1¹ [DU/1974/141#U art. 36] |
| Indeks w nawiasie kwadratowym | `442[1]` = art. 442¹ | [DU/1964/93#U art. 442¹]; dawny art. 442 jest uchylony: „Art. 442. (uchylony)” [DU/1964/93#U art. 442] |
| Artykuł wchłonięty do poprzedniego | brak osobnego rekordu, treść wewnątrz sąsiedniego artykułu | art. 446¹ k.c. jest w treści art. 446: „Art. 446[1].4) Z chwilą urodzenia dziecko może żądać naprawienia szkód doznanych przed urodzeniem.” [DU/1964/93#U art. 446]; art. 124 k.p.k. wewnątrz art. 123 [DU/1997/555#U art. 123] |
| Art. 1 w fragmencie wstępnym | `art=1` nic nie zwraca | ustawa o Sądzie Najwyższym [DU/2018/5#U ord 1] |
| Przypisy wklejone w treść | numery „1)” i opisy dyrektyw na końcu artykułu | [DU/1964/93#U art. 5]; przypis o utracie mocy na podstawie obwieszczenia Prezesa TK: „Zdanie drugie utraciło moc z dniem 23 grudnia 1997 r.” [DU/1964/93#U art. 448]; przypis o wyroku TK „sygn. akt SK. 12/99” [DU/1964/296#U art. 2] |
| Przyszłe brzmienie w nawiasach | `< >` nowe, `[ ]` stare; adnotacja „wejdzie w życie z dn. …” | art. 94³ k.p. (mobbing) – nowe brzmienie od 5.11.2026 [DU/1974/141#U art. 942]; art. 124 k.p.k. [DU/1997/555#U art. 123]; zestawienie: `nadchodzace-zmiany` |
| Nagłówki stron w obwieszczeniach | „Dziennik Ustaw – 10 – Poz. 795” w treści | [DU/2026/795 art. 60] |
| `announcement_date` ≠ data ogłoszenia | to data wydania aktu | ustawa z 23.01.2026 ogłoszona 18.02.2026: „Warszawa, dnia 18 lutego 2026 r. Poz. 184” [DU/2026/184 ord 1] |
| `is_consolidated=false` dla `jednolite` | flaga dotyczy tylko `#U` | patrz `teksty-jednolite-ujednolicone-zmieniajace` |
| Duplikaty widoków | `DU/1964/296#U` i `DU/2026/468#U` prawie identyczne | porównanie k.p.c. (2026-10-11): 1950 wspólnych artykułów, 3 różnią się |
| „(uchylony)” | numer został, treści brak | [DU/1964/93#U art. 123] (§ 2), [DU/1964/93#U art. 117] (§ 3) |

## 4. Lex specialis i kolizje – lista kontrolna

1. Czy akt ma własne przepisy ogólne i wyjątki dla swojej dziedziny (np. k.p. wobec k.c.)? [DU/1974/141#U art. 300]
2. Czy przepis mówi „chyba że ustawa stanowi inaczej” / „przepis szczególny”? [DU/1964/296#U art. 13] [DU/1964/93#U art. 118]
3. Czy w prawie pracy postanowienie umowy jest mniej korzystne niż przepis (wtedy nieważne)? [DU/1974/141#U art. 18]
4. Czy kodeks karny stosuje się do ustaw szczególnych? Tak, chyba że wyraźnie wyłączono [DU/1997/553#U art. 116].
5. Czy akt wyższego rzędu (Konstytucja, ratyfikowana umowa) nie wyłącza przepisu? [DU/1997/483#U art. 91] (zob. `hierarchia-zrodel-prawa`).

## 5. Terminy – nie licz z głowy

Zawsze weryfikuj termin w tekście przepisu i opisz zasady liczenia (`terminy-i-przedawnienie`). Przykład: odwołanie od wypowiedzenia umowy o pracę – 21 dni od doręczenia pisma [DU/1974/141#U art. 264]; nie podawaj liczby dni z pamięci, bo terminy się zmieniają. Przy terminach zawsze dopisz: licząc od daty doręczenia/ogłoszenia, sobota jak dzień wolny [DU/1964/93#U art. 115].

## 6. Struktura dobrej odpowiedzi

1. **Wniosek w jednym zdaniu** (z zastrzeżeniem: „zasadniczo”, „co do zasady”).
2. **Podstawa prawna** – akt, jednostka, `display_address`, rodzaj tekstu; cytat dosłowny w cudzysłowie; link `source_url`.
3. **Założenia i pytania** – co przyjąłeś (data, status stron), czego brakuje.
4. **Wyjątki i ryzyka** – przepis szczególny, przepisy przejściowe, terminy.
5. **Niepewność** – co może zmienić wynik; kiedy konieczny prawnik (terminy sądowe, sprawy karne, duże kwoty).
6. **Stopka:** „Stan danych na dzień <data_as_of>. Przepisy ogłoszone później nie są uwzględnione. To informacja ogólna, nie porada prawna; sprawdź aktualność w ISAP.”

Wzorzec stopki trzeba dodać nawet wtedy, gdy wynik wygląda na pewny.

## 7. Przykład rozumowania: przedawnienie roszczenia z umowy o dzieło

1. `search_law(query="przedawnienie umowa o dzieło")` → k.c. art. 646.
2. `get_article(id="DU/1964/93", art="646")` → „Roszczenia wynikające z umowy o dzieło przedawniają się z upływem lat dwóch od dnia oddania dzieła, a jeżeli dzieło nie zostało oddane – od dnia, w którym zgodnie z treścią umowy miało być oddane.” [DU/1964/93#U art. 646]
3. Sprawdź regułę ogólną i jej zastrzeżenia: art. 118 (6/3 lata; przepis szczególny ma pierwszeństwo) [DU/1964/93#U art. 118]. Zdanie drugie art. 118 przesuwa koniec terminu na ostatni dzień roku kalendarzowego, chyba że termin jest krótszy niż dwa lata [DU/1964/93#U art. 118]; czy i jak ta reguła dotyczy terminu z przepisu szczególnego, nie wynika wprost z tekstu – nie rozstrzygaj tego sam, zaznacz niepewność i odeślij do orzecznictwa/prawnika **[WO]**.
4. Sprawdź zawieszenie i przerwanie biegu [DU/1964/93#U art. 121, 123] oraz to, że po upływie terminu dłużnik może uchylić się od zaspokojenia roszczenia [DU/1964/93#U art. 117].
5. Dopytaj o datę oddania dzieła i czy strona jest konsumentem [DU/1964/93#U art. 22¹].
6. Odpowiedz z zastrzeżeniami (pkt 6).

## 8. Czego nie wolno

- Wymyślać numerów artykułów i treści. Każdy numer zweryfikuj `get_article` (lub w ostateczności napisz „nie zweryfikowałem”).
- Cytować `zmieniajace` jako obowiązującą treść; polegać na tekście `podstawowe` jako aktualnym.
- Obiecywać wyniku sprawy ani kwot (np. zadośćuczynienie to uznanie sądu).
- Pomijać `warnings`, `truncated`, `data_as_of`.
- Zakładać, że baza zawiera orzecznictwo, prawo UE, akty prawa miejscowego – nie zawiera (`gdzie-szukac-dalej`).
- Ujawniać klucza API (w trybie zamkniętym).

## 9. Kiedy odesłać do prawnika lub oficjalnego źródła **[WO]**

Gdy chodzi o termin sądowy, sprawę karną, postępowanie przed organem z krótkim terminem, duże kwoty, podatki o zmieniających się stawkach, albo gdy wynik zależy od orzecznictwa (którego baza nie ma). Wtedy podaj ogólne informacje, zaznacz granice i skieruj do ISAP / prawnika.
