# ChatGPT i OpenAI – podłączenie

Klikalna wersja z kopiowaniem snippetów i testem połączenia: `/podlacz.html` na Twoim wdrożeniu. Stan dokumentacji sprawdzono 2026-10-11 (procedura odświeżania: `ai/SOURCES.md`). Gemini ma osobny plik: `ai/gemini/INSTRUCTIONS.md`.

Reguła niezależna od klienta: w każdej odpowiedzi opartej na API model podaje „Stan danych na dzień <data_as_of>” (pole `data_as_of`, nagłówek `X-Data-As-Of`, `/api/health`, `/data-info.json`). Jako instrukcję użyj `ai/SYSTEM_PROMPT.md`.

## Którą drogę wybrać
| Droga | Status | Uwagi |
|---|---|---|
| ChatGPT: wtyczka z własnym serwerem MCP | zalecana dla nowych wdrożeń | etykiety menu i wymagane plany niepotwierdzone przez OpenAI |
| ChatGPT: Custom GPT z Actions (OpenAPI) | wygaszana | OpenAI zapowiedziało zastąpienie Custom GPT „pluginami” (relacje prasowe z września 2026, nie oficjalna strona OpenAI); planowane wygaszenie 11.12.2026 – nie buduj na tym nowych rzeczy |
| OpenAI Responses API + narzędzie `mcp` | zweryfikowane | wymaga klucza API OpenAI |
| Agents SDK | częściowo zweryfikowane | tryb hostowany lub lokalny |
| Codex CLI | zweryfikowane | `~/.codex/config.toml` |

## 1. ChatGPT – wtyczka z serwerem MCP (zalecana)
Niezweryfikowane w oficjalnej dokumentacji OpenAI: wymagane plany (źródła zewnętrzne wskazują Plus, Pro, Business, Enterprise, Edu; Free bez własnych serwerów), dokładne etykiety menu (w lipcu 2026 „apps” przemianowano na „plugins”; ścieżka z trybem Developer mode mogła zostać usunięta). Oficjalna strona opisuje tylko, że dostępne są protokoły SSE i streaming HTTP oraz tryby „OAuth”, „No authentication”.
1. Wejdź na `chatgpt.com/plugins` (wersja webowa). Aplikacje MCP nie działają w aplikacji mobilnej ani w Advanced Voice.
2. Plus > **Add custom MCP server**.
3. Nazwa `Prawo PL`, opis: „Wyszukiwarka polskiego prawa (Dz.U., M.P.). Zawsze podawaj datę stanu danych (data_as_of).”
4. Server URL: `https://TWOJA-DOMENA.vercel.app/api/mcp`.
5. Authentication: **No authentication**. W UI nie ma pola na nagłówek Bearer ani `x-api-key` – jeśli włączysz `API_KEY` na serwerze, ta wtyczka przestanie działać.
6. Zaznacz potwierdzenie ostrzeżenia o ryzyku i kliknij **Create as a plugin**.
7. Zainstaluj wtyczkę. W nowej rozmowie wpisz `@` i wybierz ją. Po zmianie narzędzi na serwerze kliknij **Refresh** w ustawieniach wtyczki.
8. Bez adnotacji `readOnlyHint` przy narzędziach ChatGPT może prosić o potwierdzenie każdego wywołania.
Polityki workspace (np. Lockdown) mogą blokować własne serwery – wtedy poproś administratora.

## 2. Custom GPT z Actions (przejściowo, do wygaszenia)
Etykiety przycisków pochodzą z pamięci i streszczeń wyszukiwarki (help.openai.com zwracał 403) – niezweryfikowane.
1. ChatGPT > Explore GPTs > Create > Configure > Actions > Create new action.
2. Schemat: zaimportuj z URL `https://TWOJA-DOMENA.vercel.app/openapi.json`, a jeśli import z URL nie jest dostępny – wklej treść pliku.
3. Authentication: **None**. Tylko w trybie zamkniętym: API Key > Bearer > klucz (nigdy nie wpisuj klucza do schematu). Oficjalna dokumentacja Actions podaje, że niestandardowe nagłówki nie są wspierane, więc trzymaj się trybu Bearer.
4. Privacy policy: wymagana przy publicznym udostępnieniu (potrzebna strona z polityką prywatności); dla prywatnego GPT można pominąć.
5. Instructions: wklej tekst poniżej.
6. Limity Actions (oficjalna dokumentacja): 45 s na zapytanie, treść zapytania i odpowiedzi poniżej 100 000 znaków, opis operacji do 300 znaków, opis parametru do 700 znaków, TLS 1.2+ na porcie 443.
7. Błąd „Could not find a valid URL in servers”: pole `servers` w `/openapi.json` to adres względny (`/`). Wklej schemat zamiast importować go z URL i ustaw tam `servers: [{"url": "https://TWOJA-DOMENA.vercel.app"}]`.
Custom Actions nie migrują automatycznie do wtyczek – trzeba je odtworzyć jako serwer MCP (pkt 1).

### Instructions dla GPT
```
Jesteś asystentem informacji o prawie polskim. Masz Action z endpointami searchLaw (/api/search), getArticle (/api/article), getAct (/api/act).
ZASADY:
1. Szukaj krótką frazą kluczową (2–4 słowa), ewentualnie "art. N" + nazwa aktu. Nie wklejaj całego pytania.
2. Każdy przepis, który cytujesz, zweryfikuj przez getArticle (id = eli, np. DU/1964/93; art = numer, np. 446; artykuły z indeksem: 442[1]).
3. NIGDY nie wymyślaj numerów artykułów ani treści. Brak wyniku nie oznacza braku przepisu – powiedz to.
4. Hierarchia: ujednolicone > jednolite > podstawowe (brzmienie z dnia ogłoszenia, może być nieaktualne) > zmieniające (nowelizacje, nie obowiązująca treść). Orzeczenia i umowy to nie przepisy.
5. Przekaż użytkownikowi pole warnings; przy truncated=true zaznacz obcięcie.
6. Cytuj: art. N § M k.c. (display_address, kategoria) + source_url; cytat dosłowny w cudzysłowie.
7. Dopytaj (1–2 pytania), gdy wynik zależy od daty zdarzenia, rodzaju umowy, stron, rodzaju sprawy.
8. OBOWIĄZKOWO w każdej odpowiedzi opartej na API podaj "Stan danych na dzień <data_as_of>" (pole data_as_of z odpowiedzi lub /api/health) i ostrzeż: przepisy ogłoszone po tej dacie nie są uwzględnione; teksty ujednolicone mogą być starsze niż data_as_of.
9. Nie udzielaj pewnych porad; unikaj "na pewno". Zakończ: "To informacja ogólna, nie porada prawna; sprawdź aktualność w ISAP lub skonsultuj się z prawnikiem."
10. Odpowiadaj w języku użytkownika.
```

## 3. OpenAI API – Responses API z narzędziem MCP (zweryfikowane)
Serwer jest zdalny, publiczny i bez OAuth, więc pola `authorization` i `headers` są zbędne. Za `TU-AKTUALNY-MODEL` wstaw aktualny identyfikator z `https://developers.openai.com/api/docs/models`.
```bash
curl https://api.openai.com/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "TU-AKTUALNY-MODEL",
    "instructions": "Odpowiadaj na podstawie narzędzi prawa polskiego. Zawsze podaj stan danych (data_as_of).",
    "tools": [{
      "type": "mcp",
      "server_label": "prawo_pl",
      "server_description": "Wyszukiwarka polskiego prawa (Dz.U., M.P.).",
      "server_url": "https://TWOJA-DOMENA.vercel.app/api/mcp",
      "require_approval": "never",
      "allowed_tools": ["search_law", "get_article", "get_act"]
    }],
    "input": "Co mówi art. 30 Kodeksu pracy o rozwiązaniu umowy?"
  }'
```
- `require_approval`: domyślnie OpenAI prosi o zgodę (`mcp_approval_request`); dla publicznych danych tylko do odczytu można ustawić `never`.
- Tryb zamknięty (`API_KEY`): dodaj `"headers": {"Authorization": "Bearer TWOJ_KLUCZ"}` (pole `headers` jest w referencji API; poradnik go nie opisuje).
- W odpowiedzi: elementy `mcp_list_tools`, `mcp_call`, `mcp_approval_request`.

## 4. Agents SDK (częściowo zweryfikowane)
Python, tryb lokalny (nazwy pakietów i dokładna sygnatura konstruktora z pamięci):
```python
import asyncio
from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp

async def main():
    async with MCPServerStreamableHttp(
        name="prawo_pl",
        params={"url": "https://TWOJA-DOMENA.vercel.app/api/mcp", "timeout": 10},
        cache_tools_list=True,
    ) as server:
        agent = Agent(name="Asystent prawa PL",
                      instructions="Korzystaj z narzędzi prawa. Zawsze podaj stan danych (data_as_of).",
                      mcp_servers=[server])
        r = await Runner.run(agent, "Co mówi art. 8 Kodeksu pracy?")
        print(r.final_output)

asyncio.run(main())
```
TypeScript, tryb hostowany: `hostedMcpTool({ serverLabel: 'prawo_pl', serverUrl: 'https://TWOJA-DOMENA.vercel.app/api/mcp', requireApproval: 'never', allowedTools: ['search_law','get_article','get_act'] })`.

## 5. Codex CLI (zweryfikowane)
`~/.codex/config.toml` (Windows prawdopodobnie `%USERPROFILE%\.codex\config.toml`):
```toml
[mcp_servers.prawo_pl]
url = "https://TWOJA-DOMENA.vercel.app/api/mcp"
enabled_tools = ["search_law", "get_article", "get_act"]
startup_timeout_sec = 20
tool_timeout_sec = 60
# tylko w trybie zamkniętym: bearer_token_env_var = "PRAWO_API_KEY"
```
Weryfikacja: `codex mcp list`, w TUI `/mcp`.

## 6. Function calling (bez MCP, własna pętla)
Aplikacja pośrednia wykonuje wywołanie HTTP do API i zwraca wynik modelowi. Definicje (JSON Schema; w OpenAI Responses `tools[]` jako `{"type":"function", ...}`, w Gemini `functionDeclarations`):

```json
[
  {
    "name": "searchLaw",
    "description": "Full-text search w polskich aktach prawnych. Krótka fraza kluczowa, opcjonalnie 'art. N' i nazwa aktu. Zwraca snippety; dokładne brzmienie sprawdź getArticle.",
    "parameters": {
      "type": "object",
      "properties": {
        "q": {"type": "string", "description": "Fraza kluczowa, np. 'zadośćuczynienie śmierć najbliższego'"},
        "kategoria": {"type": "string", "enum": ["ujednolicone","jednolite","podstawowe","zmieniajace","mp","orzeczenie","umowa","inne","wyrok","ue"]},
        "act": {"type": "string", "description": "eli aktu, np. DU/1964/93"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 20}
      },
      "required": ["q"]
    }
  },
  {
    "name": "getArticle",
    "description": "Dokładne brzmienie artykułu aktu. Używaj do weryfikacji przed cytowaniem.",
    "parameters": {
      "type": "object",
      "properties": {
        "id": {"type": "string", "description": "eli (DU/1964/93) lub doc_id (DU/1964/93#U)"},
        "art": {"type": "string", "description": "Numer artykułu, np. '445' lub '442[1]'"},
        "variant": {"type": "string", "enum": ["U"], "description": "U = tekst ujednolicony"}
      },
      "required": ["id", "art"]
    }
  },
  {
    "name": "getAct",
    "description": "Metadane aktu i opcjonalnie spis artykułów.",
    "parameters": {
      "type": "object",
      "properties": {
        "id": {"type": "string"},
        "variant": {"type": "string", "enum": ["U"]},
        "include_toc": {"type": "string", "enum": ["1"]}
      },
      "required": ["id"]
    }
  }
]
```
Uwaga: w trybie `strict: true` (OpenAI) wszystkie pola muszą być w `required` i `additionalProperties: false` – dostosuj schemat albo nie używaj `strict`.

Mapowanie na HTTP: `searchLaw` -> `GET /api/search`, `getArticle` -> `GET /api/article`, `getAct` -> `GET /api/act`; nagłówek `Authorization: Bearer KLUCZ` tylko w trybie zamkniętym. Do odpowiedzi modelu dołączaj `data_as_of`. Przy `function_call` wykonaj zapytanie i odeślij JSON jako `function_call_output` (z `call_id`).
