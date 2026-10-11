# UPDATE_SPEC – jak ma działać „Uaktualnij to wszystko”

Cel: właściciel otwiera ten folder w Claude Code i mówi **„Uaktualnij to wszystko”**. Claude uruchamia jedną komendę (`python aktualizuj.py`), która **przyrostowo** odświeża dane, indeks, bazę i stronę, a na końcu daje czytelny raport. Dodatkowe źródła (orzecznictwo, prawo UE, …) są w repo od razu, ale **uśpione** (`enabled:false`) – włącza się je jedną zmianą w `zrodla/sources.json`.

Zasady wspólne: patrz `docs/SPEC.md` (identyfikatory `eli`/`doc_id`, format `chunks.jsonl`, schemat bazy). Ten plik dodaje kontrakty aktualizacji. Dziś: 2026-10-11.

## Układ (kto jest właścicielem)
| Ścieżka | Właściciel | Opis |
|---|---|---|
| `pipeline/update_data.py` (+ `pipeline/update_lib/`) | A1 | przyrostowe odświeżanie `dane/` + manifest |
| `pipeline/export_chunks.py`, `pipeline/load_to_postgres.py` | A2 | tryby przyrostowe (`--changed`, `--sync`), wiele plików wejściowych |
| `zrodla/` (`sources.json`, `saos/`, `eurlex/`, `README.md`) | B | rejestr źródeł + uśpione fetchery |
| `vercel/public/wiedza/**`, `vercel/public/llms.txt` | C | baza wiedzy o prawie (md + `index.json`) |
| `vercel/public/index.html`, `vercel/public/podlacz.html`, `ai/**`, `pipeline/build_data_info.py` | D | strona główna, instrukcja podłączenia, instrukcje AI, generowanie data-info + patch fallbacku w index.html |
| `aktualizuj.py`, `CLAUDE.md`, `.claude/**`, `.env.example` (root), `README.md`, `docs/DEPLOY.md`, `docs/AKTUALIZACJA.md`, `.gitignore` | E | orkiestrator, instrukcje dla Claude Code, skill/komenda, konfiguracja |
Nikt nie edytuje cudzych plików. Nie ruszaj `prawnik.py`, `pobierz_prawo.py`, `pobierz_wiecej.py`, `kategorie.py`, `przeklasyfikuj.py` (legacy; można z nich importować `kategorie.kategoria`).

## Katalogi stanu (nie trafiają do GitHuba, patrz .gitignore)
- `stan/manifest.json` – mapa `klucz -> {status, changeDate, kategoria, files:[…], sha256?}`; klucze: `DU/2024/1984`, `MP/2026/977`, `DU/1964/93#U`.
- `stan/zmiany.json` – wynik ostatniego `update_data.py`: `{"run_at": ISO, "added":[doc_id…], "changed":[doc_id…], "removed":[doc_id…], "unchanged": N, "latest": {"DU": "Dz.U. 2026 poz. …", "MP": "…"}}` (`doc_id` jak w chunks, np. `DU/1964/93#U`).
- `stan/ostatnia_aktualizacja.json`, `stan/raport_YYYY-MM-DD.md` – raporty.
- `dane/_wycofane/<kategoria>/…` – pliki aktów, które przestały być „obowiązujące” (przeniesione, nie skasowane – da się cofnąć).
- `.env.local` (root, w .gitignore): `DATABASE_URL=…` (nigdy nie wypisywać wartości w logach/raportach).
- `.claude/uaktualnij.config.json`: `{"auto_load_db": true, "auto_commit": true, "auto_push": false, "auto_deploy": false, "backup_before_update": true}` – trwała zgoda właściciela na kroki zewnętrzne. `false` = Claude pyta przed wypchnięciem/wdrożeniem.

## Kontrakt `pipeline/update_data.py` (A1)
`python pipeline/update_data.py [--dry-run] [--bootstrap] [--full] [--dane DIR] [--stan DIR] [--lata 2025,2026] [--workers N]`
- Pobiera świeże metadane DU i MP (wszystkie lata, WSZYSTKIE statusy – by wykryć zmiany statusu). Wynik końcowy musi być zgodny z dzisiejszym formatem `dane/indeks_obowiazujacych.json`, `indeks_mp.json`, `indeks_ujednolicone.json` (lista obiektów z polami API + `kategoria`; kategorie z `kategorie.kategoria`).
- Zbiory docelowe: DU ze statusem `obowiązujący` (teksty HTML, w razie braku PDF → `dane/<kategoria>/DU_<rok>_<poz>.(html|pdf)`); M.P. `obowiązujący` (`dane/mp/MP_…`); teksty ujednolicone typu `U` dla DU o statusie `obowiązujący` lub `akt posiada tekst jednolity` (`dane/ujednolicone/U-DU_<rok>_<poz>.pdf`, URL `/eli/acts/DU/<r>/<p>/text/U/<plik>`).
- Przyrostowo: nowe → pobierz; `changeDate` nowsze niż w manifeście → pobierz ponownie i porównaj sha256 (zmiana treści ⇒ `changed`); status przestał być obowiązujący lub akt zniknął → przenieś pliki do `dane/_wycofane/` (`removed`); zmiana kategorii → przenieś plik.
- `--bootstrap`: zbuduj manifest z istniejących `dane/` i indeksów BEZ pobierania treści (pierwszy raz); `--full`: pobierz wszystko od nowa.
- `--dry-run`: tylko raport planowanych zmian; nic nie zapisuje poza stdout. Każdy zapis do `dane/` atomowy (plik tymczasowy → rename). Wznawialne po przerwaniu. Retry z backoffem, limit współbieżności ≤ 12. Zwraca kod 0 nawet gdy brak zmian; kod ≠ 0 tylko przy błędzie krytycznym.
- Zapisuje `stan/zmiany.json` (patrz wyżej) oraz odświeża trzy pliki indeksów w `dane/`.

## Kontrakt eksportu/ładowania (A2)
- `python pipeline/export_chunks.py --changed stan/zmiany.json`: usuń z `pipeline/out/chunks.jsonl` wiersze doc_id z `changed`+`removed`, wyeksportuj `added`+`changed` i dopisz (zapis atomowy przez plik tymczasowy), zapisz też `pipeline/out/chunks_delta.jsonl` (tylko nowe wiersze). Dotychczasowe flagi bez zmian. Raport do `pipeline/out/raport.txt`.
- `python pipeline/load_to_postgres.py --sync stan/zmiany.json [--input plik1 plik2 …] [--max-mb N]`: w transakcji usuń z bazy `removed`+`changed`, załaduj `added`+`changed` z chunks (COPY), przelicz `n_chunks`, `ANALYZE`; nowe dokumenty dodawaj tylko jeśli `pg_database_size` < `--max-mb` (jeśli podano). `--input` przyjmuje wiele plików (np. `chunks.jsonl`, `chunks_saos.jsonl`). Bez `--sync` zachowanie dotychczasowe. `--dry-run` wspierany.
- Brak `DATABASE_URL` → czytelny komunikat, kod 2 (orkiestrator traktuje to jako „krok pominięty”).

## Kontrakt źródeł dodatkowych (B)
`zrodla/sources.json`: lista `{"id","nazwa","opis","enabled","kategoria","skrypt","wyjscie","zakres","licencja","status":"aktywne|uśpione|planowane"}`. Źródła aktywne dziś: `eli-du`, `eli-mp`, `isap-ujednolicone` (obsługiwane przez `update_data.py`, wpisy tylko informacyjne, `skrypt:null`). Uśpione: `saos` (wyroki sądów), `eurlex` (prawo UE). Planowane: `tk` (Trybunał Konstytucyjny), `sn` (Sąd Najwyższy), `nsa` (orzeczenia.nsa.gov.pl) – tylko wpis opisowy, jeśli istnieje publiczne API; inaczej adnotacja dlaczego brak.
Każdy fetcher: `python zrodla/<id>/fetch.py [--limit N] [--since YYYY-MM-DD] [--out PLIK] [--dry-run]`, przyrostowy (stan w `stan/zrodlo_<id>.json`: `last_run`, `count`, `newest_date`), pisze `pipeline/out/chunks_<id>.jsonl` zgodnie z `docs/SPEC.md` (`kategoria` = `wyrok` lub `ue`, `doc_id` np. `SAOS/12345`, `CELEX/32016R0679`, `source_url` do oryginału, ostrzeżenia dla modeli – patrz `vercel/lib/warnings.ts`). Szanuje limity serwisów (User-Agent z opisem, opóźnienia, retry). Domyślnie `--limit 25` w testach. NIE uruchamiać pełnych pobrań.

## Kontrakt orkiestratora `aktualizuj.py` (E)
`python aktualizuj.py [--dry-run] [--bez-bazy] [--bez-wdrozenia] [--bez-zrodel] [--tylko KROK] [--pierwszy-raz]`
Kroki w kolejności: `kopia` → `dane` (update_data) → `zrodla` (włączone w sources.json) → `eksport` → `info` (build_data_info) → `testy` (tsc+vitest w vercel/) → `baza` (load --sync) → `commit` → `wdrozenie`. Każdy krok loguje start/wynik/czas; błąd kroku krytycznego zatrzymuje dalsze; `baza` bez `DATABASE_URL` = pominięte z ostrzeżeniem; `commit`/`wdrozenie`/push tylko zgodnie z `.claude/uaktualnij.config.json` (inaczej tylko wypisz co zrobić). Na końcu: `stan/raport_YYYY-MM-DD.md` + podsumowanie po polsku: ile nowych/zmienionych/wycofanych aktów, najnowszy Dz.U./M.P., nowa data `data_as_of`, co pominięto i dlaczego. Nigdy nie wypisuje sekretów.

## `data-info.json` (D)
Pola jak dziś + `sources:[{id,nazwa,status,enabled,count,newest_date}]` (z `zrodla/sources.json` i `stan/`), `last_update_run` (ISO). `build_data_info.py` dodatkowo PATCHUJE blok fallbacku w `vercel/public/index.html` między znacznikami `<!--DATA-INFO:START-->` i `<!--DATA-INFO:END-->` tak, by bez JS strona pokazywała aktualne daty (bez ręcznej edycji).

## Baza wiedzy (C)
Pliki `vercel/public/wiedza/*.md` + `vercel/public/wiedza/index.json` (`[{slug,tytul,opis,tagi,zweryfikowano:"YYYY-MM-DD"}]`). Każde twierdzenie dotyczące konkretnego przepisu ma odnośnik `[DU/1964/93#U art. 118]` zweryfikowany z tekstem w `pipeline/out/chunks.jsonl`. Czego nie da się zweryfikować w danych – oznaczyć „wiedza ogólna, do weryfikacji w ISAP” albo pominąć. Zero zmyślonych numerów artykułów.
