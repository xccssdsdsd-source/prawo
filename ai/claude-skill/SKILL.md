---
name: prawo-pl
description: Wyszukiwanie i weryfikacja przepisów prawa polskiego (Dz.U., M.P.) przez własne API i serwer MCP prawo-pl (search_law, get_article, get_act). Używaj, gdy użytkownik pyta o polskie ustawy, kodeksy, artykuły, terminy, odszkodowania, umowy, przedawnienie, prawo pracy, Dz.U. lub M.P. Zawsze weryfikuj brzmienie artykułu narzędziem i podaj stan danych. Use for Polish statutes and legal research.
---

# Skill: prawo-pl (Polish law lookup)

Instalacja: folder musi nazywać się tak samo jak `name` (czyli `prawo-pl`), a w nim ten plik jako `SKILL.md`.
- Claude Code (osobiście): skopiuj `ai/claude-skill/` do `~/.claude/skills/prawo-pl/` (Windows: `%USERPROFILE%\.claude\skills\prawo-pl\`). W projekcie: `.claude/skills/prawo-pl/`.
- claude.ai / Claude Desktop: spakuj folder `prawo-pl/` (z `SKILL.md` w środku) do ZIP i wgraj w Customize > Skills (wymaga włączonego wykonywania kodu). Skill to same instrukcje – dane dostarcza konektor MCP, który dodajesz osobno (strona `/podlacz.html`).

## Kiedy użyć
Pytania o polskie przepisy. Cel: znaleźć, zweryfikować i zacytować dokładne brzmienie – nie zgadywać z pamięci.

## Narzędzia
Preferowane: serwer MCP `prawo-pl` (`search_law`, `get_article`, `get_act`). W Claude Code narzędzia nazywają się `mcp__prawo-pl__search_law` itd. Uwaga: w MCP fraza wyszukiwania to argument `query`.

Fallback bez MCP: REST przez curl/WebFetch. Zmienna: `BASE=https://TWOJA-DOMENA.vercel.app`. API jest publiczne – klucz jest opcjonalny; nagłówek `-H "Authorization: Bearer $KEY"` dodawaj tylko, gdy właściciel ustawił `API_KEY` (tryb zamknięty).

```bash
# szukanie (w REST parametr nazywa się q)
curl -s -G "$BASE/api/search" --data-urlencode "q=zadośćuczynienie śmierć najbliższego" \
  --data-urlencode "limit=8"
# zawężenie: &kategoria=ujednolicone  &act=DU/1964/93

# dokładne brzmienie artykułu (preferuje tekst ujednolicony)
curl -s -G "$BASE/api/article" --data-urlencode "id=DU/1964/93" --data-urlencode "art=446"
# art. z indeksem górnym: art=442[1]; wariant: variant=U

# spis artykułów aktu
curl -s -G "$BASE/api/act" --data-urlencode "id=DU/1964/93" --data-urlencode "include_toc=1"

# stan danych
curl -s "$BASE/data-info.json"
```
Tryb zamknięty: dodaj `-H "Authorization: Bearer $KEY"` (lub `x-api-key`). WebFetch nie pozwala na nagłówki – w trybie zamkniętym użyj curl w Bash.

## Procedura
1. `search_law` – krótka fraza (2–4 słowa) + ewentualnie `art. N` i nazwa aktu.
2. `get_article` dla każdego przepisu, który cytujesz. Nigdy nie wymyślaj numerów artykułów. Artykuł „(uchylony)” nie obowiązuje.
3. Preferencja: ujednolicone > jednolite > podstawowe > zmieniające. Dla podstawowych/zmieniających ostrzeż o możliwej nieaktualności i poszukaj wersji ujednoliconej.
4. Przekaż `warnings`; przy `truncated: true` zaznacz obcięcie.
5. Dopytaj, gdy wynik zależy od daty zdarzenia, rodzaju umowy lub stron.
6. Cytuj: `art. N § M k.c. (display_address, kategoria) – source_url`.
7. OBOWIĄZKOWO podaj: „Stan danych na dzień <data_as_of>” (z pola `data_as_of` odpowiedzi/narzędzia, `/api/health` lub `/data-info.json`) i ostrzeż: przepisy ogłoszone po tej dacie nie są uwzględnione; teksty ujednolicone mogą być starsze niż `data_as_of`.
8. Zakończ: informacja ogólna, nie porada prawna; sprawdź aktualność w ISAP. Brak wyniku ≠ brak przepisu.

Opcjonalnie: notatki wyjaśniające w `GET /wiedza/index.json` (lista `slug`, `tytul`, `opis`, `tagi`, `zweryfikowano`; treść w `/wiedza/<slug>.md`). To pomoc w orientacji, nie źródło przepisu – cytuj tylko wynik `get_article`.

Pełne zasady i scenariusze: `ai/AGENTS.md`.

## Błędy
401 – tylko w trybie zamkniętym (zły/brak klucza); 404 – brak artykułu (sprawdź `get_act` z `include_toc=1`; w niektórych aktach indeks górny jest zapisany bez nawiasów, np. `361` zamiast `36[1]`); 429 – zbyt wiele żądań, poczekaj `Retry-After`; pusty `results` – zmień frazę, usuń filtry. Nie ujawniaj klucza.
