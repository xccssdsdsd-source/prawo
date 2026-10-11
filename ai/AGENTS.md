# AGENTS.md – jak korzystać z API prawa polskiego (Dz.U. + M.P.)

Instrukcja dla każdego agenta/modelu AI (Claude, GPT, Gemini, Llama…). English hints in parentheses.

Narzędzia (MCP) / endpointy (REST):
| MCP | REST | Do czego |
|---|---|---|
| `search_law` | `GET /api/search?q=` | szukanie fragmentów (full-text search) |
| `get_article` | `GET /api/article?id=&art=` | dokładne brzmienie artykułu (verify exact wording) |
| `get_act` | `GET /api/act?id=&include_toc=1` | metadane aktu i spis artykułów (table of contents) |

Auth REST: API jest publiczne i otwarte – klucz jest opcjonalny. Nagłówek `Authorization: Bearer <API_KEY>` (lub `x-api-key`) jest potrzebny tylko wtedy, gdy właściciel wdrożenia ustawił `API_KEY` (tryb zamknięty; wtedy brak klucza = 401).

## 0. OBOWIĄZKOWA zasada: stan danych (data freshness)
W KAŻDEJ odpowiedzi opartej na API podaj linię: **„Stan danych na dzień <data_as_of>”** (pole `data_as_of` z odpowiedzi API, a gdy go brak – z `/api/health` lub `/data-info.json`). Dodaj ostrzeżenie: przepisy ogłoszone po tej dacie nie są uwzględnione, a teksty ujednolicone mogą odzwierciedlać stan starszy niż `data_as_of` (stan na dzień ich sporządzenia). Nie pomijaj tego, nawet gdy wynik wygląda na pewny.

## 1. Zasady nadrzędne (hard rules)
1. NIGDY nie wymyślaj numerów artykułów ani treści przepisów (never invent article numbers). Cytuj tylko to, co zwróciło API.
2. Każdy cytowany przepis zweryfikuj przez `get_article` (search zwraca tylko snippet).
3. Nie udzielaj pewnych porad prawnych. Zawsze zastrzeżenie: to informacja, nie porada prawna; aktualność sprawdź w ISAP (isap.sejm.gov.pl) lub u prawnika.
4. Brak wyniku ≠ brak przepisu. Baza obejmuje Dz.U. i M.P. obowiązujące (+ ewentualnie wyroki/UE, jeśli załadowane).
5. Odpowiadaj w języku użytkownika; terminy prawne zostaw po polsku.

## 2. Jak szukać (search strategy)
1. Zacznij od `search_law` z KRÓTKĄ frazą kluczową (2–4 słowa), nie całym pytaniem. Dobrze: `zadośćuczynienie śmierć najbliższego`. Źle: pełne zdanie z kontekstem.
2. Znasz akt/artykuł? Dodaj `art. N` i nazwę aktu: `art. 446 kodeks cywilny`. Możesz zawęzić: `act=DU/1964/93` albo `kategoria=ujednolicone`.
3. Jeśli 0 wyników lub słabe: synonimy, forma podstawowa, mniej słów, usuń przymiotniki; spróbuj innej kategorii (bez filtra).
4. Znalazłeś akt właściwy → `get_article` (`id`=eli lub doc_id, `art`=numer). Dla struktury aktu `get_act` z `include_toc=1`.
5. Artykuły z indeksem: `46[1]` = art. 46¹. `#` w doc_id koduj jako `%23` lub użyj `variant=U`.
6. Zacznij od kodeksów i ustaw podstawowych dla danej dziedziny (KC, KP, KK, KPC, KPK, KRO, Prawo budowlane…), potem rozporządzenia wykonawcze.

## 3. Hierarchia źródeł (source priority)
`ujednolicone` (tekst ujednolicony, uwzględnia nowelizacje) > `jednolite` > `podstawowe` (brzmienie z dnia ogłoszenia – może być nieaktualne) > `zmieniajace` (akt nowelizujący – NIE jest źródłem obowiązującej treści) > `mp`, `orzeczenie`, `umowa`, `inne`, `wyrok`, `ue` (kontekst, nie przepis krajowy).

## 4. Pola i ostrzeżenia
- `kategoria`, `is_consolidated`: czy to tekst ujednolicony.
- `display_address`: np. `Dz.U. 1964 nr 16 poz. 93` – podawaj zawsze.
- `warnings[]`: czytaj i PRZEKAŻ użytkownikowi. Typowe: brzmienie z dnia ogłoszenia; orzeczenie TK – nie jest przepisem.
- `truncated: true` – tekst obcięty (12 000 znaków); powiedz o tym, nie zgaduj reszty.
- `source_url` – link do źródła, cytuj.

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

## 9. Scenariusze

### A. Zadośćuczynienie za śmierć bliskiego
1. `search_law("zadośćuczynienie śmierć najbliższego członka rodziny")` → kandydaci: k.c. art. 446 § 4.
2. `get_article(id="DU/1964/93", art="446")` (preferuje `#U`) – sprawdź § 4 dosłownie.
3. Opcjonalnie `get_article(art="448")` (zadośćuczynienie za naruszenie dóbr osobistych) i `art. 444`/`446` (inne roszczenia).
4. Dopytaj: kiedy zmarł bliski (przepisy w brzmieniu z daty zdarzenia – art. 446 § 4 obowiązuje od 3.08.2008), kto jest wnioskodawcą.
Wzór odpowiedzi:
> Zgodnie z art. 446 § 4 k.c. (Dz.U. 1964 nr 16 poz. 93, tekst ujednolicony) „sąd może przyznać najbliższym członkom rodziny zmarłego odpowiednią sumę tytułem zadośćuczynienia pieniężnego za doznaną krzywdę” [cytat zweryfikuj z `text`]. Wysokość ocenia sąd. Źródło: <source_url>. To informacja ogólna, nie porada prawna; sprawdź aktualność w ISAP.

### B. Okres wypowiedzenia umowy o pracę
1. `search_law("okres wypowiedzenia umowa o pracę kodeks pracy")`.
2. `get_article(id="DU/1974/141", art="36")` – zweryfikuj eli aktu w wynikach (nie zakładaj).
3. Dopytaj: umowa na okres próbny / określony / nieokreślony; staż pracy u pracodawcy.
4. Podaj okresy tylko z tekstu `text` (np. 2 tygodnie / 1 miesiąc / 3 miesiące zależnie od stażu – potwierdź w pobranym artykule), wspomnij `art. 36¹` (`get_article art="36[1]"`) przy zatrudnieniu u kilku pracodawców/ staż.
Wzór: lista okresów + `art. 36 § 1 k.p. (Dz.U. … )` + link + zastrzeżenie.

### C. Przedawnienie roszczeń
1. `search_law("przedawnienie roszczeń termin")` → k.c. art. 118 (ogólny), 117 (skutek), 123–124 (przerwanie), 120 (bieg).
2. `get_article` dla 118, 117, 120, 123 po kolei. Szukaj też terminów szczególnych (np. `search_law("przedawnienie roszczenia z tytułu czynu niedozwolonego art. 442")`, `art. 554` sprzedaż).
3. Dopytaj: rodzaj roszczenia, data wymagalności, czy stroną jest przedsiębiorca, kiedy zdarzenie (nowelizacja z 2018 r. zmieniła terminy – przepisy przejściowe!).
4. Odpowiedz: termin ogólny + czy dotyczy szczególny; zaznacz, że przedawnienie sąd uwzględnia na zarzut dłużnika.
Wzór: „Zasadniczo … (art. 118 k.c., Dz.U. 1964 nr 16 poz. 93) – … Zastrzeżenie: terminy szczególne i przepisy przejściowe mogą zmieniać wynik; to nie jest porada prawna.”

Uwaga: numery artykułów w scenariuszach to punkty startowe do WERYFIKACJI, nie źródło prawdy.
