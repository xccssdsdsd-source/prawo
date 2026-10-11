import { neon } from '@neondatabase/serverless';
import { ApiError } from './http';

let cached: ReturnType<typeof neon> | null = null;

function client() {
  if (cached) return cached;
  const url = process.env.DATABASE_URL;
  if (!url) throw new ApiError(503, 'db_unavailable', 'Brak konfiguracji bazy danych (DATABASE_URL).');
  cached = neon(url);
  return cached;
}

/** Zapytanie parametryzowane ($1, $2, ...). Wartości użytkownika WYŁĄCZNIE przez `params`. */
export async function query<T = Record<string, unknown>>(
  text: string,
  params: unknown[] = [],
): Promise<T[]> {
  const rows = await client().query(text, params);
  return rows as unknown as T[];
}

/**
 * Tagged template (sql`... ${val}`) - wartości są parametryzowane przez sterownik.
 * Dla zgodności z api/mcp.ts; w nowym kodzie preferuj query().
 */
export const sql = ((strings: TemplateStringsArray, ...values: unknown[]) =>
  (client() as unknown as (s: TemplateStringsArray, ...v: unknown[]) => Promise<unknown[]>)(
    strings,
    ...values,
  )) as (strings: TemplateStringsArray, ...values: unknown[]) => Promise<any[]>;
