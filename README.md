# Prawo PL – otwarte API prawa polskiego dla modeli AI

**English summary.** Open, read-only API and MCP server giving AI models (Claude, GPT, Gemini...) full-text search and exact article wording for Polish law: Dziennik Ustaw (Journal of Laws) and Monitor Polski, sourced from the Sejm ELI API. Data snapshot: **11 Oct 2026** (latest Dz.U. 2026 item 1307 of 8 Oct 2026; M.P. 2026 item 977 of 6 Oct 2026). Consolidated texts may be older than the snapshot. Not legal advice. Code: MIT. Legal acts themselves are not protected by copyright in Poland (art. 4(1) of the Copyright Act); keep the source attribution.

## Co to jest

Zestaw skryptów i usługa (Vercel + Postgres/Neon), która udostępnia modelom AI:

- wyszukiwanie pełnotekstowe po fragmentach aktów (`search_law`),
- dokładne brzmienie artykułu (`get_article`),
- metadane aktu i spis artykułów (`get_act`),

dla aktów prawa polskiego ogłoszonych w Dzienniku Ustaw (Dz.U.) i Monitorze Polskim (M.P.). Cel: model cytuje prawdziwe przepisy zamiast zgadywać. API jest **publiczne i otwarte** – klucz jest opcjonalny (tryb zamknięty włącza się tylko wtedy, gdy właściciel wdrożenia ustawi zmienną `API_KEY`).

## Aktualność danych

Źródło: [API ELI Sejmu RP](https://api.sejm.gov.pl/eli). Szczegóły w pliku [`vercel/public/data-info.json`](vercel/public/data-info.json) (serwowanym też jako `/data-info.json`; pole `data_as_of` jest zwracane w odpowiedziach API i w `/api/health`).

| Pozycja | Wartość |
|---|---|
| **Stan danych (`data_as_of`)** | **11.10.2026** (pobrano 2026-10-11 15:21 UTC) |
| Najnowszy akt w Dz.U. | **Dz.U. 2026 poz. 1307**, ogłoszony 8.10.2026 (ostatnia zmiana w API: 9.10.2026) |
| Najnowszy akt w M.P. | **M.P. 2026 poz. 977**, ogłoszony 6.10.2026 |
| Liczba dokumentów | Dz.U.: 17 737; M.P.: 2 743; teksty ujednolicone: 1 688 |
| Najnowszy tekst ujednolicony | Dz.U. 2026 poz. 1070 (ogłoszony 7.08.2026) |

**Ważne:**

- Przepisy ogłoszone **po 11.10.2026** nie są uwzględnione.
- Tekst ujednolicony odzwierciedla stan prawny **na dzień jego sporządzenia** – może być starszy niż `data_as_of`, a zmiany ogłoszone później mogą nie być w nim ujęte.
- Zakres: tylko akty o statusie „obowiązujący” (+ teksty ujednolicone z ISAP).

### Jak odświeżyć dane („Uaktualnij to wszystko”)

Otwórz folder w Claude Code i napisz **„Uaktualnij to wszystko”** albo uruchom jedną komendę:

```powershell
python aktualizuj.py --dry-run     # plan: co jest nowe, zmienione, wycofane (niczego nie zmienia)
python aktualizuj.py               # przyrostowa aktualizacja: kopia -> dane -> źródła -> eksport -> info -> testy -> baza -> commit -> wdrożenie
```

Pobiera tylko nowości, przenosi uchylone akty do `dane\_wycofane\`, odświeża bazę w jednej transakcji i `data_as_of`, a na końcu zapisuje raport `stan\raport_RRRR-MM-DD.md`. Push na GitHub i wdrożenie na Vercel dzieją się dopiero za Twoją zgodą (`.claude\uaktualnij.config.json`). Hasło do bazy (`DATABASE_URL`) wpisz do `.env.local` (wzór: `.env.example`). Opis dla właściciela: **[docs/AKTUALIZACJA.md](docs/AKTUALIZACJA.md)**; instrukcja dla Claude'a: [CLAUDE.md](CLAUDE.md).

Ręczne kroki (starsze skrypty, nadal działają; do pierwszego pobrania całości):

```powershell
python pobierz_prawo.py                # pobranie aktów z ELI Sejmu
python pobierz_wiecej.py               # uzupełnienia (m.in. teksty ujednolicone)
python pipeline\export_chunks.py       # pełny eksport fragmentów do pipeline\out\chunks.jsonl (ok. 9 min)
python pipeline\build_data_info.py     # odświeża vercel\public\data-info.json (data_as_of)
python pipeline\load_to_postgres.py    # pełne ładowanie do Postgresa (patrz docs\DEPLOY.md)
```

Pominięcie `build_data_info.py` oznacza, że API będzie podawać nieaktualną datę stanu danych. `aktualizuj.py` robi to sam.

## Czego nie obejmuje

- akty uchylone i wygasłe,
- prawo UE (źródło EUR-Lex jest przygotowane, ale uśpione),
- orzecznictwo sądów (poza wyrokami TK ogłaszanymi w Dz.U.; źródło SAOS jest przygotowane, ale uśpione),
- akty prawa miejscowego i dzienniki wojewódzkie,
- akty ogłoszone po dacie `data_as_of`.

## Architektura

```
 ELI Sejm (api.sejm.gov.pl/eli)
        |  pobierz_prawo.py, pobierz_wiecej.py
        v
 dane\ (PDF/HTML, lokalnie, poza repo)
        |  pipeline\export_chunks.py   -> chunks.jsonl
        |  pipeline\build_data_info.py -> data-info.json
        v
 pipeline\load_to_postgres.py
        v
 Postgres (Neon) -- FTS + pg_trgm + unaccent
        ^
        |  vercel\api\*.ts
 Vercel: /api/search /api/article /api/act /api/health /api/mcp
        ^
        |  REST / MCP / OpenAPI Actions
 Modele AI (Claude, GPT, Gemini, Cursor...)
```

## Szybki start (wdrożenie)

Pełna instrukcja: **[docs/DEPLOY.md](docs/DEPLOY.md)** (Neon, ładowanie danych, Vercel, publikacja na GitHub). W skrócie: baza Neon -> `python pipeline\load_to_postgres.py --schema` -> `vercel --prod` w katalogu `vercel\` z ustawionym `DATABASE_URL`.

Repozytorium: `https://github.com/xccssdsdsd-source/prawo`.

## Endpointy

Baza: `https://TWOJA-DOMENA.vercel.app` *(placeholder)*.

| Endpoint | Opis |
|---|---|
| `GET /api/search?q=` | wyszukiwanie fragmentów (filtry: `kategoria`, `act`, `limit`) |
| `GET /api/article?id=&art=` | dokładne brzmienie artykułu |
| `GET /api/act?id=&include_toc=1` | metadane aktu i spis artykułów |
| `GET /api/health` | stan usługi i `data_as_of` |
| `POST /api/mcp` | serwer MCP (Streamable HTTP) |
| `/openapi.json`, `/llms.txt`, `/data-info.json` | opis API, wskazówki dla LLM, aktualność danych |

Klucz API jest opcjonalny; jeśli właściciel go włączył, przesyłaj `Authorization: Bearer <klucz>` lub `x-api-key`.

## Podłączenie Claude / GPT / Gemini

- **Kreator krok po kroku dla 37 klientów AI** (Claude, ChatGPT, Gemini, Cursor, VS Code ...) z testem połączenia: po wdrożeniu otwórz `https://TWOJA-DOMENA.vercel.app/podlacz.html` (plik: [vercel/public/podlacz.html](vercel/public/podlacz.html)). Domenę podstawia sam z paska adresu.
- Gemini: [ai/gemini/INSTRUCTIONS.md](ai/gemini/INSTRUCTIONS.md); skąd pochodzą instrukcje i jak je odświeżać: [ai/SOURCES.md](ai/SOURCES.md)
- Claude Code / Desktop / Cursor (MCP): [ai/mcp/README.md](ai/mcp/README.md)
- Skill dla Claude: [ai/claude-skill/SKILL.md](ai/claude-skill/SKILL.md)
- Custom GPT / Gemini / function calling: [ai/openai-actions/INSTRUCTIONS.md](ai/openai-actions/INSTRUCTIONS.md)
- System prompt: [ai/SYSTEM_PROMPT.md](ai/SYSTEM_PROMPT.md)

## Zasady czytania prawa przez agentów (skrót)

1. Nigdy nie wymyślaj numerów artykułów ani treści – cytuj tylko to, co zwróciło API; każdy przepis weryfikuj przez `get_article`.
2. Hierarchia źródeł: ujednolicone > jednolite > podstawowe > zmieniające (nowelizacja nie jest obowiązującą treścią).
3. **W każdej odpowiedzi opartej na API podaj „Stan danych na dzień <data_as_of>”** i ostrzeż, że przepisy ogłoszone po tej dacie nie są uwzględnione, a teksty ujednolicone mogą być starsze.
4. Przekazuj `warnings`, zaznaczaj `truncated`, kończ zastrzeżeniem „to nie porada prawna”.

Pełne zasady: [ai/AGENTS.md](ai/AGENTS.md).

## Baza wiedzy o polskim prawie

Poradniki w markdown po polsku dla modeli i ludzi (hierarchia źródeł prawa, jak czytać akt, jak cytować, terminy i przedawnienie, kodeksy i główne ustawy, słownik pojęć, pułapki, nadchodzące zmiany ...): [vercel/public/wiedza/](vercel/public/wiedza/) - po wdrożeniu `/wiedza/<temat>.md`, spis `/wiedza/index.json`, skrót w `/llms.txt`. Każde twierdzenie o przepisie ma odnośnik do artykułu zweryfikowany z danymi (`python pipeline\tools\lookup_article.py --verify-md ...`). To nie jest porada prawna. Zasady utrzymania: [vercel/public/wiedza/README.md](vercel/public/wiedza/README.md).

## Dodatkowe źródła (uśpione)

Orzeczenia sądów (SAOS) i prawo UE po polsku (EUR-Lex) są przygotowane w `zrodla\`, ale wyłączone (`enabled:false` w `zrodla\sources.json`). Włączenie i ograniczenia (licencja SAOS, rozmiar bazy): [zrodla/README.md](zrodla/README.md).

## Rozmiar danych

Katalog `dane\` (PDF/HTML) to gigabajty, a `pipeline\out\chunks.jsonl` ma ok. 956 MB (przekracza limit pliku GitHub 100 MB) – **nie trafiają do repozytorium** (`.gitignore`). Każdy odtwarza je własnymi skryptami. Darmowy plan Neon (~0,5 GB) mieści praktycznie tylko teksty ujednolicone; pełny zbiór wymaga planu płatnego.

## Zastrzeżenie

Narzędzie pomocnicze, **nie porada prawna** i nie oficjalne źródło prawa. Treść może zawierać błędy, braki lub być nieaktualna. Wiążące są wyłącznie akty opublikowane urzędowo. Aktualne brzmienie zawsze weryfikuj w [ISAP](https://isap.sejm.gov.pl) lub u prawnika. Autorzy nie odpowiadają za skutki korzystania z danych.

## Licencja i źródło danych

- **Kod:** MIT – zob. [LICENSE](LICENSE).
- **Dane:** akty normatywne (ustawy, rozporządzenia itd.) nie podlegają prawu autorskiemu (art. 4 pkt 1 ustawy o prawie autorskim i prawach pokrewnych). Dane pobrano z API ELI Sejmu RP. Zachowaj wzmiankę o źródle: „Źródło: Sejm RP, API ELI (api.sejm.gov.pl/eli); ISAP”. Pochodne opracowania (podział na fragmenty, klasyfikacja) są częścią kodu na licencji MIT, bez gwarancji.
