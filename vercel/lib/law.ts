// Logika zapytań (wspólna dla REST i MCP). Wszystkie wartości od użytkownika idą przez parametry $n.
import { query } from './db';
import { ApiError, MAX_Q_LEN } from './http';
import { buildTsQuery, makeSnippet, normalizeArticle, parseArticleRef, stems } from './query';
import { warningsFor } from './warnings';
import { dataAsOf } from './datainfo';

export const KATEGORIE = [
  'ujednolicone', 'jednolite', 'podstawowe', 'zmieniajace', 'mp',
  'orzeczenie', 'umowa', 'inne', 'wyrok', 'ue',
] as const;
// Domyślnie pomijane: nie są przepisami krajowymi (wyroki i akty UE tylko przez kategoria=wyrok|ue).
export const DEFAULT_EXCLUDED = ['orzeczenie', 'umowa', 'inne', 'wyrok', 'ue'];
const MAX_ARTICLE_CHARS = 12000;
// ELI/doc_id aktu: DU/1964/93, DU/1964/93#U, MP/2026/977 oraz identyfikatory uśpionych źródeł:
// SAOS/<id> (wyroki) i CELEX/<numer celex> (prawo UE) - bez sufiksu #U.
const ELI_RE = /^(?:[A-Za-z]+\/\d{4}\/\d+(?:#U)?|(?:SAOS|CELEX)\/[A-Za-z0-9._-]+)$/i;

// ---------- SQL (stałe; bez sklejania wartości użytkownika) ----------

/** $1 tsquery-text, $2 limit, $3 eli|null, $4 kategoria|null, $5 text[] wykluczone */
export const SQL_SEARCH = `
with q as (select to_tsquery('simple', f_unaccent($1::text)) as tsq)
select c.id, d.doc_id, d.eli, d.title, d.display_address, d.kategoria, d.is_consolidated, d.status,
       d.source_url, c.article, c.heading, c.text,
       ts_rank_cd(c.tsv, q.tsq) * (case d.kategoria
         when 'ujednolicone' then 1.3 when 'jednolite' then 1.2 when 'podstawowe' then 1.1
         else 1.0 end) as score
from q, chunks c join documents d on d.doc_id = c.doc_id
where c.tsv @@ q.tsq
  and ($3::text is null or d.eli = $3::text)
  and (($4::text is not null and d.kategoria = $4::text)
    or ($4::text is null and d.kategoria <> all($5::text[])))
order by score desc, d.doc_id, c.ord
limit $2::int`;

/** $1 fraza tytułu -> kandydaci aktów (dopasowanie tytułu pg_trgm) */
export const SQL_TITLE_MATCH = `
select doc_id, eli,
       word_similarity(f_unaccent(lower($1::text)), f_unaccent(lower(title))) as sim,
       similarity(f_unaccent(lower($1::text)), f_unaccent(lower(title))) as sim_full,
       case kategoria when 'ujednolicone' then 0 when 'jednolite' then 1 else 2 end as cat_rank
from documents
where kategoria in ('ujednolicone', 'jednolite', 'podstawowe')
  and word_similarity(f_unaccent(lower($1::text)), f_unaccent(lower(title))) >= 0.6
order by sim desc, cat_rank asc, sim_full desc
limit 6`;

/** $1 text[] doc_id, $2 numer artykułu -> dokładny artykuł (pierwszy fragment) */
export const SQL_EXACT_ARTICLE = `
select c.id, d.doc_id, d.eli, d.title, d.display_address, d.kategoria, d.is_consolidated, d.status,
       d.source_url, c.article, c.heading, c.text, c.ord
from documents d join chunks c on c.doc_id = d.doc_id
where d.doc_id = any($1::text[]) and c.article = $2::text
order by d.doc_id, c.ord`;

/** $1 eli -> dokładny artykuł w akcie podanym przez parametr act (preferuje #U) */
export const SQL_EXACT_BY_ELI = `
select c.id, d.doc_id, d.eli, d.title, d.display_address, d.kategoria, d.is_consolidated, d.status,
       d.source_url, c.article, c.heading, c.text, c.ord
from documents d join chunks c on c.doc_id = d.doc_id
where d.eli = $1::text and c.article = $2::text
order by (d.doc_id like '%#U') desc, d.doc_id, c.ord`;

/** $1 text[] kandydaci doc_id w kolejności preferencji */
export const SQL_DOC = `
select doc_id, eli, kategoria, title, display_address, announcement_date, status,
       is_consolidated, source_url, n_chunks
from documents where doc_id = any($1::text[])
order by array_position($1::text[], doc_id) limit 1`;

/** $1 doc_id, $2 artykuł */
export const SQL_ARTICLE_CHUNKS = `
select article, heading, text from chunks
where doc_id = $1::text and article = $2::text order by ord`;

/** $1 doc_id */
export const SQL_TOC = `
select article, (array_agg(heading order by ord))[1] as heading
from chunks where doc_id = $1::text and article is not null
group by article order by min(ord)`;

export const SQL_HEALTH = `
select (select count(*) from documents)::int as documents, (select count(*) from chunks)::int as chunks`;

// ---------- typy ----------

interface Row {
  id: number | string;
  doc_id: string; eli: string; title: string; display_address: string | null;
  kategoria: string; is_consolidated: boolean | null; status: string | null;
  source_url: string | null; article: string | null; heading: string | null; text: string;
  score?: number | string;
}

export interface SearchResult {
  doc_id: string; eli: string; title: string; display_address: string | null; kategoria: string;
  is_consolidated: boolean; article: string | null; heading: string | null; snippet: string;
  score: number; source_url: string | null; warnings: string[];
}
export interface SearchResponse { query: string; count: number; data_as_of: string | null; results: SearchResult[] }

function toResult(r: Row, snippet: string, score: number): SearchResult {
  return {
    doc_id: r.doc_id, eli: r.eli, title: r.title, display_address: r.display_address,
    kategoria: r.kategoria, is_consolidated: !!r.is_consolidated, article: r.article,
    heading: r.heading, snippet, score: Math.round(score * 10000) / 10000,
    source_url: r.source_url, warnings: warningsFor(r),
  };
}

export function normalizeEli(act: string | undefined): string | null {
  if (!act) return null;
  const a = act.trim();
  if (!ELI_RE.test(a)) throw new ApiError(400, 'bad_request', 'Parametr act musi mieć postać ELI lub doc_id, np. DU/1964/93, SAOS/12345 lub CELEX/32016R0679.');
  return a.replace(/#U$/i, '').toUpperCase();
}

// ---------- wyszukiwanie ----------

export async function searchLaw(opts: {
  q?: string; kategoria?: string; act?: string; limit: number;
}): Promise<SearchResponse> {
  const q = (opts.q ?? '').trim();
  if (!q) throw new ApiError(400, 'bad_request', 'Parametr q jest wymagany.');
  if (q.length > MAX_Q_LEN) throw new ApiError(400, 'bad_request', `Parametr q jest za długi (max ${MAX_Q_LEN} znaków).`);
  if (opts.kategoria && !(KATEGORIE as readonly string[]).includes(opts.kategoria)) {
    throw new ApiError(400, 'bad_request', `Nieznana kategoria. Dozwolone: ${KATEGORIE.join(', ')}.`);
  }
  const eli = normalizeEli(opts.act);
  const limit = opts.limit;

  const ref = parseArticleRef(q);
  const seen = new Set<string>();
  const results: SearchResult[] = [];

  // 1) dokładny artykuł ("art. 445 kodeks cywilny" lub art. + parametr act)
  if (ref.article) {
    let exact: Row[] = [];
    if (eli) {
      exact = await query<Row>(SQL_EXACT_BY_ELI, [eli, ref.article]);
    } else if (stems(ref.rest).length > 0) {
      const cands = await query<{ doc_id: string; sim: number | string }>(SQL_TITLE_MATCH, [ref.rest]);
      if (cands.length) {
        const top = Number(cands[0].sim);
        const ids = cands.filter((c) => Number(c.sim) >= top - 0.05).slice(0, 3).map((c) => c.doc_id);
        const rows = await query<Row>(SQL_EXACT_ARTICLE, [ids, ref.article]);
        rows.sort((a, b) => ids.indexOf(a.doc_id) - ids.indexOf(b.doc_id));
        exact = rows;
      }
    }
    const takenDocs = new Set<string>();
    for (const r of exact) {
      if (takenDocs.has(r.doc_id)) continue; // tylko pierwszy fragment artykułu w danym akcie
      takenDocs.add(r.doc_id);
      seen.add(String(r.id));
      results.push(toResult(r, makeSnippet(r.text, [], 320), 100));
      if (results.length >= Math.min(limit, 3)) break;
    }
  }

  // 2) pełnotekstowo
  const tsq = buildTsQuery(ref.article && eli ? ref.rest || q : q);
  if (tsq && results.length < limit) {
    const rows = await query<Row>(SQL_SEARCH, [
      tsq, limit + results.length, eli, opts.kategoria ?? null, DEFAULT_EXCLUDED,
    ]);
    const st = stems(q);
    for (const r of rows) {
      if (results.length >= limit) break;
      if (seen.has(String(r.id))) continue;
      results.push(toResult(r, makeSnippet(r.text, st), Number(r.score)));
    }
  }
  return { query: q, count: results.length, data_as_of: dataAsOf, results };
}

// ---------- artykuł ----------

export function docCandidates(id: string, variant?: string): string[] {
  const v = (variant ?? '').trim().toUpperCase();
  if (v && v !== 'U') throw new ApiError(400, 'bad_request', 'Parametr variant może mieć tylko wartość U.');
  if (!ELI_RE.test(id.trim())) throw new ApiError(400, 'bad_request', 'Parametr id musi mieć postać ELI lub doc_id, np. DU/1964/93, DU/1964/93#U, SAOS/12345 lub CELEX/32016R0679.');
  const raw = id.trim();
  const base = raw.replace(/#U$/i, '').toUpperCase();
  // wyroki (SAOS) i akty UE (CELEX) nie mają wariantu #U
  if (/^(SAOS|CELEX)\//.test(base)) return [base];
  if (/#U$/i.test(raw) || v === 'U') return [`${base}#U`];
  return [`${base}#U`, base];
}

export interface DocRow {
  doc_id: string; eli: string; kategoria: string; title: string; display_address: string | null;
  announcement_date: string | null; status: string | null; is_consolidated: boolean | null;
  source_url: string | null; n_chunks: number | null;
}

async function findDoc(id: string, variant?: string): Promise<DocRow> {
  const rows = await query<DocRow>(SQL_DOC, [docCandidates(id, variant)]);
  if (!rows.length) throw new ApiError(404, 'not_found', 'Nie znaleziono aktu o podanym identyfikatorze.');
  return rows[0];
}

export async function getArticle(opts: { id?: string; art?: string; variant?: string }) {
  if (!opts.id) throw new ApiError(400, 'bad_request', 'Parametr id jest wymagany.');
  if (!opts.art) throw new ApiError(400, 'bad_request', 'Parametr art jest wymagany (np. 445).');
  const art = normalizeArticle(opts.art);
  if (!art) throw new ApiError(400, 'bad_request', 'Niepoprawny numer artykułu (przykłady: 445, 3a, 46[1]).');
  const doc = await findDoc(opts.id, opts.variant);
  const chunks = await query<{ article: string; heading: string | null; text: string }>(SQL_ARTICLE_CHUNKS, [doc.doc_id, art]);
  if (!chunks.length) throw new ApiError(404, 'not_found', `Nie znaleziono art. ${art} w akcie ${doc.doc_id}.`);
  let text = chunks.map((c) => c.text).join('\n');
  const truncated = text.length > MAX_ARTICLE_CHARS;
  if (truncated) text = text.slice(0, MAX_ARTICLE_CHARS);
  return {
    doc_id: doc.doc_id, title: doc.title, display_address: doc.display_address,
    article: chunks[0].article, heading: chunks[0].heading, text,
    source_url: doc.source_url, warnings: warningsFor(doc), truncated, data_as_of: dataAsOf,
  };
}

// ---------- akt ----------

export async function getAct(opts: { id?: string; variant?: string; include_toc?: boolean }) {
  if (!opts.id) throw new ApiError(400, 'bad_request', 'Parametr id jest wymagany.');
  const doc = await findDoc(opts.id, opts.variant);
  const out: Record<string, unknown> = {
    doc_id: doc.doc_id, eli: doc.eli, title: doc.title, display_address: doc.display_address,
    kategoria: doc.kategoria, is_consolidated: !!doc.is_consolidated, status: doc.status,
    announcement_date: doc.announcement_date, source_url: doc.source_url,
    n_chunks: doc.n_chunks, warnings: warningsFor(doc), data_as_of: dataAsOf,
  };
  if (opts.include_toc) {
    out.articles = await query<{ article: string; heading: string | null }>(SQL_TOC, [doc.doc_id]);
  }
  return out;
}
