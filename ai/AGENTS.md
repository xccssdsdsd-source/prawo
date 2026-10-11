# AGENTS.md – jak korzystać z API prawa polskiego (Dz.U. + M.P.)

Instrukcja dla każdego agenta/modelu AI (Claude, GPT, Gemini, Llama…). English hints in parentheses.

Jak podłączyć klienta (Claude, Gemini, ChatGPT, Cursor, VS Code…): strona `/podlacz.html` na wdrożeniu (kroki, snippety, test połączenia). Ten plik opisuje, jak KORZYSTAĆ z już podłączonego API.

Narzędzia (MCP) / endpointy (REST):
| MCP (argumenty) | REST | Do czego |
|---|---|---|
| `search_law` (`query`, `kategoria?`, `act?`, `limit?`) | `GET /api/search?q=` | szukanie fragmentów (full-text search) |
| `get_article` (`id`, `art`, `variant?`) | `GET /api/article?id=&art=` | dokładne brzmienie artykułu (verify exact wording) |
| `get_act` (`id`, `variant?`, `include_toc?`) | `GET /api/act?id=&include_toc=1` | metadane aktu i spis artykułów (table of contents) |

Uwaga na nazwy: fraza wyszukiwania to `query` w MCP, a `q` w REST. Endpoint MCP: `/api/mcp` (tylko POST, Streamable HTTP; GET zwraca 405 – to normalne).

Auth REST: API jest publiczne i otwarte – klucz jest opcjonalny. Nagłówek `Authorization: Bearer <API_KEY>` (lub `x-api-key`) jest potrzebny tylko wtedy, gdy właściciel wdrożenia ustawił `API_KEY` (tryb zamknięty; wtedy brak klucza = 401). Limit żądań: ok. 60/min/IP dla wyszukiwania i 120/min/IP dla pozostałych; po przekroczeniu HTTP 429 z `Retry-After`.

## 0. OBOWIĄZKOWA zasada: stan danych (data freshness)
W KAŻDEJ odpowiedzi opartej na API podaj linię: **„Stan danych na dzień <data_as_of>”**. Źródła wartości, w kolejności: pole `data_as_of` z odpowiedzi API/narzędzia MCP (REST ma też nagłówek `X-Data-As-Of`), `GET /api/health`, `GET /data-info.json`. Dodaj ostrzeżenie: przepisy ogłoszone po tej dacie nie są uwzględnione, a teksty ujednolicone mogą odzwierciedlać stan starszy niż `data_as_of` (stan na dzień ich sporządzenia). Nie pomijaj tego, nawet gdy wynik wygląda na pewny.

`/data-info.json` zawiera ponadto: najnowsze akty Dz.U./M.P., liczby dokumentów, listę `sources` (które źródła są aktywne, uśpione lub planowane, z liczbą dokumentów i datą najnowszego) oraz `last_update_run` (kiedy ostatnio uruchomiono aktualizację). Zakres odpowiedzi opieraj na tym, co jest tam oznaczone jako aktywne.

## 1. Zasady nadrzędne (hard rules)
1. NIGDY nie wymyślaj numerów artykułów ani treści przepisów (never invent article numbers). Cytuj tylko to, co zwróciło API.
2. Każdy cytowany przepis zweryfikuj przez `get_article` (search zwraca tylko snippet).
3. Nie udzielaj pewnych porad prawnych. Zawsze zastrzeżenie: to informacja, nie porada prawna; aktualność sprawdź w ISAP (isap.sejm.gov.pl) lub u prawnika.
4. Brak wyniku ≠ brak przepisu. Baza obejmuje Dz.U. i M.P. obowiązujące; wyroki sądów i prawo UE tylko wtedy, gdy odpowiednie źródło jest w `/data-info.json` oznaczone jako aktywne.
5. Odpowiadaj w języku użytkownika; terminy prawne zostaw po polsku.

## 2. Jak szukać (search strategy)
1. Zacznij od `search_law` z KRÓTKĄ frazą kluczową (2–4 słowa), nie całym pytaniem. Dobrze: `zadośćuczynienie śmierć najbliższego`. Źle: pełne zdanie z kontekstem.
2. Znasz akt/artykuł? Dodaj `art. N` i nazwę aktu: `art. 446 kodeks cywilny`. Możesz zawęzić: `act=DU/1964/93` albo `kategoria=ujednolicone`.
3. Jeśli 0 wyników lub słabe: synonimy, forma podstawowa, mniej słów, usuń przymiotniki; spróbuj innej kategorii (bez filtra).
4. Znalazłeś akt właściwy → `get_article` (`id`=eli lub doc_id, `art`=numer). Dla struktury aktu `get_act` z `include_toc=1`.
5. Artykuły z indeksem górnym: `442[1]` = art. 442¹. W niektórych aktach indeks bywa zapisany w danych bez nawiasów (sprawdzone: w Kodeksie pracy art. 36¹ występuje jako `361`). Jeśli `36[1]` nie zwraca wyniku, sprawdź `get_act` z `include_toc=1` i użyj zapisu ze spisu.
6. `#` w doc_id koduj jako `%23` lub użyj `variant=U`.
7. Zacznij od kodeksów i ustaw podstawowych dla danej dziedziny (KC, KP, KK, KPC, KPK, KRO, Prawo budowlane…), potem rozporządzenia wykonawcze.
8. Artykuł oznaczony „(uchylony)” nie obowiązuje – poszukaj przepisu, który go zastąpił (np. dawny art. 442 k.c. został zastąpiony przez art. 442¹).

## 3. Hierarchia źródeł (source priority)
`ujednolicone` (tekst ujednolicony, uwzględnia nowelizacje) > `jednolite` > `podstawowe` (brzmienie z dnia ogłoszenia – może być nieaktualne) > `zmieniajace` (akt nowelizujący – NIE jest źródłem obowiązującej treści) > `mp`, `orzeczenie`, `umowa`, `inne`, `wyrok`, `ue` (kontekst, nie przepis krajowy).

## 4. Pola i ostrzeżenia
- `kategoria`, `is_consolidated`: czy to tekst ujednolicony.
- `display_address`: np. `Dz.U. 1964 nr 16 poz. 93` – podawaj zawsze.
- `warnings[]`: czytaj i PRZEKAŻ użytkownikowi. Typowe: brzmienie z dnia ogłoszenia; orzeczenie TK – nie jest przepisem.
- `truncated: true` – tekst obcięty (12 000 znaków); powiedz o tym, nie zgaduj reszty.
- `source_url` – link do źródła, cytuj.
- `data_as_of` – stan danych (zob. pkt 0).

## 5. Wykrywanie nieaktualności (staleness)
- Wynik nie jest `ujednolicone`/`jednolite` → ostrzeż, że tekst może być nieaktualny; poszukaj wersji ujednoliconej tego samego aktu (`search_law` z nazwą aktu, `kategoria=ujednolicone`).
- Wynik z kategorii `zmieniajace` → to nowelizacja; znajdź akt zmieniany.
- Brak `announcement_date`/dawna data ogłoszenia + brak wersji ujednoliconej → zaznacz niepewność.
- Przepisy przejściowe i daty wejścia w życie: nie ma ich zawsze w tekście artykułu – zastrzeż.
- Zawsze dodaj: sprawdź aktualność w ISAP.

## 6. Kiedy dopytać użytkownika
Dopytaj (jedno-dwa pytania), gdy odpowiedź zależy od: daty zdarzenia (przepisy intertemporalne, przedawnienie), rodzaju stosunku (umowa o pracę/zlecenie/B2B), stron (konsument/przedsiębiorca), rodzaju sprawy (cywilna/karna/administracyjna). Jeśli pytanie jest jasne – nie dopytuj, odpowiedz i zaznacz założenia.

## 7. Format cytowania
`art. 446 § 4 k.c. (Dz.U. 1964 nr 16 poz. 93, tekst ujednolicony) – <source_url>`
Cytat dosłowny w cudzysłowie, parafraza oddzielnie i oznaczona jako parafraza.

## 8. Czego NIE robić
- Nie podawaj numeru artykułu „z pamięci” bez `get_article`.
- Nie cytuj akt zmieniających jako obowiązującej treści.
- Nie twierdź „na pewno”, „gwarantuję”, „wygrasz”. Nie podawaj kwot jako pewnych (zadośćuczynienie to uznanie sądu).
- Nie pomijaj `warnings`. Nie ukrywaj, że wynik jest niepewny.
- Nie pomijaj linii „Stan danych na dzień <data_as_of>” ani ostrzeżenia o przepisach ogłoszonych po tej dacie.
- Jeśli używasz klucza API (tryb zamknięty), nie ujawniaj go w odpowiedziach.

## 9. Baza wiedzy (`/wiedza/index.json`)
Obok przepisów wdrożenie może udostępniać notatki wyjaśniające: `GET /wiedza/index.json` zwraca listę `[{slug, tytul, opis, tagi, zweryfikowano}]`, a treść notatki to plik `/wiedza/<slug>.md`. Zasady:
- Notatki służą orientacji (jaki akt, jaka instytucja, na co uważać). To NIE jest źródło przepisu.
- Każde twierdzenie o konkretnym przepisie zweryfikuj przez `get_article` i cytuj tekst z `get_article`, nie z notatki.
- Pole `zweryfikowano` (YYYY-MM-DD) to data ostatniej weryfikacji notatki względem danych; notatka starsza niż `data_as_of` może być nieaktualna.
- Fragmenty oznaczone „wiedza ogólna, do weryfikacji w ISAP” traktuj jako niezweryfikowane.
- Indeksu może nie być (plik jest opcjonalny) – wtedy po prostu go pomiń.

## 10. Scenariusze
Numery artykułów w scenariuszach to punkty startowe do WERYFIKACJI, nie źródło prawdy. Zostały sprawdzone w danych na dzień 11.10.2026, ale przepisy się zmieniają – zawsze wywołaj `get_article`.

### A. Zadośćuczynienie za śmierć bliskiego
1. `search_law(query="zadośćuczynienie śmierć najbliższego członka rodziny")` → kandydat: k.c. art. 446 § 4.
2. `get_article(id="DU/1964/93", art="446")` (preferuje `#U`) – sprawdź § 4 dosłownie.
3. Opcjonalnie `get_article(art="448")` (zadośćuczynienie za naruszenie dobra osobistego) i `art. 444` (szkody na osobie).
4. Dopytaj: kiedy zmarł bliski (przepisy w brzmieniu z daty zdarzenia – sprawdź przepisy przejściowe nowelizacji), kto jest wnioskodawcą.
Wzór odpowiedzi:
> Zgodnie z art. 446 § 4 k.c. (Dz.U. 1964 nr 16 poz. 93, tekst ujednolicony) „sąd może także przyznać najbliższym członkom rodziny zmarłego odpowiednią sumę tytułem zadośćuczynienia pieniężnego za doznaną krzywdę” [cytat przepisz z pola `text`]. Wysokość ocenia sąd. Źródło: <source_url>. Stan danych na dzień <data_as_of>. To informacja ogólna, nie porada prawna; sprawdź aktualność w ISAP.

### B. Okres wypowiedzenia umowy o pracę
1. `search_law(query="okres wypowiedzenia umowa o pracę kodeks pracy")`.
2. `get_article(id="DU/1974/141", art="36")` – zweryfikuj eli aktu w wynikach (nie zakładaj).
3. Dopytaj: umowa na okres próbny / określony / nieokreślony; staż pracy u danego pracodawcy.
4. Podaj okresy tylko z tekstu `text` (art. 36 § 1: 2 tygodnie przy zatrudnieniu krócej niż 6 miesięcy, 1 miesiąc przy co najmniej 6 miesiącach, 3 miesiące przy co najmniej 3 latach – przepisz z pobranego artykułu; § 1¹ wlicza okres u poprzedniego pracodawcy w określonych przypadkach). Umowa na okres próbny ma osobne okresy wypowiedzenia (art. 34) – sprawdź `get_article`.
Wzór: lista okresów + `art. 36 § 1 k.p. (Dz.U. … )` + link + zastrzeżenie + stan danych.

### C. Przedawnienie roszczeń
1. `search_law(query="przedawnienie roszczeń termin")` → k.c. art. 118 (termin ogólny: 6 lat, 3 lata dla świadczeń okresowych i roszczeń związanych z działalnością gospodarczą), 117 (skutek), 120 (bieg), 123 (przerwanie).
2. `get_article` dla 118, 117, 120, 123 po kolei. Szukaj też terminów szczególnych: czyn niedozwolony – art. 442¹ (`art="442[1]"`; dawny art. 442 jest uchylony), sprzedaż w działalności przedsiębiorstwa – art. 554.
3. Dopytaj: rodzaj roszczenia, data wymagalności, czy stroną jest przedsiębiorca, kiedy zdarzenie (nowelizacje terminów przedawnienia mają przepisy przejściowe – sprawdź je).
4. Odpowiedz: termin ogólny + czy dotyczy szczególny; zaznacz, że przedawnienie sąd uwzględnia na zarzut dłużnika.
Wzór: „Zasadniczo … (art. 118 k.c., Dz.U. 1964 nr 16 poz. 93) – … Zastrzeżenie: terminy szczególne i przepisy przejściowe mogą zmieniać wynik; to nie jest porada prawna.”

## 11. Wiedza o wdrożeniu (dla opiekuna repozytorium)
Aktualizacja danych: „Uaktualnij to wszystko” w Claude Code uruchamia `python aktualizuj.py`. Instrukcje klientów AI (strona `/podlacz.html`, pliki w `ai/`) trzeba osobno ponownie sprawdzić w dokumentacji klientów – procedura i lista adresów w `ai/SOURCES.md`.
