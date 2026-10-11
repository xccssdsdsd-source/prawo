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

/** Dodatkowe ostrzeżenia dla źródeł uzupełniających (zrodla/saos, zrodla/eurlex) – dopisywane po ostrzeżeniu podstawowym. */
const WYROK_EXTRA =
  'Treść orzeczenia pochodzi z publicznej bazy orzeczeń i jest zanonimizowana przez sąd; orzeczenie może nie być prawomocne ani aktualne – podawaj sąd i sygnaturę, nie wskazuj osób prywatnych.';
const UE_ORYGINAL =
  'Tekst z Dziennika Urzędowego UE w brzmieniu z dnia publikacji – późniejsze zmiany i sprostowania nie są uwzględnione; sprawdź aktualną wersję w EUR-Lex.';
const UE_UJEDNOLICONY =
  'Wersja ujednolicona prawa UE ma charakter dokumentacyjny – wiążąca jest wersja opublikowana w Dzienniku Urzędowym UE (EUR-Lex).';

/** Generuje listę ostrzeżeń dla wyniku wg kategorii i statusu aktu. */
export function warningsFor(d: WarnInput): string[] {
  const out: string[] = [];
  const w = BY_KATEGORIA[d.kategoria];
  if (w) out.push(w);
  if (d.kategoria === 'wyrok') out.push(WYROK_EXTRA);
  if (d.kategoria === 'ue') out.push(d.is_consolidated ? UE_UJEDNOLICONY : UE_ORYGINAL);
  // Dla orzeczeń (status „orzeczenie”) i aktów UE (status opisuje rodzaj tekstu) status nie oznacza „nieobowiązujący”.
  if (d.kategoria === 'wyrok' || d.kategoria === 'ue') return out;
  const st = (d.status ?? '').trim().toLowerCase();
  if (st && !st.startsWith('obowiązując') && !st.startsWith('obowiazujac')) {
    out.push(`Status aktu: „${d.status}” – akt może nie obowiązywać; sprawdź ISAP.`);
  }
  return out;
}
