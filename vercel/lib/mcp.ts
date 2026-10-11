// Logika serwera MCP (JSON-RPC 2.0, Streamable HTTP, bezstanowo). Dane przez Deps (lib/law.ts),
// co pozwala testować bez bazy.

export const PROTOCOL_VERSION = '2025-03-26';
export const SERVER_INFO = { name: 'prawo-pl', version: '1.0.0' };
const MAX_TEXT = 12000;

export interface Deps {
  searchLaw: (o: { q: string; kategoria?: string; act?: string; limit: number }) => Promise<any>;
  getArticle: (o: { id?: string; art?: string; variant?: string }) => Promise<any>;
  getAct: (o: { id?: string; variant?: string; include_toc?: boolean }) => Promise<any>;
  /** Data stanu danych (YYYY-MM-DD) – dopisywana do każdej odpowiedzi narzędzia. */
  dataAsOf?: string | null;
}

const KATEGORIE = ['ujednolicone', 'jednolite', 'podstawowe', 'zmieniajace', 'mp', 'orzeczenie', 'umowa', 'inne', 'wyrok', 'ue'];

export const TOOLS = [
  {
    name: 'search_law',
    description:
      'Full-text search of Polish law (Dz.U. and M.P. acts, consolidated texts preferred). Returns ranked fragments with citation data (display_address, article, kategoria, source_url, warnings). ' +
      'Use it to find which act/article covers a topic; then verify the exact wording with get_article. Polish keywords work best (e.g. "zadośćuczynienie krzywda"). No result does not mean no rule exists. ' +
      '| Wyszukiwanie pełnotekstowe w prawie polskim (Dz.U., M.P.; preferowane teksty ujednolicone). Zwraca fragmenty z danymi do cytowania. Użyj do znalezienia właściwego aktu/artykułu, potem zweryfikuj brzmienie przez get_article. Brak wyniku nie oznacza braku przepisu.',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Search phrase in Polish / Fraza do wyszukania, po polsku.' },
        kategoria: { type: 'string', enum: KATEGORIE, description: 'Optional category filter. Default excludes orzeczenie, umowa, inne. / Opcjonalny filtr kategorii.' },
        act: { type: 'string', description: 'Optional ELI to restrict search to one act, e.g. "DU/1964/93". / Opcjonalnie ELI aktu.' },
        limit: { type: 'integer', minimum: 1, maximum: 20, default: 8, description: 'Number of results (1-20, default 8). / Liczba wyników.' },
      },
      required: ['query'],
      additionalProperties: false,
    },
  },
  {
    name: 'get_article',
    description:
      'Fetch the exact text of one article of an act. id is the ELI (e.g. "DU/1964/93") or doc_id ("DU/1964/93#U" = consolidated text). Without variant it prefers the consolidated text (#U), then the original. Never invent article numbers; verify them here. Text is truncated at 12000 chars (truncated=true). ' +
      '| Pobiera dokładną treść jednego artykułu aktu. id to ELI lub doc_id (#U = tekst ujednolicony). Bez variant preferowany tekst ujednolicony. Nie zgaduj numerów artykułów – zweryfikuj tutaj. Cytuj: display_address, art., kategoria, source_url.',
    inputSchema: {
      type: 'object',
      properties: {
        id: { type: 'string', description: 'ELI or doc_id, e.g. "DU/1964/93" or "DU/1964/93#U".' },
        art: { type: 'string', description: 'Article number, e.g. "445" or "46[1]" (also accepts "art. 46¹"). / Numer artykułu.' },
        variant: { type: 'string', enum: ['U'], description: '"U" forces the consolidated text. / "U" wymusza tekst ujednolicony.' },
      },
      required: ['id', 'art'],
      additionalProperties: false,
    },
  },
  {
    name: 'get_act',
    description:
      'Metadata of an act (title, display_address, kategoria, status, source_url, warnings), optionally with a table of contents (list of articles with headings). ' +
      '| Metadane aktu (tytuł, adres publikacyjny, kategoria, status, źródło, ostrzeżenia), opcjonalnie spis artykułów z nagłówkami (include_toc).',
    inputSchema: {
      type: 'object',
      properties: {
        id: { type: 'string', description: 'ELI or doc_id.' },
        variant: { type: 'string', enum: ['U'], description: '"U" forces the consolidated text.' },
        include_toc: { type: 'boolean', default: false, description: 'Include list of articles with headings. / Dołącz spis artykułów.' },
      },
      required: ['id'],
      additionalProperties: false,
    },
  },
];

class ToolError extends Error {}

/** Błędy walidacji/„nie znaleziono” z lib/law.ts (ApiError ze statusem 4xx) pokazujemy modelowi jako błąd narzędzia. */
function toToolError(e: any): never {
  const status = Number(e?.status);
  if (status >= 400 && status < 500) throw new ToolError(String(e.message));
  throw e;
}

function cite(r: any): string {
  const parts = [r.display_address || r.doc_id, r.article ? `art. ${r.article}` : null, r.kategoria ? `kategoria: ${r.kategoria}` : null];
  return parts.filter(Boolean).join(', ');
}
function warnText(w?: string[]) {
  return w && w.length ? '\nOstrzeżenia: ' + w.join(' | ') : '';
}

async function searchLaw(deps: Deps, a: any) {
  const query = String(a?.query ?? '').trim();
  if (!query) throw new ToolError('Parameter "query" is required.');
  const limit = Math.min(20, Math.max(1, Math.trunc(Number(a.limit ?? 8)) || 8));
  let data: any;
  try {
    data = await deps.searchLaw({ q: query, kategoria: a.kategoria ?? undefined, act: a.act ? String(a.act) : undefined, limit });
  } catch (e) { toToolError(e); }
  const results = data.results;
  const text = results.length
    ? `Wyniki dla "${query}" (${results.length}):\n\n` +
      results.map((r: any, i: number) =>
        `${i + 1}. ${r.title}\n   ${cite(r)}${r.heading ? '\n   Dział: ' + r.heading : ''}\n   ${String(r.snippet ?? '').replace(/\s+/g, ' ')}\n   doc_id: ${r.doc_id}\n   źródło: ${r.source_url}${warnText(r.warnings)}`).join('\n\n') +
      '\n\nUwaga: zweryfikuj brzmienie przez get_article; to nie jest porada prawna, sprawdź aktualność w ISAP.'
    : `Brak wyników dla "${query}". Brak wyniku nie oznacza braku przepisu – spróbuj innych słów lub filtra kategoria.`;
  return { text, data };
}

async function getArticle(deps: Deps, a: any) {
  let data: any;
  try {
    data = await deps.getArticle({ id: a?.id, art: a?.art, variant: a?.variant });
  } catch (e) { toToolError(e); }
  const out = `${data.title}\n${cite(data)}${data.heading ? '\nDział: ' + data.heading : ''}\n\n${data.text}${data.truncated ? '\n\n[tekst obcięty do 12000 znaków]' : ''}\n\nŹródło: ${data.source_url}${warnText(data.warnings)}`;
  return { text: out, data };
}

async function getAct(deps: Deps, a: any) {
  const toc = a?.include_toc === true || a?.include_toc === 1 || a?.include_toc === '1' || a?.include_toc === 'true';
  let data: any;
  try {
    data = await deps.getAct({ id: a?.id, variant: a?.variant, include_toc: toc });
  } catch (e) { toToolError(e); }
  let tocText = '';
  if (data.articles) {
    tocText = '\n\nSpis artykułów:\n' + data.articles.map((r: any) => `art. ${r.article}${r.heading ? ' – ' + r.heading : ''}`).join('\n');
  }
  const text = `${data.title}\n${cite(data)}\nstatus: ${data.status ?? 'n/d'}, data ogłoszenia: ${data.announcement_date ?? 'n/d'}\nŹródło: ${data.source_url}${warnText(data.warnings)}${tocText}`;
  return { text, data };
}

async function callTool(deps: Deps, name: string, args: any) {
  try {
    let r;
    if (name === 'search_law') r = await searchLaw(deps, args || {});
    else if (name === 'get_article') r = await getArticle(deps, args || {});
    else if (name === 'get_act') r = await getAct(deps, args || {});
    else return { __rpcError: { code: -32602, message: `Unknown tool: ${name}` } };
    const asOf = deps.dataAsOf ?? null;
    const stan = asOf ? `

Stan danych na dzień ${asOf.split('-').reverse().join('.')} – przepisy ogłoszone później nie są uwzględnione; teksty ujednolicone mogą być starsze. Zweryfikuj w ISAP.` : '';
    return { content: [{ type: 'text', text: r.text + stan }], structuredContent: { ...r.data, data_as_of: asOf } };
  } catch (e: any) {
    const msg = e instanceof ToolError ? e.message : 'Internal tool error: ' + (e?.message || String(e));
    return { content: [{ type: 'text', text: msg }], structuredContent: { error: { code: e instanceof ToolError ? 'bad_request' : 'internal', message: msg } }, isError: true };
  }
}

const rpcErr = (id: any, code: number, message: string) => ({ jsonrpc: '2.0', id: id ?? null, error: { code, message } });

/** Obsługa pojedynczej wiadomości JSON-RPC. Zwraca null dla notyfikacji. */
export async function handleMessage(deps: Deps, msg: any): Promise<any | null> {
  if (!msg || typeof msg !== 'object' || msg.jsonrpc !== '2.0' || typeof msg.method !== 'string') {
    if (msg && typeof msg === 'object' && ('result' in msg || 'error' in msg)) return null; // odpowiedź klienta
    return rpcErr(msg?.id, -32600, 'Invalid Request');
  }
  const isNotification = msg.id === undefined || msg.id === null;
  const id = msg.id;
  switch (msg.method) {
    case 'initialize':
      return { jsonrpc: '2.0', id, result: {
        protocolVersion: PROTOCOL_VERSION, capabilities: { tools: { listChanged: false } }, serverInfo: SERVER_INFO,
        instructions: 'Polish law lookup. Always cite display_address, article, kategoria and source_url. Prefer consolidated texts, verify article numbers with get_article, not legal advice (verify in ISAP). | Zawsze cytuj adres publikacyjny, artykuł, kategorię i źródło; nie wymyślaj numerów artykułów.' } };
    case 'ping':
      return isNotification ? null : { jsonrpc: '2.0', id, result: {} };
    case 'tools/list':
      return { jsonrpc: '2.0', id, result: { tools: TOOLS } };
    case 'tools/call': {
      const p = msg.params;
      if (!p || typeof p.name !== 'string') return rpcErr(id, -32602, 'Invalid params: name required');
      const r: any = await callTool(deps, p.name, p.arguments);
      if (r.__rpcError) return rpcErr(id, r.__rpcError.code, r.__rpcError.message);
      return { jsonrpc: '2.0', id, result: r };
    }
    default:
      if (isNotification || msg.method.startsWith('notifications/')) return null;
      return rpcErr(id, -32601, `Method not found: ${msg.method}`);
  }
}

export interface HttpResult { status: number; headers: Record<string, string>; body?: string }
const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization, x-api-key, Mcp-Session-Id, MCP-Protocol-Version, Accept',
  'Access-Control-Expose-Headers': 'Mcp-Session-Id',
};

/** Przetwarza żądanie HTTP (metoda, body już sparsowane lub tekst). Auth sprawdza wywołujący. */
export async function handleHttp(deps: Deps, method: string, body: any): Promise<HttpResult> {
  const json = { 'Content-Type': 'application/json; charset=utf-8', ...CORS };
  if (method === 'OPTIONS') return { status: 204, headers: { ...CORS } };
  if (method === 'GET' || method === 'DELETE') return { status: 405, headers: { ...CORS, Allow: 'POST, OPTIONS' }, body: JSON.stringify(rpcErr(null, -32000, 'Method not allowed: use POST')) };
  if (method !== 'POST') return { status: 405, headers: { ...CORS, Allow: 'POST, OPTIONS' } };
  if (typeof body === 'string') {
    try { body = JSON.parse(body); } catch { return { status: 400, headers: json, body: JSON.stringify(rpcErr(null, -32700, 'Parse error')) }; }
  }
  if (body === undefined || body === null) return { status: 400, headers: json, body: JSON.stringify(rpcErr(null, -32700, 'Parse error')) };
  if (Array.isArray(body)) {
    if (!body.length) return { status: 400, headers: json, body: JSON.stringify(rpcErr(null, -32600, 'Invalid Request')) };
    const out = (await Promise.all(body.map((m) => handleMessage(deps, m)))).filter((x) => x !== null);
    return out.length ? { status: 200, headers: json, body: JSON.stringify(out) } : { status: 202, headers: { ...CORS } };
  }
  const res = await handleMessage(deps, body);
  return res === null ? { status: 202, headers: { ...CORS } } : { status: 200, headers: json, body: JSON.stringify(res) };
}
