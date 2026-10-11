import { describe, it, expect } from 'vitest';
import { warningsFor } from '../lib/warnings';

describe('warningsFor', () => {
  it('ujednolicone obowiązujące -> brak ostrzeżeń', () => {
    expect(warningsFor({ kategoria: 'ujednolicone', status: 'obowiązujący' })).toEqual([]);
    expect(warningsFor({ kategoria: 'jednolite', status: null })).toEqual([]);
  });
  it('podstawowe -> tekst z dnia ogłoszenia', () => {
    expect(warningsFor({ kategoria: 'podstawowe' })[0]).toBe(
      'Tekst w brzmieniu z dnia ogłoszenia – nie jest tekstem ujednoliconym; sprawdź ISAP.',
    );
  });
  it('orzeczenie -> nie jest przepisem', () => {
    expect(warningsFor({ kategoria: 'orzeczenie' })).toContain('Orzeczenie TK – nie jest przepisem.');
  });
  it('zmieniające, mp, wyrok, ue, umowa, inne mają ostrzeżenie', () => {
    for (const k of ['zmieniajace', 'mp', 'wyrok', 'ue', 'umowa', 'inne']) {
      expect(warningsFor({ kategoria: k }).length).toBeGreaterThan(0);
    }
  });
  it('status nieobowiązujący dodaje ostrzeżenie', () => {
    const w = warningsFor({ kategoria: 'ujednolicone', status: 'uchylony' });
    expect(w).toHaveLength(1);
    expect(w[0]).toContain('uchylony');
  });
});
