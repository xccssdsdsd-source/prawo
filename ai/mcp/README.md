# Serwer MCP – podłączenie

Endpoint: `https://TWOJA-DOMENA.vercel.app/api/mcp` (Streamable HTTP, JSON-RPC 2.0).
Narzędzia: `search_law`, `get_article`, `get_act`. Serwer jest publiczny i otwarty – klucz jest opcjonalny. Nagłówek `Authorization: Bearer KLUCZ` (Twój `API_KEY`) jest potrzebny tylko, gdy właściciel wdrożenia włączył tryb zamknięty; w przykładach poniżej pomiń go, jeśli API jest otwarte.

**Zasada dla modeli:** w każdej odpowiedzi opartej na narzędziach podaj „Stan danych na dzień <data_as_of>” i ostrzeż, że przepisy ogłoszone po tej dacie nie są uwzględnione, a teksty ujednolicone mogą być starsze (zob. `ai/AGENTS.md`).

Szybki test:
```bash
curl -s https://TWOJA-DOMENA.vercel.app/api/mcp \
  -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

## Claude Code
```bash
claude mcp add --transport http prawo https://TWOJA-DOMENA.vercel.app/api/mcp
# tryb zamknięty: dodaj --header "Authorization: Bearer KLUCZ"
claude mcp list
```
Opcja `--scope user` udostępnia serwer we wszystkich projektach. Dodatkowo skopiuj `ai/claude-skill/` do `~/.claude/skills/prawo-pl/`.

## Claude Desktop / claude.ai
- claude.ai (plany z custom connectors): Ustawienia > Connectors > Add custom connector > URL serwera. Ponieważ API jest otwarte, connector działa bez klucza. W trybie zamkniętym (klucz w nagłówku), jeśli UI nie pozwala na własny nagłówek, użyj mostu poniżej (Claude Desktop) lub REST.
- Claude Desktop – pomost `mcp-remote` (wymaga Node.js); konfiguracja poniżej dotyczy trybu zamkniętego (dla otwartego usuń `--header` i `env`), plik `claude_desktop_config.json` (Windows: `%APPDATA%\Claude\`):
```json
{
  "mcpServers": {
    "prawo": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://TWOJA-DOMENA.vercel.app/api/mcp",
               "--header", "Authorization:${AUTH}"],
      "env": { "AUTH": "Bearer KLUCZ" }
    }
  }
}
```
(Brak spacji po dwukropku w `--header` – stąd zmienna `AUTH`; to znany obejście dla Windows.) Zrestartuj aplikację.

## Cursor
`~/.cursor/mcp.json` (lub `.cursor/mcp.json` w projekcie):
```json
{ "mcpServers": { "prawo": {
  "url": "https://TWOJA-DOMENA.vercel.app/api/mcp",
  "headers": { "Authorization": "Bearer KLUCZ" } } } }
```

## VS Code / Windsurf / inne
Klient z obsługą "streamable HTTP" i własnych nagłówków: podaj URL + nagłówek Authorization. Klient tylko stdio: użyj `npx -y mcp-remote URL --header "Authorization:..."` jak wyżej.

## Brak MCP
Użyj REST (`/api/search`, `/api/article`, `/api/act`) – patrz `ai/claude-skill/SKILL.md` lub Custom GPT: `ai/openai-actions/INSTRUCTIONS.md`.

## Rozwiązywanie problemów
401 – tylko w trybie zamkniętym (zły klucz/nagłówek). Timeout przy pierwszym wywołaniu – zimny start funkcji, ponów. Jeśli używasz klucza, trzymaj go w sekrecie; nie commituj go do repozytorium.
