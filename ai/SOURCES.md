# SOURCES – skąd pochodzą instrukcje podłączenia i jak je odświeżyć

Instrukcje dla klientów AI (`vercel/public/podlacz.html`, `ai/mcp/README.md`, `ai/openai-actions/INSTRUCTIONS.md`, `ai/gemini/INSTRUCTIONS.md`) opierają się na dokumentacji producentów sprawdzonej **2026-10-11**. Interfejsy tych produktów zmieniają się co kilka tygodni, więc przy poleceniu „Uaktualnij to wszystko” oprócz danych (`python aktualizuj.py`) warto przejść poniższą procedurę.

## Procedura odświeżenia instrukcji (dla Claude Code)
1. Dla każdego wiersza z tabel poniżej otwórz stronę (WebFetch/WebSearch) i porównaj z opisem w `vercel/public/podlacz.html` (tablica `CLIENTS` w skrypcie na dole pliku) oraz w plikach `ai/`.
2. Zmień tylko to, co faktycznie się zmieniło (nazwy menu, pola JSON, limity, daty wygaszania). Nie dopisuj twierdzeń, których nie widzisz na stronie – jeśli strona jest niedostępna (403/404), zostaw wpis z poziomem pewności „częściowo” albo „z pamięci” i napisz to wprost.
3. Zaktualizuj `verified` w odpowiednim wpisie `CLIENTS` (data w formacie `YYYY-MM-DD`) oraz stałą `VERIFIED` na początku skryptu, gdy przeszedłeś wszystkie wpisy.
4. Zaktualizuj tabelę poniżej (kolumna „Ostatnio sprawdzono”).
5. Uruchom `python pipeline/build_data_info.py` (odświeża `data-info.json`, fallback w `index.html` i blok promptu w `podlacz.html` z `ai/SYSTEM_PROMPT.md`).
6. Zwaliduj skrypt: wyciągnij `<script>` z `podlacz.html` i uruchom `node --check`.
7. Gdy zmieniły się nazwy narzędzi MCP, parametry REST lub ścieżki (`vercel/lib/mcp.ts`, `vercel/public/openapi.json`) – popraw wszystkie snippety, prompt i `ai/AGENTS.md`.

## Poziomy pewności używane na stronie
- **zweryfikowane** – opis zgadza się ze stroną dokumentacji odczytaną w dniu weryfikacji;
- **częściowo** – część opisu pochodzi ze źródeł zewnętrznych, streszczeń wyszukiwarki lub z pamięci (strona pokazuje ostrzeżenie „niezweryfikowane w żywej dokumentacji” i wskazuje, czego dotyczy);
- **z pamięci** – brak potwierdzenia w dokumentacji (ostrzeżenie jak wyżej);
- **własny interfejs** – dotyczy tylko naszego API (REST/OpenAPI/llms.txt); nie ma zewnętrznej dokumentacji, sprawdza się to testem połączenia.

## Anthropic / Claude
| Temat | Adres | Ostatnio sprawdzono |
|---|---|---|
| Konektory niestandardowe (claude.ai, Desktop, Team/Enterprise) | https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp | 2026-10-11 |
| Dodawanie konektora spoza katalogu | https://claude.com/docs/connectors/custom/add-unlisted.md | 2026-10-11 |
| Budowa konektorów, limity wyników | https://claude.com/docs/connectors/building.md | 2026-10-11 |
| Uwierzytelnianie konektorów | https://claude.com/docs/connectors/building/authentication.md | 2026-10-11 |
| Claude Code – MCP | https://code.claude.com/docs/en/mcp | 2026-10-11 |
| Claude Agent SDK – MCP | https://code.claude.com/docs/en/agent-sdk/mcp | 2026-10-11 |
| Claude API – konektor MCP | https://platform.claude.com/docs/en/agents-and-tools/mcp-connector | 2026-10-11 |
| Adresy IP Anthropic | https://platform.claude.com/docs/en/api/ip-addresses | 2026-10-11 |
| Skills | https://support.claude.com/en/articles/12512180-use-skills-in-claude oraz https://code.claude.com/docs/en/skills | 2026-10-11 |
| Projekty | https://support.claude.com/en/articles/9519177-how-can-i-create-and-manage-projects | 2026-10-11 (częściowo) |
| MCP – łączenie ze zdalnymi serwerami | https://modelcontextprotocol.io/docs/develop/connect-remote-servers | 2026-10-11 |

## Google / Gemini
| Temat | Adres | Ostatnio sprawdzono |
|---|---|---|
| Gemini CLI – serwery MCP | https://geminicli.com/docs/tools/mcp-server/ | 2026-10-11 |
| Gemini CLI – instalacja i logowanie | https://geminicli.com/docs/get-started/installation/ oraz https://geminicli.com/docs/get-started/authentication/ | 2026-10-11 |
| Przejście Gemini CLI -> Antigravity CLI | https://developers.googleblog.com/en/an-important-update-transitioning-gemini-cli-to-antigravity-cli/ | 2026-10-11 |
| Antigravity – MCP | https://antigravity.google/docs/mcp oraz https://antigravity.google/docs/mcp?tab=cli | 2026-10-11 |
| Antigravity – start i migracja | https://antigravity.google/docs/getting-started?tab=cli oraz https://antigravity.google/docs/cli/gcli-migration | 2026-10-11 |
| Gemini API – function calling i zdalny MCP | https://ai.google.dev/gemini-api/docs/function-calling | 2026-10-11 |
| Gemini API – Interactions (sekcja Limitations!) | https://ai.google.dev/gemini-api/docs/interactions | 2026-10-11 |
| Gemini API – changelog | https://ai.google.dev/gemini-api/docs/changelog | 2026-10-11 |
| SDK google-genai (Python) | https://github.com/googleapis/python-genai | 2026-10-11 |
| SDK js-genai | https://github.com/googleapis/js-genai | 2026-10-11 |
| Aplikacja Gemini – własne aplikacje (Custom apps) | https://support.google.com/gemini/answer/17209137 | 2026-10-11 (warunek: USA, tylko angielski) |
| Gems / skills | https://gemini.google/overview/gems/ oraz https://blog.google/products-and-platforms/products/gemini/automate-tasks-with-skills/ | 2026-10-11 |
| Gemini Enterprise – Business | https://support.google.com/g/answer/17106276 | 2026-10-11 |
| Gemini Enterprise – konsola Cloud | https://docs.cloud.google.com/gemini/enterprise/docs/connectors/custom-mcp-server/set-up-custom-mcp-server | 2026-10-11 |
| Google ADK – MCP i OpenAPI | https://adk.dev/tools-custom/mcp-tools/ oraz https://adk.dev/tools-custom/openapi-tools/ | 2026-10-11 |

## OpenAI / ChatGPT
| Temat | Adres | Ostatnio sprawdzono |
|---|---|---|
| Własny serwer MCP w ChatGPT | https://developers.openai.com/api/docs/guides/custom-mcp-server | 2026-10-11 |
| Podłączanie do ChatGPT | https://developers.openai.com/apps-sdk/deploy/connect-chatgpt | 2026-10-11 |
| Responses API – narzędzie MCP | https://developers.openai.com/api/docs/guides/tools-connectors-mcp | 2026-10-11 |
| Responses API – referencja | https://developers.openai.com/api/reference/resources/responses/methods/create | 2026-10-11 |
| Function calling | https://developers.openai.com/api/docs/guides/function-calling | 2026-10-11 |
| GPT Actions | https://developers.openai.com/api/docs/actions/getting-started oraz .../actions/production oraz .../actions/authentication | 2026-10-11 |
| Wygaszanie Custom GPT (relacja prasowa; sprawdź help.openai.com) | https://virtualizationreview.com/articles/2026/09/28/openai-to-retire-custom-gpts-replace-them-with-plugins.aspx | 2026-10-11 (źródło wtórne) |
| Agents SDK (Python / JS) | https://openai.github.io/openai-agents-python/mcp/ oraz https://openai.github.io/openai-agents-js/guides/mcp/ | 2026-10-11 (częściowo) |
| Codex – MCP | https://learn.chatgpt.com/docs/extend/mcp?surface=cli (przekierowanie z developers.openai.com/codex/mcp) | 2026-10-11 |
| Lista modeli (dla `MODEL_ID`) | https://developers.openai.com/api/docs/models | do sprawdzenia przy każdej aktualizacji |

## Edytory i inne aplikacje
| Klient | Adres | Ostatnio sprawdzono |
|---|---|---|
| Cursor | https://cursor.com/docs/context/mcp | 2026-10-11 |
| VS Code | https://code.visualstudio.com/docs/copilot/customization/mcp-servers | 2026-10-11 (częściowo) |
| Windsurf (docs przeniesione na Devin) | https://docs.devin.ai/desktop/cascade/mcp | 2026-10-11 |
| Zed | https://zed.dev/docs/ai/mcp | 2026-10-11 (częściowo) |
| Cline | https://docs.cline.bot/mcp/configuring-mcp-servers | 2026-10-11 |
| LM Studio | https://lmstudio.ai/docs/app/mcp | 2026-10-11 |
| Raycast | https://manual.raycast.com/ai/model-context-protocol | 2026-10-11 (częściowo) |
| Perplexity (Help Center zwraca 403) | https://docs.perplexity.ai/docs/agent-api/tools/mcp | 2026-10-11 (częściowo) |
| Mistral Le Chat | https://docs.mistral.ai/le-chat/knowledge-integrations/connectors/mcp-connectors | 2026-10-11 (częściowo) |
| Microsoft Copilot Studio | https://learn.microsoft.com/en-us/microsoft-copilot-studio/mcp-add-existing-server-to-agent | 2026-10-11 |
| Open WebUI | https://docs.openwebui.com/features/extensibility/mcp | 2026-10-11 |

## Pliki naszego serwera, z którymi muszą być zgodne snippety
- `vercel/lib/mcp.ts` – nazwy narzędzi (`search_law`, `get_article`, `get_act`) i argumentów (w MCP fraza to `query`), wersja protokołu, instrukcje serwera;
- `vercel/public/openapi.json` – `operationId` (`searchLaw`, `getArticle`, `getAct`), parametry REST (`q`, `id`, `art`), pole `servers`;
- `vercel/public/llms.txt`, `vercel/public/data-info.json`.
