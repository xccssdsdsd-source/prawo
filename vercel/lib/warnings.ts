export interface WarnInput {
  kategoria: string;
  is_consolidated?: boolean | null;
  status?: string | null;
}

const BY_KATEGORIA: Record<string, string> = {
  podstawowe: 'Tekst w brzmieniu z dnia ogłoszenia – nie jest tekstem ujednoliconym; sprawdź ISAP.',
  zmieniajace: 'Akt zmieniający (nowelizacja) – nie jest pełnym tekstem przepisu; sprawdź tekst ujednolicony w ISAP.',
  mp: 'Akt z Monitora Polskiego – sprawdź aktualność i charakter aktu w ISAP.',
  orzeczenie: 'Orzeczenie TK – nie jest przepisem.',
  wyrok: 'Wyrok sądu – nie jest przepisem; dotyczy konkretnej sprawy.',
  umowa: 'Umowa międzynarodowa lub dokument – nie jest powszechnie obowiązującym przepisem krajowym; sprawdź ISAP.',
  ue: 'Akt prawa UE – sprawdź aktualną wersję w EUR-Lex.',
  inne: 'Dokument spoza głównego zbioru przepisów – zweryfikuj jego charakter i aktualność w ISAP.',
};

/** Generuje listę ostrzeżeń dla wyniku wg kategorii i statusu aktu. */
export function warningsFor(d: WarnInput): string[] {
  const out: string[] = [];
  const w = BY_KATEGORIA[d.kategoria];
  if (w) out.push(w);
  const st = (d.status ?? '').trim().toLowerCase();
  if (st && !st.startsWith('obowiązując') && !st.startsWith('obowiazujac')) {
    out.push(`Status aktu: „${d.status}” – akt może nie obowiązywać; sprawdź ISAP.`);
  }
  return out;
}
