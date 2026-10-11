import { describe, it, expect, beforeEach } from 'vitest';
import { rateCheck, clientIp, _resetRateLimit } from '../lib/ratelimit';
import { cacheControl } from '../lib/http';

describe('ratelimit', () => {
  beforeEach(() => _resetRateLimit());
  it('przepuszcza do limitu, potem blokuje', () => {
    for (let i = 0; i < 3; i++) expect(rateCheck('a', 3, 1000).allowed).toBe(true);
    const r = rateCheck('a', 3, 1000);
    expect(r.allowed).toBe(false);
    expect(r.remaining).toBe(0);
    expect(r.retryAfterSec).toBeGreaterThan(0);
  });
  it('osobne liczniki per klucz i reset po oknie', () => {
    rateCheck('a', 1, 0);
    expect(rateCheck('a', 1, 0).allowed).toBe(false);
    expect(rateCheck('b', 1, 0).allowed).toBe(true);
    expect(rateCheck('a', 1, 61_000).allowed).toBe(true);
  });
  it('clientIp', () => {
    expect(clientIp({ 'x-forwarded-for': '1.2.3.4, 5.6.7.8' })).toBe('1.2.3.4');
    expect(clientIp({})).toBe('unknown');
  });
});

describe('cache-control', () => {
  it('tryb otwarty -> publiczny cache, błędy no-store', () => {
    delete process.env.API_KEY;
    expect(cacheControl(300)).toBe('public, s-maxage=300, stale-while-revalidate=86400');
    expect(cacheControl(300, 404)).toBe('no-store');
  });
  it('z kluczem -> private', () => {
    process.env.API_KEY = 'k';
    expect(cacheControl(300)).toBe('private, no-store');
    delete process.env.API_KEY;
  });
});
