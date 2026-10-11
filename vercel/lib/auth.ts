import { createHash, timingSafeEqual } from 'node:crypto';

type Headers = Record<string, string | string[] | undefined>;

function first(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

/** Wyciąga klucz z `Authorization: Bearer ...` lub `x-api-key`. */
export function extractKey(headers: Headers): string | null {
  const auth = first(headers['authorization']);
  if (auth) {
    const m = /^Bearer\s+(.+)$/i.exec(auth.trim());
    if (m) return m[1].trim();
  }
  const x = first(headers['x-api-key']);
  return x ? x.trim() : null;
}

/** Porównanie stałoczasowe (przez SHA-256, więc równe długości). */
export function safeEqual(a: string, b: string): boolean {
  const ha = createHash('sha256').update(a).digest();
  const hb = createHash('sha256').update(b).digest();
  return timingSafeEqual(ha, hb);
}

/** true gdy API_KEY jest ustawiony (tryb zamknięty); pusty/brak = tryb otwarty (publiczne API). */
export function isKeyRequired(apiKey: string | undefined = process.env.API_KEY): boolean {
  return !!(apiKey && apiKey.trim());
}

/**
 * Brak API_KEY w env (pusty/niezdefiniowany) = API otwarte, każdy jest autoryzowany.
 * Gdy API_KEY ustawiony: wymagany identyczny klucz (Bearer / x-api-key).
 */
export function isAuthorized(
  headers: Headers,
  apiKey: string | undefined = process.env.API_KEY,
): boolean {
  if (!apiKey || !isKeyRequired(apiKey)) return true;
  const given = extractKey(headers);
  if (!given) return false;
  return safeEqual(given, apiKey);
}

/** Wygodny wrapper na obiekt żądania (VercelRequest / IncomingMessage). */
export function checkAuth(req: { headers: Headers }): boolean {
  return isAuthorized(req.headers);
}
