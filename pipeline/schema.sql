-- Schemat Postgresa dla Prawo API (wg docs/SPEC.md). Idempotentny.
create extension if not exists unaccent;
create extension if not exists pg_trgm;

-- UWAGA: unaccent() jest STABLE, a kolumna generowana wymaga IMMUTABLE,
-- dlatego opakowanie (bez niego "generation expression is not immutable").
-- Po stronie zapytan uzywaj f_unaccent() / pl_prefix_query() - ta sama normalizacja.
create or replace function f_unaccent(text) returns text
  language sql immutable parallel safe strict
  as $$ select public.unaccent('public.unaccent'::regdictionary, $1) $$;

create table if not exists documents(
  doc_id text primary key, eli text not null, kategoria text not null, publisher text, year int, pos int,
  title text not null, display_address text, announcement_date date, status text,
  is_consolidated boolean default false, source_url text, n_chunks int default 0);

create table if not exists chunks(
  id bigserial primary key, doc_id text not null references documents(doc_id) on delete cascade,
  ord int not null, article text, heading text, text text not null,
  tsv tsvector generated always as (to_tsvector('simple', f_unaccent(coalesce(heading,'')||' '||text))) stored);

create index if not exists chunks_tsv on chunks using gin(tsv);
create index if not exists chunks_doc on chunks(doc_id, ord);
create index if not exists chunks_art on chunks(doc_id, article);
create index if not exists documents_title_trgm on documents using gin(title gin_trgm_ops);
create index if not exists documents_eli on documents(eli);
create index if not exists documents_kat on documents(kategoria);

-- Zapytanie uzytkownika -> tsquery z prefiksami i przyblizonym stemmingiem polskim
-- (jak rdzen() w prawnik.py): dlugosc >6 ucina 2 znaki, >4 ucina 1; tokeny cyfrowe bez zmian;
-- 'art', 'ust', 'pkt' oraz '§' pomijane; tokeny laczone '&'. Brak tokenow -> NULL.
create or replace function pl_prefix_query(q text) returns tsquery
  language plpgsql stable parallel safe as $$
declare
  parts text[] := '{}';
  t text;
  s text;
begin
  for t in
    select m[1] from regexp_matches(lower(f_unaccent(coalesce(q,''))), '([[:alnum:]_]+)', 'g') as m
  loop
    if t in ('art','ust','pkt') then continue; end if;
    if t ~ '^[0-9]+$' then
      parts := parts || t;
    else
      s := case when length(t) > 6 then left(t, length(t)-2)
                when length(t) > 4 then left(t, length(t)-1)
                else t end;
      parts := parts || (s || ':*');
    end if;
  end loop;
  if array_length(parts,1) is null then return null; end if;
  return to_tsquery('simple', array_to_string(parts, ' & '));
end $$;
