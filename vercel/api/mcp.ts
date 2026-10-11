import type { VercelRequest, VercelResponse } from '@vercel/node';
import { checkAuth } from '../lib/auth';
import { searchLaw, getArticle, getAct } from '../lib/law';
import { handleHttp } from '../lib/mcp';
import { applyRateLimit } from '../lib/ratelimit';

const deps = { searchLaw, getArticle, getAct } as any;

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
  if (method !== 'OPTIONS' && !applyRateLimit(req, res, 'mcp', 120)) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.status(429).json({ jsonrpc: '2.0', id: null, error: { code: -32029, message: 'Rate limit exceeded' } });
    return;
  }
  try {
    const r = await handleHttp(deps, method, req.body);
    set(r.headers);
    res.status(r.status);
    r.body === undefined ? res.end() : res.send(r.body);
  } catch (e: any) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.status(500).json({ jsonrpc: '2.0', id: null, error: { code: -32603, message: 'Internal error' } });
  }
}
