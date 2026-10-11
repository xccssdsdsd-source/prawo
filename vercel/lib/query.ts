// Budowa zapytań tsquery z przybliżonym polskim stemmingiem (jak rdzen() w prawnik.py).

const STOP_TOKENS = new Set(['art', 'ust', 'pkt']);
const MAX_TOKENS = 12;
const isNum = (t: string) => /^\p{N}+$/u.test(t);

/** Przybliżony rdzeń: >6 znaków ucina 2 litery, >4 ucina 1. */
export function rdzen(t: string): string {
  const chars = [...t.toLowerCase()];
  const n = chars.length;
  if (n > 6) return chars.slice(0, n - 2).join('');
  if (n > 4) return chars.slice(0, n - 1).join('');
  return chars.join('');
}

/** Tokeny: tylko litery/cyfry; 'art'/'ust'/'pkt' (i '§') pomijane; jednoliterowe słowa pomijane. */
export function tokenize(q: string): string[] {
  return q
    .toLowerCase()
    .split(/[^\p{L}\p{N}]+/u)
    .filter(Boolean)
    .filter((t) => !STOP_TOKENS.has(t))
    .filter((t) => isNum(t) || [...t].length > 1)
    .slice(0, MAX_TOKENS);
}

/** Rdzenie (tokeny cyfrowe bez zmian) – używane też do snippetów. */
export function stems(q: string): string[] {
  return tokenize(q).map((t) => (isNum(t) ? t : rdzen(t)));
}

/**
 * Tekst do to_tsquery('simple', unaccent($1)): "rdzen:* & 445".
 * Zawiera wyłącznie litery/cyfry, ':*', '&' i spacje - bezpieczny dla to_tsquery.
 * Zwraca null, gdy nie ma żadnych tokenów.
 */
export function buildTsQuery(q: string): string | null {
  const parts = tokenize(q).map((t) => (isNum(t) ? t : `${rdzen(t)}:*`));
  return parts.length ? parts.join(' & ') : null;
}

export interface ArticleRef {
  /** np. "445", "46[1]", "3a"; null gdy brak odwołania do artykułu */
  article: string | null;
  /** reszta zapytania po usunięciu "art. N" i oznaczeń ust./§/pkt */
  rest: string;
}

const ART_RE =
  /(?<![\p{L}\p{N}])art(?:ykuł|ykule|ykułu)?\.?\s*(\d+[a-z]?)(?:\s*\[(\d+)\]|\^(\d+))?(?![\p{L}\p{N}])/iu;

/** Rozpoznaje "art. 445", "art 46[1]", "artykuł 3a" w zapytaniu. */
export function parseArticleRef(q: string): ArticleRef {
  const m = ART_RE.exec(q);
  if (!m) return { article: null, rest: q.trim() };
  let article = m[1].toLowerCase();
  const sup = m[2] ?? m[3];
  if (sup) article += `[${sup}]`;
  const rest = (q.slice(0, m.index) + ' ' + q.slice(m.index + m[0].length))
    .replace(/(?:§|(?<![\p{L}\p{N}])(?:ust|pkt)\.?)\s*\d+[a-z]?/giu, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  return { article, rest };
}

/** Normalizacja parametru `art` endpointu /api/article; null = niepoprawny. */
export function normalizeArticle(raw: string): string | null {
  let s = raw
    .trim()
    .toLowerCase()
    .replace(/^art(ykuł)?\.?\s*/u, '')
    .replace(/\s+/g, '');
  s = s.replace(/\^(\d+)$/, '[$1]').replace(/\((\d+)\)$/, '[$1]');
  return /^\d+[a-z]{0,2}(\[\d+\])?$/.test(s) ? s : null;
}

/** Odwzorowanie znaków bez diakrytyków, zachowujące długość (indeksy zgodne z oryginałem). */
function fold(s: string): string {
  let out = '';
  for (const ch of s.toLowerCase()) {
    out += ch === 'ł' ? 'l' : ch.normalize('NFD')[0];
  }
  return out;
}

/** Własny snippet: okno wokół pierwszego trafienia któregoś z rdzeni. */
export function makeSnippet(text: string, stemList: string[], max = 320): string {
  const flat = text.replace(/\s+/g, ' ').trim();
  const folded = fold(flat);
  let pos = -1;
  for (const st of stemList) {
    if (isNum(st)) continue;
    const i = folded.indexOf(fold(st));
    if (i >= 0 && (pos < 0 || i < pos)) pos = i;
  }
  if (pos < 0) return flat.length > max ? flat.slice(0, max).trimEnd() + '…' : flat;
  const start = Math.max(0, pos - 60);
  const end = Math.min(flat.length, start + max);
  return (start > 0 ? '…' : '') + flat.slice(start, end).trim() + (end < flat.length ? '…' : '');
}
