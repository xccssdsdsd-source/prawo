import { describe, it, expect } from 'vitest';
import { rdzen, tokenize, buildTsQuery, parseArticleRef, normalizeArticle, makeSnippet } from '../lib/query';

describe('rdzen', () => {
  it('ucina końcówki wg długości', () => {
    expect(rdzen('odszkodowanie')).toBe('odszkodowan'); // >6: -2
    expect(rdzen('kodeks')).toBe('kodek'); // 6: >4 => -1
    expect(rdzen('umowa')).toBe('umow'); // 5: -1
    expect(rdzen('art')).toBe('art');
    expect(rdzen('dom')).toBe('dom');
    expect(rdzen('Cywilny')).toBe('cywil');
  });
});

describe('tokenize / buildTsQuery', () => {
  it('pomija art/ust/pkt/§ i znaki specjalne', () => {
    expect(tokenize('art. 445 § 2 ust. 1 pkt 3 kodeks')).toEqual(['445', '2', '1', '3', 'kodeks']);
  });
  it('tokeny cyfrowe bez zmian, słowa z rdzeniem i prefiksem', () => {
    expect(buildTsQuery('odszkodowanie 445')).toBe('odszkodowan:* & 445');
  });
  it('sanitizacja: tylko litery i cyfry', () => {
    const q = buildTsQuery("kodeks'; drop table x; -- (a|b) & !c:*");
    expect(q).toMatch(/^[\p{L}\p{N}:* &]+$/u);
    expect(q).not.toMatch(/[';|!()<>-]/);
  });
  it('zachowuje polskie litery', () => {
    expect(buildTsQuery('zadośćuczynienie')).toBe('zadośćuczynien:*');
  });
  it('puste wejście -> null', () => {
    expect(buildTsQuery('art. § ... !!!')).toBeNull();
    expect(buildTsQuery('')).toBeNull();
  });
  it('ogranicza liczbę tokenów', () => {
    const q = buildTsQuery(Array.from({ length: 50 }, (_, i) => `slowo${i}x`).join(' '))!;
    expect(q.split(' & ').length).toBe(12);
  });
});

describe('parseArticleRef', () => {
  it('art. 445 kodeks cywilny', () => {
    expect(parseArticleRef('art. 445 kodeks cywilny')).toEqual({ article: '445', rest: 'kodeks cywilny' });
  });
  it('art na końcu i wielkie litery', () => {
    expect(parseArticleRef('Kodeks cywilny ART 445')).toEqual({ article: '445', rest: 'Kodeks cywilny' });
  });
  it('indeks górny i litera', () => {
    expect(parseArticleRef('art. 46[1] kc').article).toBe('46[1]');
    expect(parseArticleRef('art. 46^1 kc').article).toBe('46[1]');
    expect(parseArticleRef('artykuł 3a kodeks pracy').article).toBe('3a');
  });
  it('usuwa § / ust. / pkt z reszty', () => {
    expect(parseArticleRef('art. 445 § 2 ust. 3 pkt 4 kodeks cywilny').rest).toBe('kodeks cywilny');
  });
  it('brak odwołania', () => {
    expect(parseArticleRef('zadośćuczynienie za krzywdę').article).toBeNull();
    expect(parseArticleRef('partia 445').article).toBeNull();
  });
});

describe('normalizeArticle', () => {
  it('akceptuje i normalizuje', () => {
    expect(normalizeArticle('445')).toBe('445');
    expect(normalizeArticle(' Art. 46[1] ')).toBe('46[1]');
    expect(normalizeArticle('46^1')).toBe('46[1]');
    expect(normalizeArticle('3A')).toBe('3a');
  });
  it('odrzuca śmieci', () => {
    expect(normalizeArticle("1' or 1=1")).toBeNull();
    expect(normalizeArticle('')).toBeNull();
    expect(normalizeArticle('abc')).toBeNull();
  });
});

describe('makeSnippet', () => {
  it('okno wokół trafienia, ignoruje diakrytyki', () => {
    const text = 'x '.repeat(100) + 'Zadośćuczynienie pieniężne za krzywdę' + ' y'.repeat(300);
    const s = makeSnippet(text, ['zadoscuczyn']);
    expect(s).toContain('Zadośćuczynienie');
    expect(s.length).toBeLessThan(340);
  });
  it('brak trafienia -> początek', () => {
    expect(makeSnippet('Art. 1. Treść.', ['zzz'])).toBe('Art. 1. Treść.');
  });
});
