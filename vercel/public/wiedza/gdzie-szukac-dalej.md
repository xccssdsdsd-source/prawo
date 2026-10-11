# Gdzie szukać dalej: oficjalne portale i źródła polskiego prawa

> **Data weryfikacji: 2026-10-11** (adresy i opisy sprawdzono online tego dnia; strony i API zmieniają się bez uprzedzenia). Stan danych: baza Prawo API z dnia 11.10.2026.
> **To nie jest porada prawna** – to informacja ogólna. Aktualność przepisów zawsze sprawdź w ISAP (https://isap.sejm.gov.pl) lub u prawnika.
> Każdy wpis ma ocenę pewności: **sprawdzone** (odczytane z żywej dokumentacji lub odpowiedzi serwera), **częściowo** (adres działa, ale część opisu pochodzi z wyników wyszukiwania lub nie udało się odczytać treści), **z pamięci** (niezweryfikowane – sprawdź ręcznie przed poleceniem użytkownikowi). Odnośniki w formie `[doc_id art. N]` zweryfikowano z tekstem w bazie.

## W skrócie

Do **treści ustaw i rozporządzeń** używaj ISAP / Dziennika Ustaw / Monitora Polskiego, a do **dostępu programistycznego** – API ELI Sejmu (https://api.sejm.gov.pl/eli), bo ISAP odrzuca zapytania botów. Do **orzecznictwa** – bazy poszczególnych sądów (część jest niedostępna dla skryptów). Do **prawa UE** – EUR-Lex. Nasza baza obejmuje wyłącznie Dz.U. i M.P. (obowiązujące + teksty ujednolicone ISAP); reszta jest poza zakresem.

## 1. Akty prawne (Dz.U., M.P., teksty ujednolicone)

| Portal | Adres | Co zawiera / jak używać | Dostęp maszynowy | Pewność |
|---|---|---|---|---|
| **ISAP** (Kancelaria Sejmu) | https://isap.sejm.gov.pl | Opisy i teksty aktów ogłoszonych w Dz.U. i M.P. od 1918 r., także nieobowiązujących; dla ustaw bywają trzy pliki: tekst ogłoszony, tekst jednolity (obwieszczenie) i tekst ujednolicony. Wyszukiwanie po tytule, słowach kluczowych lub adresie publikacyjnym. | Brak udokumentowanego API; serwer odrzuca curl (HTTP 403, ochrona antybotowa) – używaj API ELI | sprawdzone (adres), częściowo (opis pomocy ISAP) |
| **API ELI Sejmu** | https://api.sejm.gov.pl/eli (Swagger: https://api.sejm.gov.pl/eli/openapi/ui/) | Wydawcy DU i MP; metadane, status, teksty (HTML/PDF), struktura, odesłania; tekst jednolity i ujednolicony jako osobne pliki. Bez klucza w zaobserwowanych wywołaniach. | Tak (JSON) | sprawdzone |
| **Dziennik Ustaw** | https://dziennikustaw.gov.pl/DU | Elektroniczne wydanie Dz.U. (wyłącznie elektronicznie od 1 stycznia 2012 r.), wybór roku i pozycji, wyszukiwarka. | Do automatu użyj ELI | sprawdzone |
| **Monitor Polski** | https://monitorpolski.gov.pl/MP | Elektroniczny M.P., archiwum 1921–2026 (brak lat 1940–1945). | Do automatu użyj ELI | sprawdzone |
| **Rządowe Centrum Legislacji** | https://rcl.gov.pl | Linki do Dz.U. i M.P., wykaz aktów oczekujących na ogłoszenie (podpisane, a jeszcze nieogłoszone), opisy procesu legislacyjnego, zasady techniki prawodawczej. | Brak opisu API | sprawdzone |
| **Rządowy Proces Legislacyjny** | https://legislacja.gov.pl | Projekty ustaw i rozporządzeń, status (w toku / przyjęte / archiwalne), konsultacje, OSR. Treść konkretnego projektu może wymagać konta. | Brak API; `robots.txt` zabrania botom (wg `zrodla/niedostepne.json`) – nie scrapuj | sprawdzone |
| **Sejm – druki i procesy** | https://www.sejm.gov.pl; API: https://api.sejm.gov.pl/sejm/openapi | Druki sejmowe, procesy legislacyjne, głosowania; do śledzenia projektów ustaw w toku (10. kadencja). Strona jest za ochroną antybotową. | Tak (API Sejmu: /sejm/term10/prints, /processes, /votings) | częściowo |

Ważne fakty, które potwierdzają nasze dane i ustawy:

- Dziennik Ustaw i Monitor Polski są dostępne nieodpłatnie do wglądu i pobrania na stronach internetowych Rządowego Centrum Legislacji [DU/2000/718#U art. 28b]; wydaje je Prezes Rady Ministrów przy pomocy RCL [DU/2000/718#U art. 21].
- Dniem ogłoszenia jest dzień udostępnienia aktu w postaci elektronicznej na stronie wydawcy [DU/2000/718#U art. 20].
- W Dz.U. i M.P. ogłasza się różne rodzaje aktów – patrz `hierarchia-zrodel-prawa`, pkt 10 [DU/2000/718#U art. 9, 10].
- **Adres rekordu w ISAP** ma postać `https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU<rok><nr 3 cyfry><poz 4 cyfry>`, gdzie część po `WDU` to pole `address` z ELI: np. `WDU19640160093` dla Dz.U. 1964 nr 16 poz. 93, a dla aktów od 2012 r. numer wynosi `000` (np. `WDU20260000184` dla Dz.U. 2026 poz. 184). Wzór zgadza się z polami `address` w naszych indeksach (zob. `dane/indeks_ujednolicone.json`). ISAP przy otwarciu wymaga ciasteczek (kilka przekierowań 302), więc skrypty tej strony nie otworzą.

### Jak używać API ELI (dla programistów i agentów)

- Lista wydawców: `GET https://api.sejm.gov.pl/eli/acts`; akty roku: `GET /eli/acts/DU/2026`; szczegóły: `GET /eli/acts/DU/2026/1307` (albo po adresie `/acts/WDU20260001307`).
- Tekst: `/text.html`, `/text.pdf`; struktura: `/struct`; odesłania i powiązania (np. tekst jednolity dla aktu, nowelizacje po tekście jednolitym): `/references`.
- Wyszukiwanie: `GET /acts/search?title=…&publisher=DU&year=…&inForce=1&limit=500&offset=0`.
- **Aktualizacja bazy:** `GET /eli/changes/acts?since=2026-10-01T00:00:00&limit=500` (parametr `since` jest wymagany, `limit` maks. 500) – dokładnie to, czego potrzeba do polecenia „Uaktualnij to wszystko”. Pliki tekstów jednolitych mają typ `T`, ujednoliconych `U` (zob. `teksty-jednolite-ujednolicone-zmieniajace`).
- Niektóre akty mają tylko PDF (`textHTML=false`). Stan bazy ELI bywa nowszy niż stan naszej bazy – podczas weryfikacji online 2026-10-11 ELI pokazywało m.in. Dz.U. 2026 poz. 1317 (9.10.2026) i M.P. 2026 poz. 990 (9.10.2026), podczas gdy nasza baza (patrz `/data-info.json`) miała stan do Dz.U. 2026 poz. 1307 i M.P. 2026 poz. 977. Po aktualizacji liczby się zmienią.

## 2. Orzecznictwo krajowe

| Portal | Adres | Co zawiera | Dostęp maszynowy / uwagi | Pewność |
|---|---|---|---|---|
| **Trybunał Konstytucyjny** | https://trybunal.gov.pl/orzeczenia/ | Orzeczenia TK, wokanda, RSS; wyszukiwarka pełnotekstowa w IPO: https://ipo.trybunal.gov.pl/ipo/. Sygnatury: K, SK, P itd. | Brak API; IPO i OTK ZU nie odpowiedziały w teście (timeout) | częściowo |
| **Sąd Najwyższy** | https://www.sn.pl | Orzecznictwo w zakładce „Orzecznictwo” – wyszukiwanie po sygnaturze (np. III CZP 61/05). | Serwis chroniony antybotowo (pętla przekierowań); niedostępny dla skryptów | z pamięci |
| **Sądy administracyjne (CBOSA)** | https://orzeczenia.nsa.gov.pl/cbo/query | Wyroki NSA i WSA od 2004 r., teksty zanonimizowane, charakter informacyjny. | Brak API; `robots.txt` blokuje wyszukiwarkę (wg `zrodla/niedostepne.json`); serwis bywa niestabilny (błędy SSL/HTTP 500) | częściowo |
| **Portal Orzeczeń Sądów Powszechnych** | https://orzeczenia.ms.gov.pl | Orzeczenia sądów powszechnych po anonimizacji; wyszukiwanie proste i zaawansowane. | Ochrona antybotowa (CAPTCHA); nie nadaje się do pobierania skryptami | częściowo |
| **SAOS** (System Analizy Orzeczeń Sądowych) | https://www.saos.org.pl | Orzeczenia SN, sądów powszechnych i administracyjnych, TK, KIO; REST API: https://www.saos.org.pl/api/search/judgments (dokumentacja: /help/index.php/dokumentacja-api). | Podczas testu 2026-10-11 API zwróciło stronę „Przerwa techniczna”; brak informacji o licencji i limitach. W projekcie jest uśpiony fetcher `zrodla/saos` (`enabled:false`). | częściowo |
| **Portal Informacyjny Sądów Powszechnych** | https://portal.wroclaw.sa.gov.pl | Dostęp do informacji o **własnych** sprawach i składanie pism (konto z weryfikacją, logowanie m.in. przez Login.gov.pl). **To nie jest baza prawa ani orzeczeń.** Adres `portal.sad.gov.pl` NIE istnieje. | – | częściowo |

## 3. Organy i rejestry tematyczne

| Portal | Adres | Co zawiera | Pewność |
|---|---|---|---|
| **UODO** (ochrona danych osobowych) | https://uodo.gov.pl | Wytyczne EROD, aktualności, decyzje Prezesa UODO w zakładce „Orzecznictwo” (ścieżkę sprawdź ręcznie). | częściowo |
| **UOKiK** | https://uokik.gov.pl; decyzje: https://decyzje.uokik.gov.pl; rejestr klauzul niedozwolonych: https://rejestr.uokik.gov.pl | Decyzje Prezesa UOKiK i wyroki SOKiK wpisane do rejestru klauzul niedozwolonych (sygnatura, data wpisu, branża). | sprawdzone (adresy) |
| **KNF** | https://www.knf.gov.pl | Komunikaty, ostrzeżenia publiczne, dane i opracowania, rekomendacje; wyszukiwarka z filtrami kategorii; RSS. | częściowo |
| **BIP** | https://www.gov.pl/web/bip | Biuletyn Informacji Publicznej; wiele organów ma własny BIP. Wniosek o udostępnienie informacji publicznej składa się do organu – zob. ustawa o dostępie do informacji publicznej (Dz.U. 2001 nr 112 poz. 1198: `DU/2001/1198#U` w bazie). | z pamięci |

## 4. Prawo UE i orzecznictwo europejskie

| Portal | Adres | Co zawiera / jak używać | Pewność |
|---|---|---|---|
| **EUR-Lex** | https://eur-lex.europa.eu/homepage.html?locale=pl | Oficjalny portal prawa UE w 24 językach (w tym polskim); wydanie elektroniczne Dz.Urz. UE jest autentyczne od 1 lipca 2013 r. Numer CELEX (np. 32016R0679 dla RODO) lub adres ELI (https://eur-lex.europa.eu/eli/reg/2016/679/oj). Dostęp maszynowy: SPARQL (http://publications.europa.eu/webapi/rdf/sparql) i Cellar REST. W projekcie: uśpiony fetcher `zrodla/eurlex`. | sprawdzone |
| **TSUE (Curia)** | https://curia.europa.eu/site/ | Orzecznictwo Trybunału Sprawiedliwości UE i Sądu: sygnatury C-123/20, T-456/21; alternatywnie przez CELEX (np. 62020CJ0123) w EUR-Lex. | częściowo |
| **ETPCz (HUDOC)** | https://hudoc.echr.coe.int/ | Orzecznictwo Europejskiego Trybunału Praw Człowieka; numer skargi w formie 12345/10; tłumaczenia polskie wyroków dot. Polski także na stronie TK (trybunal.gov.pl/orzeczenia-etpcz/…). | częściowo |

## 5. Cytowanie i status źródeł

- Dla wiążącego brzmienia powołuj się na Dziennik Ustaw (tekst ogłoszony i obwieszczenie o tekście jednolitym); tekst ujednolicony z ISAP jest pomocą informacyjną – `teksty-jednolite-ujednolicone-zmieniajace`.
- Nowelizacje ustawy o ogłaszaniu aktów: podstawa opracowania tekstu ujednoliconego to t.j. z 2019 r. oraz zmiana z 2026 r. („Dz. U. z 2019 r. poz. 1461, z 2026 r. poz. 912.”) [DU/2000/718#U art. 3] – dobry przykład, jak przypis w tekście ujednoliconym wskazuje świeże nowelizacje.
- Zasady zapisu dzienników i powołania aktów – `jak-cytowac-przepisy`; ZTP wymagają skrótów Dz. U., M.P., Dz. Urz. UE [DU/2026/300 § 162].
- Do każdego z powyższych portali stosuj własne warunki korzystania; nie obchodź zabezpieczeń antybotowych ani zakazów w `robots.txt`.

## 6. Co jest, a czego nie ma w tej bazie

| Źródło | W bazie? |
|---|---|
| Dz.U. i M.P. (obowiązujące) + teksty ujednolicone ISAP | tak, stan na dzień `data_as_of` |
| Akty uchylone i wygasłe, akty prawa miejscowego, dzienniki wojewódzkie, ministerialne | nie |
| Prawo UE | nie (uśpione `zrodla/eurlex`) |
| Orzecznictwo sądów (SN, NSA, sądy powszechne) | nie (uśpione `zrodla/saos`); w bazie są tylko wyroki TK ogłaszane w Dz.U. (kategoria `orzeczenie`) |
| Projekty ustaw, druki sejmowe | nie |

Szczegóły rejestru źródeł: `zrodla/sources.json` i `zrodla/README.md`; źródła, których nie da się dodać, i powody: `zrodla/niedostepne.json`.
