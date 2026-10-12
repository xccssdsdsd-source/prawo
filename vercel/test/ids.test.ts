import { describe, it, expect } from 'vitest';
import { normalizeEli, docCandidates, DEFAULT_EXCLUDED } from '../lib/law';

describe('identyfikatory aktów', () => {
  it('normalizeEli: ELI Dz.U./M.P., wyroki SAOS i akty UE CELEX', () => {
    expect(normalizeEli('DU/1964/93')).toBe('DU/1964/93');
    expect(normalizeEli('du/1964/93#U')).toBe('DU/1964/93');
    expect(normalizeEli('MP/2026/977')).toBe('MP/2026/977');
    expect(normalizeEli('SAOS/12345')).toBe('SAOS/12345');
    expect(normalizeEli('CELEX/32016R0679')).toBe('CELEX/32016R0679');
    expect(normalizeEli(undefined)).toBeNull();
  });
  it('normalizeEli odrzuca śmieci', () => {
    for (const bad of ['', 'DU/64/93', "DU/1964/93'; drop table", 'SAOS/', 'CELEX/3201 6R', 'abc', 'DU/1964/93/x']) {
      if (bad === '') continue; // pusty = brak filtra
      expect(() => normalizeEli(bad)).toThrow();
    }
  });
  it('docCandidates: Dz.U. preferuje #U, SAOS/CELEX bez wariantu #U', () => {
    expect(docCandidates('DU/1964/93')).toEqual(['DU/1964/93#U', 'DU/1964/93']);
    expect(docCandidates('DU/1964/93#U')).toEqual(['DU/1964/93#U']);
    expect(docCandidates('DU/1964/93', 'U')).toEqual(['DU/1964/93#U']);
    expect(docCandidates('SAOS/12345')).toEqual(['SAOS/12345']);
    expect(docCandidates('CELEX/32016R0679')).toEqual(['CELEX/32016R0679']);
    expect(docCandidates('celex/32016r0679')).toEqual(['CELEX/32016R0679']);
  });
  it('docCandidates: zły id lub variant -> 400', () => {
    expect(() => docCandidates('foo')).toThrow();
    expect(() => docCandidates('DU/1964/93', 'X')).toThrow();
  });
  it('wyroki i akty UE są domyślnie wykluczone z wyszukiwania', () => {
    expect(DEFAULT_EXCLUDED).toEqual(expect.arrayContaining(['wyrok', 'ue']));
    expect(DEFAULT_EXCLUDED).not.toContain('ujednolicone');
    expect(DEFAULT_EXCLUDED).not.toContain('mp');
  });
});
