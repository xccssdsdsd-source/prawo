// Best-effort limit żądań per IP, w pamięci instancji funkcji.
// UWAGA: to ograniczenie PER-INSTANCJA (każda instancja serverless ma własny licznik, zimny start zeruje stan),
// więc jest tylko buforem przeciw prostym nadużyciom. Docelowo użyj Vercel Firewall / WAF Rate Limiting.
import type { VercelRequest, VercelResponse } from '@vercel/node';

interface Bucket { count: number; reset: number }
const WINDOW_MS = 60_000;
const MAX_BUCKETS = 5000;
const buckets = new Map<string, Bucket>();

export interface RateResult { allowed: boolean; limit: number; remaining: number; resetSec: number; retryAfterSec: number }

export function rateCheck(key: string, limit: number, now = Date.now()): RateResult {
  if (buckets.size > MAX_BUCKETS) {
    for (const [k, b] of buckets) if (b.reset <= now) buckets.delete(k);
    if (buckets.size > MAX_BUCKETS) buckets.clear();
  }
  let b = buckets.get(key);
  if (!b || b.reset <= now) {
    b = { count: 0, reset: now + WINDOW_MS };
    buckets.set(key, b);
  }
  b.count++;
  const resetSec = Math.ceil(b.reset / 1000);
  const retryAfterSec = Math.max(1, Math.ceil((b.reset - now) / 1000));
  return { allowed: b.count <= limit, limit, remaining: Math.max(0, limit - b.count), resetSec, retryAfterSec };
}

export function clientIp(headers: Record<string, string | string[] | undefined>): string {
  const f = headers['x-real-ip'] ?? headers['x-forwarded-for'];
  const v = Array.isArray(f) ? f[0] : f;
  return (v ?? 'unknown').split(',')[0].trim() || 'unknown';
}

/** Ustawia nagłówki X-RateLimit-*; zwraca false (i nagłówek Retry-After), gdy limit przekroczony. */
export function applyRateLimit(req: VercelRequest, res: VercelResponse, scope: string, limit: number): boolean {
  const r = rateCheck(`${scope}:${clientIp(req.headers)}`, limit);
  res.setHeader('X-RateLimit-Limit', String(r.limit));
  res.setHeader('X-RateLimit-Remaining', String(r.remaining));
  res.setHeader('X-RateLimit-Reset', String(r.resetSec));
  if (!r.allowed) res.setHeader('Retry-After', String(r.retryAfterSec));
  return r.allowed;
}

export function _resetRateLimit(): void { buckets.clear(); }
