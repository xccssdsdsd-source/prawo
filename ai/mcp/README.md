# Serwer MCP – podłączenie

Pełna, klikalna instrukcja z przyciskami „Kopiuj” i testem połączenia: **`/podlacz.html`** na Twoim wdrożeniu. Ten plik to skrót tekstowy, spójny z tą stroną. Stan dokumentacji klientów sprawdzono 2026-10-11; interfejsy zmieniają się szybko (procedura odświeżania: `ai/SOURCES.md`).

Endpoint: `https://TWOJA-DOMENA.vercel.app/api/mcp` (Streamable HTTP, JSON-RPC 2.0, bezstanowy, bez OAuth). Obsługuje tylko POST – otwarcie adresu w przeglądarce (GET) zwraca 405, to normalne. Narzędzia: `search_law` (argument `query`), `get_article`, `get_act`. Serwer jest publiczny i otwarty – klucz jest opcjonalny. Nagłówek `Authorization: Bearer KLUCZ` (Twój `API_KEY`) jest potrzebny tylko, gdy właściciel wdrożenia włączył tryb zamknięty; w przykładach poniżej pomiń go, jeśli API jest otwarte.

**Zasada dla modeli:** w każdej odpowiedzi opartej na narzędziach podaj „Stan danych na dzień <data_as_of>” i ostrzeż, że przepisy ogłoszone po tej dacie nie są uwzględnione, a teksty ujednolicone mogą być starsze (zob. `ai/AGENTS.md`).

Szybki test z linii poleceń:
```bash
curl -s https://TWOJA-DOMENA.vercel.app/api/mcp \
  -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

## Co działa gdzie (stan: 2026-10-11)
| Klient | Jak | Pewność instrukcji |
|---|---|---|
| claude.ai, Claude Desktop | konektor niestandardowy (Customize > Connectors), uwierzytelnianie „No sign in” | zweryfikowane |
| Claude Code | `claude mcp add --transport http` | zweryfikowane |
| Claude Agent SDK, Claude API | `mcpServers` typu `http` / `mcp_servers` + `mcp_toolset` | zweryfikowane |
| ChatGPT | wtyczka z własnym serwerem MCP (chatgpt.com/plugins), „No authentication” | częściowo (plany i etykiety menu niepotwierdzone) |
| OpenAI Responses API, Codex CLI | narzędzie `mcp` / `config.toml` | zweryfikowane |
| Cursor, Windsurf, Cline, LM Studio, Open WebUI, Copilot Studio | plik JSON lub formularz | zweryfikowane |
| VS Code, Zed, Raycast, Perplexity, Mistral Le Chat | plik JSON lub formularz | częściowo |
| Gemini CLI, Antigravity, Gemini Enterprise | plik JSON / panel admina | zweryfikowane (Gemini w aplikacji i AI Studio: patrz `ai/gemini/INSTRUCTIONS.md`) |

## Claude Code
```bash
claude mcp add --transport http prawo-pl https://TWOJA-DOMENA.vercel.app/api/mcp
# we wszystkich projektach: dodaj --scope user
# tryb zamknięty: dodaj --header "Authorization: Bearer KLUCZ"
claude mcp list
```
Dla zespołu `.mcp.json` w korzeniu projektu (pole `type` jest obowiązkowe):
```json
{ "mcpServers": { "prawo-pl": { "type": "http", "url": "https://TWOJA-DOMENA.vercel.app/api/mcp" } } }
```
Z kluczem bez zapisywania go w repo: `"headers": { "Authorization": "Bearer ${PRAWO_API_KEY}" }` i zmienna środowiskowa `PRAWO_API_KEY` (nie używaj nazw typu `ANTHROPIC_API_KEY`). Narzędzia: `mcp__prawo-pl__search_law`, `mcp__prawo-pl__get_article`, `mcp__prawo-pl__get_act`; regułę zezwalającą `mcp__prawo-pl__*` dodaj w ustawieniach, by uniknąć pytań. Dodatkowo skopiuj `ai/claude-skill/` do `~/.claude/skills/prawo-pl/`.

## claude.ai i Claude Desktop (konektor)
Customize > Connectors (bezpośrednio `https://claude.ai/customize/connectors`) > **+ Add** > **Add custom connector** > nazwa `Prawo PL`, URL `https://TWOJA-DOMENA.vercel.app/api/mcp` > Continue > Authentication: **No sign in** > Add. W rozmowie: **+** > Connectors > włącz. Plan Free: jeden własny konektor. Zespoły i Enterprise: Owner dodaje w Organization settings > Connectors. Ustawień uwierzytelniania nie da się zmienić po dodaniu (usuń i dodaj ponownie). Sekcja „Request headers” (nagłówek `authorization` z wartością `Bearer KLUCZ`) jest w becie i może być niedostępna – jeśli jej nie widzisz, zostaw API otwarte.

Połączenie idzie z chmury Anthropic (zakres `160.79.104.0/21`) – nie blokuj go w Vercel Firewall. Adres kończący się na `/sse` wybiera przestarzały transport; nasz kończy się na `/mcp`.

Claude Desktop – wariant zapasowy (NIEZWERYFIKOWANY w oficjalnej dokumentacji Anthropic; używaj tylko, gdy konektory są niedostępne), `claude_desktop_config.json` (Windows: `%APPDATA%\Claude\`), wymaga Node.js:
```json
{ "mcpServers": { "prawo-pl": {
  "command": "npx",
  "args": ["-y", "mcp-remote", "https://TWOJA-DOMENA.vercel.app/api/mcp", "--transport", "http-only"] } } }
```
Po zmianie całkowicie zamknij i uruchom Claude Desktop.

## Cursor
`~/.cursor/mcp.json` (Windows: `%USERPROFILE%\.cursor\mcp.json`) lub `.cursor/mcp.json` w projekcie:
```json
{ "mcpServers": { "prawo-pl": { "url": "https://TWOJA-DOMENA.vercel.app/api/mcp" } } }
```
Tryb zamknięty: `"headers": { "Authorization": "Bearer ${env:PRAWO_API_KEY}" }`.

## VS Code (GitHub Copilot, tryb Agent)
`.vscode/mcp.json` – klucz główny to `servers`, nie `mcpServers`, i trzeba podać `type`:
```json
{ "servers": { "prawo-pl": { "type": "http", "url": "https://TWOJA-DOMENA.vercel.app/api/mcp" } } }
```
Minimalna wersja VS Code i wymagany plan Copilot: niezweryfikowane.

## Windsurf / Cline / LM Studio / Zed
- Windsurf (Cascade): `mcp_config.json` – klucz `serverUrl` (otwórz plik przyciskiem „Open MCP config file”).
- Cline: wpis MUSI mieć `"type": "streamableHttp"` (bez tego Cline użyje starszego SSE).
- LM Studio (od 0.3.17): Program > Install > Edit mcp.json, ten sam format co Cursor.
- Zed: `settings.json`, klucz `context_servers` z polem `url` (obsługa Streamable HTTP niepotwierdzona w dokumentacji).

## Gemini, ChatGPT, OpenAI API, inne
Zob. `ai/gemini/INSTRUCTIONS.md` (Gemini CLI jest od 18.06.2026 zastąpiony przez Antigravity CLI dla kont indywidualnych; Antigravity używa klucza `serverUrl`) i `ai/openai-actions/INSTRUCTIONS.md`.

## Brak MCP
Użyj REST (`/api/search`, `/api/article`, `/api/act`) – patrz `ai/claude-skill/SKILL.md`, schemat `/openapi.json`, instrukcja dla modeli `/llms.txt`.

## Rozwiązywanie problemów
- „Couldn't reach the MCP server” (claude.ai): adres musi być publiczny, HTTPS i kończyć się na `/api/mcp`; sprawdź, czy wdrożenie nie jest chronione logowaniem Vercel (Deployment Protection) i czy firewall nie blokuje `160.79.104.0/21`.
- 401 – tylko w trybie zamkniętym (zły klucz/nagłówek). 429 – limit żądań, poczekaj `Retry-After`.
- Timeout przy pierwszym wywołaniu – zimny start funkcji, ponów.
- Po zmianie listy narzędzi na serwerze: ChatGPT – „Refresh” w ustawieniach wtyczki i nowa rozmowa; claude.ai – nowe połączenie; Claude Code – `/mcp` > reconnect.
- Klucz trzymaj w sekrecie; nie commituj go do repozytorium.
