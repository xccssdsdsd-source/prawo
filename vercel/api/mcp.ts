import type { VercelRequest, VercelResponse } from '@vercel/node';
import { checkAuth } from '../lib/auth';
import { searchLaw, getArticle, getAct } from '../lib/law';
import { dataAsOf } from '../lib/datainfo';
import { handleHttp } from '../lib/mcp';
import { applyRateLimit } from '../lib/ratelimit';

// Konektory claude.ai / ChatGPT / Gemini wołają serwer z chmury dostawcy (wspólne adresy IP wielu użytkowników),
// więc limit per IP musi być hojny; właściwą ochronę przed nadużyciami daje Vercel Firewall (patrz docs/DEPLOY.md).
const MCP_RATE_LIMIT = Math.max(1, Number(process.env.MCP_RATE_LIMIT) || 600);

const deps = { searchLaw, getArticle, getAct, dataAsOf } as any;

export default async function handler(req: VercelRequest, res: VercelResponse) {
  const method = (req.method || 'GET').toUpperCase();
  const set = (h: Record<string, string>) => Object.entries(h).forEach(([k, v]) => res.setHeader(k, v));
  if (method !== 'OPTIONS') {
    let ok = false;
    try { ok = !!(await (checkAuth as any)(req)); } catch { ok = false; }
    if (!ok) {
      res.setHeader('Access-Control-Allow-Origin', '*');
      res.setHeader('WWW-Authenticate', 'Bearer');
      res.status(401).json({ jsonrpc: '2.0', id: null, error: { code: -32001, message: 'Unauthorized: missing or invalid API key' } });
      return;
    }
  }
  if (method !== 'OPTIONS' && !applyRateLimit(req, res, 'mcp', MCP_RATE_LIMIT)) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.status(429).json({ jsonrpc: '2.0', id: null, error: { code: -32029, message: 'Rate limit exceeded' } });
    return;
  }
  try {
    let body: unknown = req.body;
    if (Buffer.isBuffer(body)) body = body.toString('utf8'); // inny Content-Type niż application/json
    const r = await handleHttp(deps, method, body);
    set(r.headers);
    res.status(r.status);
    r.body === undefined ? res.end() : res.send(r.body);
  } catch (e: any) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.status(500).json({ jsonrpc: '2.0', id: null, error: { code: -32603, message: 'Internal error' } });
  }
}
