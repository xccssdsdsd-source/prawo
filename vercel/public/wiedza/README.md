# Baza wiedzy o polskim prawie – instrukcja utrzymania

Katalog `vercel/public/wiedza/` zawiera poradniki w markdown po polsku dla modeli AI i ludzi oraz spis maszynowy `index.json` (`[{slug, tytul, opis, tagi, zweryfikowano}]`). Pliki są serwowane statycznie jako `/wiedza/<slug>.md`; spis jako `/wiedza/index.json`; skrót w `/llms.txt`. Treść nie jest źródłem prawa i nie jest poradą prawną.

## Zasady rzetelności (obowiązują przy każdej zmianie)

1. Każde twierdzenie o konkretnym przepisie ma odnośnik w formie `[doc_id art. N]`, np. `[DU/1964/93#U art. 118]`. Warianty: `[doc_id art. 118, 123]`, `[doc_id § 158]` (rozporządzenia bez artykułów, np. ZTP), `[doc_id ord 1]` (fragment wstępny bez numeru artykułu; `ord` to numer fragmentu).
2. Odnośnik musi wskazywać artykuł istniejący w `pipeline/out/chunks.jsonl`, a cytat dosłowny w polskich cudzysłowach („…”) musi występować w treści wskazanego artykułu. Cudzysłowów „…” **nie używaj** do niczego innego w linii z odnośnikiem (nazwy, określenia – pisz w backtickach lub bez cudzysłowu), bo weryfikator uzna to za cytat.
3. Czego nie da się sprawdzić w danych – oznacz **[WO]** (wiedza ogólna, do weryfikacji w ISAP) albo pomiń. Zero zmyślonych numerów artykułów.
4. Nagłówek każdego pliku: data weryfikacji i zastrzeżenie „to nie jest porada prawna”.
5. Zapis numerów z indeksem górnym: w odnośnikach `442¹` albo `442[1]`; w danych bywa też „spłaszczony” (`291` dla art. 29¹ k.p.) – odnośnik musi używać numeru z rekordu w bazie (patrz `jak-czytac-akt-prawny`, pkt 5).

## Weryfikacja i odświeżanie

```
python pipeline/tools/lookup_article.py --verify-md vercel/public/wiedza/*.md
```

Polecenie sprawdza wszystkie odnośniki i cytaty (kod wyjścia 3 przy błędach). Po każdej aktualizacji danych („Uaktualnij to wszystko”) uruchom je: błąd oznacza, że przepis zmienił brzmienie lub zniknął z tekstu ujednoliconego i wpis trzeba poprawić. Podgląd treści: `python pipeline/tools/lookup_article.py "DU/1964/93#U" 118 --out wynik.txt` (zapis do pliku UTF-8 omija problemy konsoli Windows). Narzędzia nie wczytują całego `chunks.jsonl` do pamięci (strumieniowo, ok. 2–10 s).

## Które pliki starzeją się najszybciej

| Plik | Co odświeżyć po aktualizacji danych |
|---|---|
| `nadchodzace-zmiany.md` | cała tabela i liczby: `python pipeline/tools/lookup_article.py --upcoming --from RRRR-MM-DD`; usuń zmiany, które weszły w życie |
| `kodeksy-i-glowne-ustawy.md` | kolumny „Zmiana rekordu w ELI” i „Najnowszy tekst jednolity” (nowe obwieszczenia); nowe ustawy |
| `gdzie-szukac-dalej.md` | adresy portali, stan ELI vs stan bazy (pozycje Dz.U./M.P.), status API (SAOS, TK, ISAP) |
| `jak-czytac-akt-prawny.md`, `najczestsze-pulapki.md`, `jak-czytac-prawo-dla-agentow-ai.md` | przykłady z konkretnych rekordów (np. art. 94³ k.p., art. 124 k.p.k., porównanie k.p.c.) – po zmianie tekstów mogą się zdezaktualizować |
| `terminy-i-przedawnienie.md`, `wejscie-w-zycie-i-vacatio-legis.md` | terminy i przykłady z aktów 2025–2026 (przepisy przejściowe) |
| pozostałe | zmieniają się rzadko; weryfikator wystarczy |

Po przeglądzie ustaw `zweryfikowano` w `index.json` oraz datę w nagłówku pliku. Nowy temat: nowy `<slug>.md` + wpis w `index.json` + (opcjonalnie) wiersz w sekcji „Baza wiedzy” w `vercel/public/llms.txt`.

## Znane ograniczenia danych (ważne dla autora treści)

- `announcement_date` w bazie to data wydania aktu, nie data ogłoszenia (ta jest w nagłówku Dziennika Ustaw w pierwszym fragmencie tekstu aktu albo w ELI jako `promulgation`).
- Dla k.p. i niektórych innych ustaw indeksy górne są spłaszczone, a artykuły z indeksem bywają wklejone w rekord poprzedniego artykułu.
- Teksty ujednolicone zawierają wklejone przypisy i adnotacje o przyszłych brzmieniach.
- Strony `gdzie-szukac-dalej` oparto na badaniu z 2026-10-11; część serwisów (ISAP, SN, orzeczenia.ms.gov.pl) blokuje skrypty, więc nie da się ich automatycznie ponownie sprawdzić.
