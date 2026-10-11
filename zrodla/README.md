# zrodla/ – rejestr źródeł danych i uśpione fetchery

Tu jest wszystko, co dotyczy **dodatkowych źródeł prawa** poza Dz.U. i M.P. (te obsługuje `pipeline/update_data.py`).
Dwa źródła są gotowe, ale **uśpione** (`enabled:false`): orzeczenia sądów z SAOS i prawo UE po polsku z EUR-Lex/Cellar.
Włącza się je jedną zmianą w `zrodla/sources.json`; od tej chwili polecenie „Uaktualnij to wszystko” (`python aktualizuj.py`) odświeża je razem z resztą.

Stan na 2026-10-11. Wszystko poniżej o zachowaniu serwisów pochodzi z żywych zapytań wykonanych tego dnia.

## Co jest w katalogu

| Plik | Rola |
|---|---|
| `sources.json` | rejestr źródeł: `id, nazwa, opis, enabled, kategoria, skrypt, wyjscie, zakres, licencja, status` (+ `opcje`, `stan`, `uwagi`) |
| `niedostepne.json` | źródła rozpoznane, których **nie da się** dodać (TK, SN, NSA/CBOSA, Portal Orzeczeń, RCL, dane.gov.pl) wraz z powodem i alternatywą |
| `_common.py` | wspólna biblioteka: HTTP z ponowieniami i limitem tempa, walidacja Content-Type, HTML na tekst, dzielenie na fragmenty, walidacja wiersza wg `docs/SPEC.md`, zapis atomowy, stan |
| `saos/fetch.py` | fetcher orzeczeń SAOS (przyrostowy) |
| `eurlex/fetch.py`, `eurlex/seed.json` | fetcher aktów UE po CELEX + lista 44 zweryfikowanych aktów |
| `laczenie_zmian.py` | skleja `stan/zmiany.json` i `stan/zmiany_<id>.json` w jeden plik dla `load_to_postgres.py --sync` |
| `tests/` | testy jednostkowe (mock, bez sieci) i `live_check.py` (żywy test) |

| id | status | kategoria | skrypt | wynik |
|---|---|---|---|---|
| `eli-du`, `eli-mp`, `isap-ujednolicone` | aktywne | wg `kategorie.py` | `pipeline/update_data.py` (wpis tylko informacyjny) | `pipeline/out/chunks.jsonl` |
| `saos` | uśpione | `wyrok` | `zrodla/saos/fetch.py` | `pipeline/out/chunks_saos.jsonl` |
| `eurlex` | uśpione | `ue` | `zrodla/eurlex/fetch.py` | `pipeline/out/chunks_eurlex.jsonl` |

## Jak włączyć źródło

1. **Sprawdź warunki.** Przeczytaj sekcję „Ograniczenia prawne” poniżej. Dla SAOS napisz najpierw do operatora (robots.txt zabrania `/api/`).
2. **Test na próbce** (nic nie rusza `stan/` ani `pipeline/out/`):
   ```powershell
   python zrodla\tests\live_check.py            # oba źródła, po kilka zapytań
   python zrodla\tests\live_check.py --eurlex   # tylko UE
   ```
3. **Włącz**: w `zrodla/sources.json` ustaw `"enabled": true` dla wybranego źródła (status możesz zmienić na `"aktywne"`).
4. **Pierwsze uruchomienie** (ręcznie, żeby zobaczyć wynik):
   ```powershell
   python zrodla\eurlex\fetch.py            # 44 akty, kilka minut
   python zrodla\saos\fetch.py              # domyślnie ostatnie 30 dni, SN/NSA/TK/KIO
   ```
5. **Załaduj do bazy** (`DATABASE_URL` w `.env.local` lub zmiennej środowiskowej):
   ```powershell
   # przyrost po aktualizacji: zmiany z jednego źródła
   python pipeline\load_to_postgres.py --sync stan\zmiany_eurlex.json --input pipeline\out\chunks.jsonl pipeline\out\chunks_eurlex.jsonl --max-mb 450
   # kilka źródeł naraz: najpierw sklej pliki zmian
   python zrodla\laczenie_zmian.py --out stan\zmiany_razem.json stan\zmiany.json stan\zmiany_saos.json stan\zmiany_eurlex.json
   python pipeline\load_to_postgres.py --sync stan\zmiany_razem.json --input pipeline\out\chunks.jsonl pipeline\out\chunks_saos.jsonl pipeline\out\chunks_eurlex.jsonl
   # pierwsze pełne ładowanie samego źródła (bez --sync)
   python pipeline\load_to_postgres.py --input pipeline\out\chunks_eurlex.jsonl --kategorie ue
   ```
   `--input` przyjmuje wiele plików; dokument występujący w kilku plikach jest brany z pierwszego. Przy `--max-mb` nowe dokumenty są dodawane tylko dopóki baza jest mniejsza niż limit.
6. **Po zmianie** uruchom `python pipeline\build_data_info.py` i wdróż stronę, żeby `data-info.json` pokazał nowe źródło.

Przez orkiestratora: krok `zrodla` w `aktualizuj.py` uruchamia `skrypt` każdego źródła z `enabled:true`; każdy fetcher zapisuje plik zmian `stan/zmiany_<id>.json` w formacie `stan/zmiany.json` (`added/changed/removed` jako `doc_id`).
Wyłączenie źródła = `"enabled": false` (dane w bazie zostają; usuwanie dokumentów robi się osobno, np. `delete from documents where kategoria = 'wyrok'`).

## Wspólne cechy fetcherów

- `python zrodla/<id>/fetch.py [--limit N] [--since YYYY-MM-DD] [--out PLIK] [--stan-dir DIR] [--dry-run] [--force]`
- **Uśpione = nic nie robi**: bez `enabled:true` w `sources.json` fetcher kończy się komunikatem (kod 0). `--force` omija to na potrzeby ręcznego testu; `--dry-run` pokazuje plan bez sieci i bez zapisu.
- **Przyrostowość**: stan w `stan/zrodlo_<id>.json` (`last_run`, `count`, `newest_date` + pola specyficzne). Zapis plików atomowy (plik tymczasowy, potem rename); przerwany przebieg jest dokańczany przy następnym uruchomieniu (`*.part`).
- **Grzeczność**: własny `User-Agent` (zmienna `PRAWO_USER_AGENT` go nadpisuje), min. odstęp między zapytaniami (`--delay`), brak równoległości, ponowienia z narastającym opóźnieniem, szanowanie `Retry-After`.
- **Walidacja**: każdy dokument jest sprawdzany względem schematu z `docs/SPEC.md` (pola, typy, `ord` 1..n, fragment ≤ 6000 znaków, `doc_id` jako pierwszy klucz – tego wymaga loader). U+FFFD są usuwane z tekstu i zliczane.
- **Kody wyjścia**: `0` ok; `1` błąd (np. część aktów się nie pobrała – reszta jest zapisana, błędy w `stan/zrodlo_<id>.json`, pole `errors`); `3` źródło niedostępne (np. SAOS zwraca HTTP 200 z HTML „Przerwa techniczna” zamiast JSON) – dane już zapisane zostają, następny przebieg wznawia.
- **Brak sekretów**: fetchery nie używają kluczy ani haseł.

## SAOS (`zrodla/saos/fetch.py`)

Źródło: `https://www.saos.org.pl/api/dump/judgments` (bez klucza, tylko GET). Pobiera strony po 100 z `withGenerated=false` i `sinceModificationDate`, idzie za `links[rel=next]`.

- **Co trafia do bazy**: `kategoria: wyrok`, `doc_id: SAOS/<id>`, `status: orzeczenie`, `publisher: SAOS`. Pierwszy fragment to metadane (rodzaj, sąd, wydział, sygnatura, data, powołane akty z odnośnikiem `DU/rok/poz`, podstawy prawne, słowa kluczowe, źródło), dalej treść w fragmentach ≤ 2000 znaków (`article: null`). `heading` = „sąd, sygn. …, data”. Nazwa sądu pochodzi ze słownika `/api/dump/commonCourts` i `/api/dump/scChambers` (cache w `stan/zrodlo_saos_sady.json`, odświeżany co 30 dni); gdy go brak – heurystyka z początku tekstu, a w ostateczności ogólna etykieta („Sąd powszechny”).
- **Dane osobowe**: sędziowie i strony nie są dopisywani do metadanych; sama treść jest anonimizowana przez sądy źródłowe (nie sprawdzamy jakości anonimizacji).
- **Filtr po rodzaju sądu** działa po stronie klienta (dump go nie ma): `opcje.typy_sadow` w `sources.json` albo `--typy SUPREME,ADMINISTRATIVE` / `--typy wszystkie`. Domyślnie bez sądów powszechnych (`COMMON`) – jest ich najwięcej i najtrudniej je pomieścić.
- **Okno czasu**: bez stanu i bez `--since` fetcher bierze ostatnie `okno_poczatkowe_dni` (30). Kolejne przebiegi startują od start-czasu ostatniego kompletnego przebiegu minus 2 dni zapasu. Pełny import historii: `--since 1990-01-01` (**bardzo długie**: strona 100 pozycji trwa od kilku do ~30 s – używaj `--max-stron`, przebieg można wznawiać).
- **Wznawianie**: gdy przebieg zatrzyma się (limit `--limit`, `--max-stron`, błąd, przerwa techniczna), stan zapisuje punkt wznowienia (`partial`); następne uruchomienie kontynuuje od tej strony. Watermark przesuwa się dopiero po przebiegu kompletnym.
- **Puste teksty**: w żywej próbce z 2026-10-11 prawie wszystkie niedawno zmodyfikowane wpisy miały pusty `textContent` (SAOS importuje metadane przed treścią; to samo zwraca `/api/judgments/{id}`). Takie wpisy nie są zapisywane, trafiają do kolejki ponowień (max 30 id na przebieg, każdy id najwyżej raz dziennie, do 6 prób, kolejka ≤ 2000) i wrócą też same, gdy SAOS uzupełni tekst (zmiana daty modyfikacji).
- **Limit rozmiaru**: orzeczenie dłuższe niż `max_znakow_orzeczenia` (150 000) jest obcinane z adnotacją i odnośnikiem do pełnego tekstu.
- **source_url**: adres oryginału u źródła, jeśli to strona czytelna dla człowieka; adresy backendu XML portalu orzeczeń (`ncourt-api`) są zastępowane stroną orzeczenia w SAOS (`https://www.saos.org.pl/judgments/<id>`), która linkuje do oryginału. Adres oryginału jest też w pierwszym fragmencie.

## EUR-Lex / Cellar (`zrodla/eurlex/fetch.py`)

Źródło: `http://publications.europa.eu/resource/celex/<CELEX>` z nagłówkami `Accept` i `Accept-Language: pl` (bez klucza). Strona `eur-lex.europa.eu` jest za AWS WAF i **nie jest używana do pobierania** (służy tylko jako `source_url` dla człowieka).

- **Formaty**: kolejno xhtml → html → pdf (starsze akty nie mają xhtml; 404 „no content datastream” znaczy brak formatu, nie brak aktu). PDF wymaga `pymupdf` lub `pypdf`.
- **Podział**: „Artykuł N” → jeden fragment (`article = "N"`, `heading` = „CZĘŚĆ/TYTUŁ/ROZDZIAŁ/SEKCJA …”); artykuł dłuższy niż 5500 znaków jest dzielony na kawałki z nagłówkiem „Artykuł N (ciąg dalszy)”. Preambuła i załączniki to fragmenty ~2000 znaków (`article: null`, `heading` „Preambuła” / „ZAŁĄCZNIK …”). Akt bez artykułów – same fragmenty. Pierwszy fragment („Informacje o akcie”) zawiera pełny tytuł, nazwę skróconą (np. RODO) i zastrzeżenie o brzmieniu z dnia publikacji. Przypisy dolne są usuwane.
- **Metadane**: `doc_id = eli = CELEX/<celex>`, `display_address` = „Dz.Urz. UE L 119 z 4.5.2016, s. 1 (CELEX 32016R0679)”, `announcement_date` = data aktu z tytułu, `is_consolidated` = prawda tylko dla CELEX zaczynających się od `0` (wersje ujednolicone). Teksty `3…` to oryginał z Dz.Urz. UE, **nie tekst ujednolicony**.
- **Lista aktów**: `seed.json` (44 akty zweryfikowane żywym zapytaniem 2026-10-11: ochrona danych, prawa konsumentów, prawo prywatne międzynarodowe, DSA/DMA/Data Act/AI Act/eIDAS, spółki i finanse, dwa pojedyncze artykuły TFUE). Dodatkowe: dopisz do `seed.json` albo `--celex 32024R1689 …` (`--tylko-celex` pomija seed).
- **Odświeżanie**: akt już pobrany jest pomijany przez 90 dni (oryginały z Dz.Urz. praktycznie się nie zmieniają); `--odswiez` wymusza pobranie, a zmiana treści (sha256) daje wpis `changed`.
- **Nowości**: `python zrodla/eurlex/fetch.py --odkryj --since 2026-09-01` wypisuje nowe rozporządzenia i dyrektywy z SPARQL (zapis do `stan/zrodlo_eurlex_kandydaci.json`) – bez pobierania; wybrane akty dodajesz sam.
- **Wersje ujednolicone**: obsługiwane przez numer CELEX w formie `0RRRR<R|L>NNNN-RRRRMMDD` (sprawdzone tylko dla RODO `02016R0679-20160504`; daty kolejnych wersji trzeba znaleźć w metadanych). Nie ma ich w `seed.json`.
- **Traktaty**: tylko pojedyncze artykuły (`12012E101`, `12012E267`); całego TFUE/TUE nie potwierdzono.

## Testy

```powershell
python -m unittest discover -s zrodla\tests -v     # 66 testów, bez sieci
python zrodla\tests\live_check.py                   # żywy: EUR-Lex 5 aktów + SAOS ~3 strony, zapis do katalogu tymczasowego
```

Wyniki z 2026-10-11: testy jednostkowe 66/66; test żywy – EUR-Lex 5 aktów (RODO, dyrektywa 2016/680, e-Privacy, rozporządzenie 2018/1725, dyrektywa o prawach konsumentów; 622 fragmenty, 918 KB) oraz SAOS 5 orzeczeń (227 fragmentów, 380 KB): wszystkie wiersze zgodne ze schematem, 0 znaków U+FFFD, polskie znaki poprawne na poziomie kodów Unicode, `load_to_postgres.py --dry-run` akceptuje oba pliki. Dodatkowo ręcznie: 12012E101, 12012E267, 32001R0044, 32004R0805. **Nie zostało przetestowane**: pełne pobranie 44 aktów (w tym CRR ~6,6 MB), ładowanie do żywej bazy, PDF jako format zapasowy (żaden z testowanych aktów go nie potrzebował), wersje ujednolicone poza analizą kodu, zachowanie SAOS przy tysiącach stron i przy odświeżaniu pustych wpisów po dniach.

## Szacunki rozmiaru (to SZACUNKI, nie pomiary całości)

Reguła z `docs/DEPLOY.md`: baza po załadowaniu ≈ 2,3–2,5 × rozmiar czystego tekstu (przy `--overhead 2.5`).

| Źródło | Podstawa | Szacunek |
|---|---|---|
| `eurlex` (44 akty) | próbka 5 aktów: średnio ~184 KB tekstu na akt (RODO 357 KB, dyrektywa konsumencka 111 KB, e-Privacy 57 KB). CRR i AI Act są większe od średniej, ich nie mierzono | tekst rzędu 8–15 MB, **w bazie rzędu 20–40 MB** |
| `saos`, SN + sądy administracyjne + TK + KIO | liczby orzeczeń tych typów w SAOS **nie sprawdzono**. Próbka 5 orzeczeń sądów powszechnych: średnio ~76 KB tekstu (mała, niereprezentatywna próbka) | wzór: liczba orzeczeń × średnia długość × 2,5. Przykład ilustracyjny przy założeniu 20 KB/orzeczenie (założenie, nie pomiar): 10 000 orzeczeń ≈ 0,5 GB w bazie |
| `saos`, sądy powszechne | Portal Orzeczeń podaje 459 260 dokumentów (2026-10-11) | przy tym samym założeniu 20 KB/orzeczenie: rzędu **dziesiątek GB** – poza zasięgiem planów Neon rozsądnych dla tego projektu |

Zmierz własną średnią: po `live_check.py` (lub `fetch.py --limit 100 --out próbka.jsonl`) statystyka „średnio … KB/dok.” pozwala policzyć wzór dla swoich typów sądów.

## Rekomendacje (Neon)

- Darmowy plan Neon (~0,5 GB) jest już praktycznie zajęty przez teksty ujednolicone (`DEPLOY.md`: `--max-mb 450`). `load_to_postgres.py` dodaje nowe dokumenty tylko dopóki baza jest poniżej `--max-mb`, więc dokumenty `ue` i `wyrok` doładowane na pełną bazę zostaną **pominięte** (komunikat o limicie).
- **`eurlex` – najlepszy kandydat** (mało danych, duża wartość: RODO, prawa konsumenta, Rzym I/II, Bruksela). Na darmowym planie zmieści się, jeśli zrobisz mu miejsce: załaduj go przed resztą albo zmniejsz `--max-mb` dla pozostałych kategorii o kilkadziesiąt MB.
- **`saos` – nie mieści się w darmowym planie.** Wymaga płatnego planu i świadomego wyboru zakresu: najpierw `SUPREME` + `CONSTITUTIONAL_TRIBUNAL` (+ `ADMINISTRATIVE`), po zmierzeniu próbki. Sądów powszechnych (`COMMON`) nie włączaj bez planu na rozmiar.
- Orzeczenia w domyślnym wyszukiwaniu mogą zdominować wyniki przepisów (przy dziesiątkach tysięcy dokumentów). `vercel/lib/law.ts` ma `DEFAULT_EXCLUDED = ['orzeczenie','umowa','inne']` – rozważ dopisanie `'wyrok'` (właściciel pliku: część Vercel). Wtedy wyroki zwraca się tylko przy `kategoria=wyrok`.
- Ostrzeżenia dla modeli: `vercel/lib/warnings.ts` dopisuje do `wyrok` i `ue` ostrzeżenia (nie jest przepisem; anonimizacja i prawomocność; oryginał z Dz.Urz. vs wersja ujednolicona) i nie traktuje statusów „orzeczenie”/„tekst z Dz.Urz. UE” jako nieobowiązywania.

## Ograniczenia prawne i techniczne

- **SAOS**: `robots.txt` ma `Disallow: /api/`, a dokumentacja SAOS jednocześnie zachęca do pobierania przez API i nie podaje ani limitów, ani licencji. Przed włączeniem napisz do operatora SAOS (adres kontaktowy jest na stronie głównej serwisu, w postaci z zamaskowanymi znakami) i uzyskaj potwierdzenie. Do tego czasu zostaw `enabled:false`. Fetcher przy starcie nie blokuje się na robots.txt – decyzja należy do Ciebie.
- **EUR-Lex**: ponowne wykorzystanie na podstawie decyzji Komisji 2011/833/UE (wg źródeł wtórnych zasadniczo CC BY 4.0 z podaniem źródła); treść strony „legal notice” nie została odczytana, więc licencja jest zapisana jako „częściowo potwierdzona”. `robots.txt` publications.europa.eu nie obejmuje ścieżek `/resource/celex` ani `/webapi/rdf/sparql`.
- **Akty ISAP/ELI**: urzędowe teksty aktów prawnych są wyłączone spod prawa autorskiego (art. 4 pkt 2 – wiedza ogólna, do weryfikacji); regulaminu API Sejmu nie odczytano.
- **Orzeczenia** zawierają dane osobowe zanonimizowane przez sądy źródłowe; model ma podawać sąd i sygnaturę, a nie wskazywać osób prywatnych (ostrzeżenie `wyrok`). Orzeczenie nie jest przepisem, może nie być prawomocne ani aktualne.
- Zawsze podawaj datę stanu danych (`data_as_of`, zasada repozytorium).

## Źródła, których nie da się dodać (szczegóły: `niedostepne.json`)

| Źródło | Dlaczego nie | Alternatywa |
|---|---|---|
| Trybunał Konstytucyjny (trybunal.gov.pl) | brak API; RSS pusty w dniu rozpoznania | orzeczenia TK przez SAOS (`CONSTITUTIONAL_TRIBUNAL`) |
| Sąd Najwyższy (sn.pl) | ochrona anty-botowa (Incapsula), brak API; nie obchodzić | SAOS (`SUPREME`) |
| NSA/WSA – CBOSA (orzeczenia.nsa.gov.pl) | `robots.txt` zabrania wyszukiwarki i pobierania dokumentów; GPTBot zablokowany | SAOS (`ADMINISTRATIVE`) – obecność w dumpie niepotwierdzona |
| Portal Orzeczeń Sądów Powszechnych | brak oficjalnego API, nieudokumentowany backend XML, WAF | SAOS (`COMMON`) |
| RCL (legislacja.gov.pl) | `robots.txt`: `Disallow: /` | API Sejmu (druki, procesy) – nietestowane |
| dane.gov.pl | głównie statystyki, nie teksty orzeczeń | – |

## Jak dodać nowe źródło

1. Utwórz `zrodla/<id>/fetch.py`, importując `_common` (`sys.path.insert(0, str(Path(__file__).resolve().parents[1]))`). Użyj `base_parser`, `check_enabled`, `http_get`, `RateLimiter`, `make_row`, `validate_rows`, `PartWriter`, `load_state/save_state`, `write_changes`.
2. Dodaj wpis do `sources.json` (`enabled:false`, `status:"uśpione"`), testy do `zrodla/tests/`, a w README opisz zakres i licencję.
3. Wynik musi spełniać `docs/SPEC.md`; kategorię (`wyrok`/`ue`/inną z listy) i ostrzeżenia dla modeli ustawia się w `vercel/lib/warnings.ts`.
