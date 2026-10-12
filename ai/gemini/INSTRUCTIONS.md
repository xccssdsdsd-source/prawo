# Gemini – podłączenie (CLI, Antigravity, API, AI Studio, aplikacja)

Klikalna wersja z kopiowaniem snippetów i testem połączenia: `/podlacz.html` na Twoim wdrożeniu. Stan dokumentacji Google sprawdzono 2026-10-11 (procedura odświeżania i lista adresów: `ai/SOURCES.md`). Wszystkie snippety poniżej złożono z udokumentowanych pól, ale NIE uruchamiano ich przeciwko wdrożonemu serwerowi.

Reguła niezależna od klienta: w każdej odpowiedzi opartej na API model podaje „Stan danych na dzień <data_as_of>”. Jako instrukcję systemową użyj `ai/SYSTEM_PROMPT.md`.

## Uczciwe podsumowanie: co działa, a co nie
| Droga | Wynik | Pewność |
|---|---|---|
| Antigravity (CLI `agy`, IDE) + MCP | działa w założeniu (klucz `serverUrl`) – najrealniejsza droga dla osoby z Polski | zweryfikowane w dokumentacji, niesprawdzone z naszym serwerem |
| Gemini CLI + MCP | dla kont indywidualnych zastąpiony przez Antigravity CLI (18.06.2026); nadal dla płatnych kluczy API i klientów enterprise | zweryfikowane |
| Gemini API: narzędzie `mcp_server` (Interactions API) | dokumentacja Google jest sprzeczna co do modeli Gemini 3 – trzeba przetestować | częściowo |
| Gemini API: function calling z REST (Python) | najpewniejsza droga programistyczna | częściowo |
| Aplikacja Gemini (gemini.google.com) „Custom apps” | warunki: konto osobiste, 18+, lokalizacja w USA, tylko angielski; z Polski prawdopodobnie niedostępne; brak potwierdzenia, że serwer bez OAuth zostanie przyjęty | częściowo – NIE obiecuj, że działa |
| Gems / skills | tylko zapisane instrukcje, NIE łączą się z API; Gems są wygaszane (listopad 2026 dla kont osobistych) | częściowo |
| Google AI Studio (interfejs) | brak potwierdzenia, że da się podłączyć serwer MCP z poziomu UI; służy do uzyskania klucza API | z pamięci |
| Gemini Enterprise | opcja „No authentication” jest udokumentowana; płatny produkt, konfiguruje administrator | zweryfikowane |
| Google ADK (`McpToolset`, `OpenAPIToolset`) | działa wg dokumentacji | zweryfikowane |

## 1. Antigravity CLI (`agy`) i IDE – zalecane
Instalacja CLI (nowy program, nie aktualizacja Gemini CLI):
- Windows PowerShell: `irm https://antigravity.google/cli/install.ps1 | iex`
- macOS/Linux: `curl -fsSL https://antigravity.google/cli/install.sh | bash`
Uruchom `agy` w katalogu projektu i zaloguj się kontem Google.

Konfiguracja: plik globalny `~/.gemini/config/mcp_config.json` (Windows: `%USERPROFILE%\.gemini\config\mcp_config.json`) albo projektowy `.agents/mcp_config.json` (nadpisuje). Dokumentacja nie opisuje komendy „agy mcp add”.
```json
{
  "mcpServers": {
    "prawo_pl": {
      "serverUrl": "https://TWOJA-DOMENA.vercel.app/api/mcp"
    }
  }
}
```
- Dla serwerów zdalnych używaj pola `serverUrl`; pola `url` i `httpUrl` z Gemini CLI NIE są tu obsługiwane. Nazwa serwera zostaje w snake_case (`prawo_pl`): w Antigravity nie sprawdzono, czy myślnik jest dozwolony. Uwaga: w Gemini CLI (sekcja 2) jest odwrotnie – tam podkreślnik jest zabroniony i używamy `prawo-pl`.
- Tryb zamknięty: dodaj `"headers": { "Authorization": "Bearer TWOJ_KLUCZ" }`.
- Weryfikacja: w panelu wpisz `/mcp` (MCP Manager). Narzędzia MCP działają domyślnie w trybie „Ask” (każde wymaga zgody); regułę zezwalającą `mcp(prawo_pl/*)` ustawisz przez `/permissions`.
- IDE: „...” u góry panelu agenta > MCP Servers > Manage MCP Servers > View raw config.
- Migracja ze starej konfiguracji Gemini CLI: `agy plugin import gemini`.

## 2. Gemini CLI (dla płatnych kluczy API i klientów enterprise)
Od 18.06.2026 Gemini CLI przestał obsługiwać użytkowników Google AI Pro/Ultra i darmowych indywidualnych użytkowników Code Assist (zastąpił go Antigravity CLI). Pozostaje dostępny przez płatne klucze API Gemini i dla klientów Gemini Code Assist Standard/Enterprise. Wymaga Node.js 20+.
```bash
npm install -g @google/gemini-cli
gemini mcp add --transport http --scope user prawo-pl https://TWOJA-DOMENA.vercel.app/api/mcp
gemini mcp list      # w sesji: /mcp
gemini mcp remove prawo-pl   # usuwanie
```
Nazwa serwera to `prawo-pl` (z myślnikiem), bo dokumentacja Gemini CLI zabrania podkreślników w nazwach serwerów MCP: parser polityk dzieli nazwy narzędzi `mcp_serwer_narzedzie` na pierwszym podkreślniku, więc reguły i wildcardy mogłyby po cichu nie działać (źródła: geminicli.com/docs/tools/mcp-server/ i /docs/reference/policy-engine/). W Antigravity i Interactions API Gemini zostaje `prawo_pl` – tam obowiązują inne zasady.
Albo ręcznie `~/.gemini/settings.json`; w Gemini CLI `httpUrl` = Streamable HTTP, a `url` = SSE:
```json
{
  "mcpServers": {
    "prawo-pl": {
      "httpUrl": "https://TWOJA-DOMENA.vercel.app/api/mcp",
      "timeout": 30000,
      "trust": true
    }
  }
}
```
`trust: true` pomija potwierdzenia wywołań – rozsądne dla narzędzi tylko do odczytu; domyślnie `false`. Tryb zamknięty: `"headers": { "Authorization": "Bearer TWOJ_KLUCZ" }`.

## 3. Gemini API – zdalny MCP (Interactions API)
Wymaga klucza z Google AI Studio (`GEMINI_API_KEY`) i `pip install google-genai`. Tylko serwery Streamable HTTP; nazwa serwera w snake_case, bez myślnika.
```python
from google import genai

client = genai.Client()  # czyta GEMINI_API_KEY
interaction = client.interactions.create(
    model="gemini-2.5-flash",   # model wymieniony w Interactions jako wspierający zdalny MCP – sprawdź aktualną listę
    input="Co mówi art. 118 Kodeksu cywilnego o przedawnieniu? Podaj datę stanu danych.",
    tools=[{
        "type": "mcp_server",
        "name": "prawo_pl",
        "url": "https://TWOJA-DOMENA.vercel.app/api/mcp",
        # "headers": {"Authorization": "Bearer TWOJ_KLUCZ"},   # tylko w trybie zamkniętym
        # "allowed_tools": ["search_law", "get_article", "get_act"],
    }],
)
print(interaction.output_text)
```
Odczyt tekstu przez `interaction.output_text` jest pokazany w dokumentacji Interactions (snippet nie był uruchomiony na żywym API). Uwaga: strona Interactions API w sekcji Limitations zawiera zdanie „Gemini 3 does not support remote MCP, this is coming soon”, a strona function calling pokazuje przykład na modelu Gemini 3.x. Dlatego domyślnie użyto `gemini-2.5-flash`; wariant z `gemini-3.8-flash` może zwrócić błąd, dopóki Google nie zdejmie ograniczenia. W razie kłopotów użyj punktu 4.

## 4. Gemini API – function calling z REST (najpewniejsze)
Zwykłe funkcje Pythona przekazane w `tools` SDK wywołuje automatycznie (automatic function calling). Uwaga z README SDK: w następnej wersji głównej AFC z bezpośrednich wywołań `generate_content` ma zniknąć – użyj wtedy `Chats` albo ręcznej pętli.
```python
# pip install google-genai requests
import requests
from google import genai
from google.genai import types

BASE = "https://TWOJA-DOMENA.vercel.app"
HEADERS = {}  # {"x-api-key": "..."} tylko w trybie zamkniętym

def search_law(q: str) -> dict:
    """Wyszukuje w polskich przepisach prawa. Zwraca wyniki i pole data_as_of."""
    return requests.get(f"{BASE}/api/search", params={"q": q}, headers=HEADERS, timeout=30).json()

def get_article(id: str, art: str) -> dict:
    """Pobiera treść artykułu aktu prawnego (id aktu np. DU/1964/93, numer artykułu)."""
    return requests.get(f"{BASE}/api/article", params={"id": id, "art": art}, headers=HEADERS, timeout=30).json()

def get_act(id: str) -> dict:
    """Pobiera metadane aktu prawnego."""
    return requests.get(f"{BASE}/api/act", params={"id": id}, headers=HEADERS, timeout=30).json()

client = genai.Client()
response = client.models.generate_content(
    model="gemini-flash-latest",
    contents="Co mówi art. 118 Kodeksu cywilnego? Podaj datę stanu danych.",
    config=types.GenerateContentConfig(
        tools=[search_law, get_article, get_act],
        system_instruction="Zawsze podawaj datę stanu danych (data_as_of) z odpowiedzi narzędzia. Nie zgaduj treści przepisów.",
    ),
)
print(response.text)
```
Alternatywa: zdefiniuj deklaracje funkcji ręcznie z JSON Schema z `ai/openai-actions/INSTRUCTIONS.md` (sekcja 6) lub wygeneruj z `/openapi.json` (obsługiwany jest tylko podzbiór schematu OpenAPI).

## 5. Klient MCP w SDK `google-genai` (eksperymentalne)
README SDK: wbudowana obsługa MCP jest eksperymentalna – SDK przyjmuje lokalnie utworzoną sesję klienta MCP w `config.tools`. Przykłady Google pokazują tylko serwery stdio; połączenie ze zdalnym Streamable HTTP to kombinacja dwóch źródeł, niesprawdzona. Zainstaluj `pip install google-genai "mcp<2"`: przykład używa `streamablehttp_client` z pakietu `mcp` 1.x. W kliencie MCP v2 działa tylko `streamable_http_client`, bez parametrów `headers=`/`timeout=` (nagłówki ustawia się na przekazanym `http_client`), więc bez przypięcia wersji snippet może się wywrócić. Jeśli to potrzebne – użyj punktu 4.

## 6. Google AI Studio (interfejs webowy)
Nie ma potwierdzenia, że da się tam podłączyć nasz serwer MCP. AI Studio służy do uzyskania klucza API (Get API key) dla punktów 3–5. Z pamięci (niezweryfikowane): w AI Studio można ręcznie wkleić deklaracje funkcji w JSON, ale wywołanie naszego API musiałbyś wykonać sam.

## 7. Aplikacja Gemini (gemini.google.com)
Oficjalna pomoc Google (Settings > Connected Apps > Custom apps > Add a custom app) pozwala wpisać adres serwera MCP, ale warunki to: konto osobiste, wiek 18+, lokalizacja w USA, włączone Keep Activity, tylko język angielski. Dla użytkownika z Polski funkcja prawdopodobnie nie jest dostępna. Pomoc opisuje tylko Dynamic Client Registration lub ręczne dane logowania – nie ma oficjalnego potwierdzenia, że serwer bez OAuth zostanie przyjęty. Jeśli masz dostęp, adres to `https://TWOJA-DOMENA.vercel.app/api/mcp` (bez ukośnika na końcu), użycie: `@` w oknie rozmowy. Traktuj to jako eksperyment do sprawdzenia, nie jako obsługiwaną ścieżkę.

## 8. Gems i skills
Zapisane instrukcje (plus pliki referencyjne), bez wywoływania zewnętrznych narzędzi. Możesz wkleić tam `ai/SYSTEM_PROMPT.md`, ale model nie pobierze przepisów z API – bez narzędzi musi powiedzieć wprost, że nie może zweryfikować brzmienia przepisu. Nie buduj na Gems: wsparcie kończy się w listopadzie 2026 dla kont osobistych (migracja do skills).

## 9. Google ADK (Python)
`pip install "google-adk[mcp]"` (Python 3.10+). W produkcji `McpToolset` definiuj synchronicznie w `agent.py`.
```python
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

root_agent = LlmAgent(
    model="gemini-flash-latest",
    name="prawo_pl",
    instruction="Odpowiadasz o polskim prawie wyłącznie na podstawie narzędzi. Zawsze podawaj datę stanu danych (data_as_of). Nie zgaduj treści przepisów.",
    tools=[
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url="https://TWOJA-DOMENA.vercel.app/api/mcp",
                timeout=10,
                sse_read_timeout=300,
            ),
            tool_filter=["search_law", "get_article", "get_act"],
        )
    ],
)
```
Wariant OpenAPI: `OpenAPIToolset(spec_str=<treść /openapi.json>, spec_str_type="json")` – narzędzia powstaną z `operationId` w snake_case (`search_law`, `get_article`, `get_act`). Pole `servers` w `/openapi.json` jest względne (`/`), więc sprawdź, czy narzędzie woła właściwy host; w razie potrzeby ustaw bazowy URL ręcznie.

## 10. Gemini Enterprise (administrator organizacji)
Edycja Business (funkcja pre-GA): business.gemini.google > Settings & help > zespół > Manage team > Connected apps > Add MCP Server > Server URL `https://TWOJA-DOMENA.vercel.app/api/mcp`, nazwa, **No authentication**, lokalizacja konektora i nazwa magazynu danych > Add > włącz połączenie (domyślnie wyłączone). Edycje z konsolą Cloud: Gemini Enterprise > Data stores > Create data store > Custom MCP Server > No authentication; wymagane: zmiana polityki organizacji dla Custom MCP, dodanie `TWOJA-DOMENA.vercel.app` do `allowedEgressFqdns`, rola Discovery Engine Editor, akcje (narzędzia) włączane ręcznie. Tylko Streamable HTTP, certyfikat zaufanego CA, nowy data store (nie da się podłączyć istniejącego).

## Test po podłączeniu
Zapytaj: „Użyj narzędzia prawa i znajdź art. 118 Kodeksu cywilnego. Podaj stan danych.” Poprawna odpowiedź zawiera dosłowne brzmienie artykułu, `display_address`, `source_url` i linię „Stan danych na dzień …”. Brak tej linii oznacza, że instrukcja systemowa nie została zastosowana.
