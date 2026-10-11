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
  it('wyrok: ostrzeżenie podstawowe + prawomocność/anonimizacja, status „orzeczenie” nie daje ostrzeżenia o nieobowiązywaniu', () => {
    const w = warningsFor({ kategoria: 'wyrok', status: 'orzeczenie', is_consolidated: false });
    expect(w[0]).toBe('Wyrok sądu – nie jest przepisem; dotyczy konkretnej sprawy.');
    expect(w).toHaveLength(2);
    expect(w[1]).toContain('zanonimizowana');
    expect(w.join(' ')).not.toContain('Status aktu');
  });
  it('ue: oryginał z Dz.Urz. vs wersja ujednolicona; status opisowy nie generuje ostrzeżenia o statusie', () => {
    const orig = warningsFor({ kategoria: 'ue', status: 'tekst z Dz.Urz. UE (brzmienie z dnia publikacji)', is_consolidated: false });
    expect(orig[0]).toBe('Akt prawa UE – sprawdź aktualną wersję w EUR-Lex.');
    expect(orig).toHaveLength(2);
    expect(orig[1]).toContain('w brzmieniu z dnia publikacji');
    const ujed = warningsFor({ kategoria: 'ue', status: 'tekst ujednolicony UE (dokumentacyjny)', is_consolidated: true });
    expect(ujed).toHaveLength(2);
    expect(ujed[1]).toContain('dokumentacyjny');
    expect(ujed.join(' ')).not.toContain('Status aktu');
  });
  it('nowe ostrzeżenia nie zmieniają pozostałych kategorii', () => {
    expect(warningsFor({ kategoria: 'orzeczenie' })).toEqual(['Orzeczenie TK – nie jest przepisem.']);
    expect(warningsFor({ kategoria: 'mp', status: 'uchylony' })).toHaveLength(2);
  });
  it('status nieobowiązujący dodaje ostrzeżenie', () => {
    const w = warningsFor({ kategoria: 'ujednolicone', status: 'uchylony' });
    expect(w).toHaveLength(1);
    expect(w[0]).toContain('uchylony');
  });
});
