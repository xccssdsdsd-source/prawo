import type { VercelRequest, VercelResponse } from '@vercel/node';
import { isAuthorized, isKeyRequired } from './auth';
import { applyRateLimit } from './ratelimit';
import { dataAsOf } from './datainfo';

export const VERSION = '1.0.0';
export const MAX_Q_LEN = 300;

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

export function setCors(res: VercelResponse): void {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Authorization, Content-Type, x-api-key, Mcp-Session-Id, Accept');
}

export function sendError(res: VercelResponse, status: number, code: string, message: string): void {
  setCors(res);
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store');
  if (dataAsOf) res.setHeader('X-Data-As-Of', dataAsOf);
  res.status(status).send(JSON.stringify({ error: { code, message } }));
}

/** Tryb otwarty -> publiczny cache CDN; z kluczem -> private, no-store; błędy/brak TTL -> no-store. */
export function cacheControl(sMaxAge: number | undefined, status = 200): string {
  if (isKeyRequired()) return 'private, no-store';
  if (!sMaxAge || status !== 200) return 'no-store';
  return `public, s-maxage=${sMaxAge}, stale-while-revalidate=86400`;
}

export function sendJson(res: VercelResponse, body: unknown, status = 200, sMaxAge?: number): void {
  setCors(res);
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', cacheControl(sMaxAge, status));
  if (dataAsOf) res.setHeader('X-Data-As-Of', dataAsOf);
  res.status(status).send(JSON.stringify(body));
}

/** Pojedyncza wartość parametru query (pierwsza, jeśli powtórzony). */
export function param(req: VercelRequest, name: string): string | undefined {
  const v = req.query[name];
  const s = Array.isArray(v) ? v[0] : v;
  return s === undefined || s === '' ? undefined : s;
}

/** limit 1-20 (domyślnie 8); niepoprawny -> 400, poza zakresem -> przycięcie. */
export function parseLimit(raw: string | undefined, def = 8, min = 1, max = 20): number {
  if (raw === undefined) return def;
  if (!/^-?\d+$/.test(raw)) throw new ApiError(400, 'bad_request', 'Parametr limit musi być liczbą całkowitą 1-20.');
  return Math.min(max, Math.max(min, parseInt(raw, 10)));
}

/** Wspólna obudowa endpointów: CORS, OPTIONS, tylko GET/HEAD, auth, błędy JSON. */
export function route(opts: { auth: boolean; scope: string; rateLimit: number; sMaxAge: number }, fn: (req: VercelRequest) => Promise<unknown>) {
  return async (req: VercelRequest, res: VercelResponse): Promise<void> => {
    try {
      setCors(res);
      if (req.method === 'OPTIONS') {
        res.status(204).end();
        return;
      }
      if (req.method !== 'GET' && req.method !== 'HEAD') {
        res.setHeader('Allow', 'GET, OPTIONS');
        throw new ApiError(405, 'method_not_allowed', 'Dozwolona metoda: GET.');
      }
      if (opts.auth && !isAuthorized(req.headers)) {
        res.setHeader('WWW-Authenticate', 'Bearer');
        throw new ApiError(
          401,
          'unauthorized',
          'Brak lub niepoprawny klucz API (Authorization: Bearer <klucz> lub x-api-key).',
        );
      }
      if (!applyRateLimit(req, res, opts.scope, opts.rateLimit)) {
        throw new ApiError(429, 'rate_limited', 'Zbyt wiele żądań. Spróbuj ponownie po czasie z nagłówka Retry-After.');
      }
      sendJson(res, await fn(req), 200, opts.sMaxAge);
    } catch (e) {
      if (e instanceof ApiError) return sendError(res, e.status, e.code, e.message);
      console.error(e);
      sendError(res, 500, 'internal_error', 'Błąd wewnętrzny serwera.');
    }
  };
}
