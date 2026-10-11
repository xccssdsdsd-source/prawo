import { describe, it, expect } from 'vitest';
import { handleMessage, handleHttp, TOOLS, type Deps } from './mcp';

const hit = {
  doc_id: 'DU/1964/93#U', eli: 'DU/1964/93', title: 'Kodeks cywilny', display_address: 'Dz.U. 1964 nr 16 poz. 93',
  kategoria: 'ujednolicone', is_consolidated: true, article: '445', heading: 'H', snippet: 'frag', score: 0.5,
  source_url: 'https://x/y.pdf', warnings: ['uwaga'],
};

class FakeApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

function mk(): Deps {
  return {
    searchLaw: async ({ q }) => ({ query: q, count: 1, results: [hit] }),
    getArticle: async ({ id, art }) => {
      if (id === 'NOPE') throw new FakeApiError(404, 'Nie znaleziono aktu o podanym identyfikatorze.');
      if (art !== '445') throw new FakeApiError(404, `Nie znaleziono art. ${art}.`);
      return { doc_id: 'DU/1964/93#U', title: 'Kodeks cywilny', display_address: hit.display_address, article: '445', heading: 'H', text: 'Art. 445. treść', source_url: hit.source_url, warnings: ['uwaga'], truncated: false };
    },
    getAct: async ({ include_toc }) => ({
      doc_id: 'DU/1964/93#U', title: 'Kodeks cywilny', display_address: hit.display_address, kategoria: 'ujednolicone', status: 'obowiązujący',
      source_url: hit.source_url, warnings: [], ...(include_toc ? { articles: [{ article: '1', heading: 'A' }, { article: '2', heading: null }] } : {}),
    }),
  };
}
const call = (name: string, args: any, deps = mk()) => handleMessage(deps, { jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name, arguments: args } });

describe('MCP JSON-RPC', () => {
  it('initialize', async () => {
    const r = await handleMessage(mk(), { jsonrpc: '2.0', id: 1, method: 'initialize', params: {} });
    expect(r.result.protocolVersion).toBe('2025-03-26');
    expect(r.result.capabilities.tools).toBeDefined();
  });
  it('notification -> 202', async () => {
    const r = await handleHttp(mk(), 'POST', { jsonrpc: '2.0', method: 'notifications/initialized' });
    expect(r.status).toBe(202);
  });
  it('ping i tools/list', async () => {
    expect((await handleMessage(mk(), { jsonrpc: '2.0', id: 2, method: 'ping' })).result).toEqual({});
    const l = await handleMessage(mk(), { jsonrpc: '2.0', id: 3, method: 'tools/list' });
    expect(l.result.tools.map((t: any) => t.name)).toEqual(['search_law', 'get_article', 'get_act']);
    expect(TOOLS[1].inputSchema.required).toEqual(['id', 'art']);
  });
  it('nieznana metoda', async () => {
    expect((await handleMessage(mk(), { jsonrpc: '2.0', id: 4, method: 'foo' })).error.code).toBe(-32601);
  });
  it('search_law', async () => {
    const r = await call('search_law', { query: 'szkoda' });
    expect(r.result.isError).toBeUndefined();
    expect(r.result.structuredContent.count).toBe(1);
    expect(r.result.content[0].text).toContain('Dz.U. 1964 nr 16 poz. 93');
    expect(r.result.content[0].text).toContain('art. 445');
  });
  it('search_law bez query -> isError', async () => {
    expect((await call('search_law', {})).result.isError).toBe(true);
  });
  it('search_law: błąd walidacji z API -> isError, błąd nieoczekiwany też', async () => {
    const bad = { ...mk(), searchLaw: async () => { throw new FakeApiError(400, 'Nieznana kategoria.'); } };
    const r = await call('search_law', { query: 'x', kategoria: 'zzz' }, bad);
    expect(r.result.isError).toBe(true);
    expect(r.result.content[0].text).toContain('Nieznana kategoria');
    const boom = { ...mk(), searchLaw: async () => { throw new Error('db down'); } };
    expect((await call('search_law', { query: 'x' }, boom)).result.isError).toBe(true);
  });
  it('dopisuje stan danych do tekstu i structuredContent', async () => {
    const r = await call('search_law', { query: 'szkoda' }, { ...mk(), dataAsOf: '2026-10-11' });
    expect(r.result.structuredContent.data_as_of).toBe('2026-10-11');
    expect(r.result.content[0].text).toContain('Stan danych na dzień 11.10.2026');
  });
  it('get_article', async () => {
    const r = await call('get_article', { id: 'DU/1964/93', art: '445' });
    expect(r.result.structuredContent.doc_id).toBe('DU/1964/93#U');
    expect(r.result.structuredContent.warnings).toEqual(['uwaga']);
    expect(r.result.content[0].text).toContain('https://x/y.pdf');
  });
  it('get_article nieistniejący -> isError', async () => {
    expect((await call('get_article', { id: 'DU/1964/93', art: '9999' })).result.isError).toBe(true);
    expect((await call('get_article', { id: 'NOPE', art: '1' })).result.isError).toBe(true);
  });
  it('get_act z toc', async () => {
    const r = await call('get_act', { id: 'DU/1964/93', include_toc: true });
    expect(r.result.structuredContent.articles).toHaveLength(2);
    expect(r.result.content[0].text).toContain('art. 1 – A');
  });
  it('nieznane narzędzie -> błąd JSON-RPC', async () => {
    expect((await call('zzz', {})).error.code).toBe(-32602);
  });
  it('HTTP: GET 405 z Allow, OPTIONS 204, zły JSON 400', async () => {
    const g = await handleHttp(mk(), 'GET', undefined);
    expect(g.status).toBe(405);
    expect(g.headers.Allow).toContain('POST');
    expect((await handleHttp(mk(), 'OPTIONS', undefined)).status).toBe(204);
    expect((await handleHttp(mk(), 'POST', '{bad')).status).toBe(400);
  });
  it('batch', async () => {
    const r = await handleHttp(mk(), 'POST', [{ jsonrpc: '2.0', id: 1, method: 'ping' }, { jsonrpc: '2.0', method: 'notifications/initialized' }]);
    expect(JSON.parse(r.body!)).toHaveLength(1);
  });
});
