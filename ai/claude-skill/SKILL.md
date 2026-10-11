---
name: prawo-pl
description: Wyszukiwanie i weryfikacja przepisów prawa polskiego (Dz.U., M.P.) przez własne API. Używaj, gdy użytkownik pyta o polskie ustawy, kodeksy, artykuły, terminy, odszkodowania, umowy, przedawnienie, prawo pracy – zawsze weryfikuj brzmienie artykułu przed cytowaniem. Use for Polish statutes and legal research.
---

# Skill: prawo-pl (Polish law lookup)

## Kiedy użyć
Pytania o polskie przepisy. Cel: znaleźć, zweryfikować i zacytować dokładne brzmienie – nie zgadywać.

## Narzędzia
Jeśli dostępny jest serwer MCP `prawo` (patrz `ai/mcp/README.md`): `search_law`, `get_article`, `get_act`.
Fallback bez MCP: REST przez curl/WebFetch. Zmienna: `BASE=https://TWOJA-DOMENA.vercel.app`. API jest publiczne – klucz jest opcjonalny; nagłówek `-H "Authorization: Bearer $KEY"` dodawaj tylko, gdy właściciel ustawił `API_KEY` (tryb zamknięty).

```bash
# szukanie
curl -s -G "$BASE/api/search" --data-urlencode "q=zadośćuczynienie śmierć najbliższego" \
  --data-urlencode "limit=8" -H "Authorization: Bearer $KEY"
# zawężenie: &kategoria=ujednolicone  &act=DU/1964/93

# dokładne brzmienie artykułu (preferuje tekst ujednolicony)
curl -s -G "$BASE/api/article" --data-urlencode "id=DU/1964/93" --data-urlencode "art=446" \
  -H "Authorization: Bearer $KEY"
# art. z indeksem: art=46[1]; wariant: variant=U

# spis artykułów aktu
curl -s -G "$BASE/api/act" --data-urlencode "id=DU/1964/93" --data-urlencode "include_toc=1" \
  -H "Authorization: Bearer $KEY"
```
WebFetch: te same URL-e (bez nagłówków, jeśli API jest otwarte). W trybie zamkniętym dodaj `Authorization: Bearer KLUCZ` (lub `x-api-key`); gdy narzędzie nie pozwala na nagłówki, użyj curl w Bash.
Linie `-H "Authorization: Bearer $KEY"` w przykładach powyżej pomiń w trybie otwartym.

## Procedura
1. `search_law` – krótka fraza (2–4 słowa) + ewentualnie `art. N` i nazwa aktu.
2. `get_article` dla każdego przepisu, który cytujesz. Nigdy nie wymyślaj numerów artykułów.
3. Preferencja: ujednolicone > jednolite > podstawowe > zmieniające. Dla podstawowych/zmieniających ostrzeż o możliwej nieaktualności i poszukaj wersji ujednoliconej.
4. Przekaż `warnings`; przy `truncated: true` zaznacz obcięcie.
5. Dopytaj, gdy wynik zależy od daty zdarzenia, rodzaju umowy lub stron.
6. Cytuj: `art. N § M k.c. (display_address, kategoria) – source_url`.
7. OBOWIĄZKOWO podaj: „Stan danych na dzień <data_as_of>” (z pola `data_as_of` odpowiedzi, `/api/health` lub `/data-info.json`) i ostrzeż: przepisy ogłoszone po tej dacie nie są uwzględnione; teksty ujednolicone mogą być starsze niż `data_as_of`.
8. Zakończ: informacja ogólna, nie porada prawna; sprawdź aktualność w ISAP. Brak wyniku ≠ brak przepisu.

Pełne zasady i scenariusze: `ai/AGENTS.md`.

## Błędy
401 – tylko w trybie zamkniętym (zły/brak klucza); 404 – brak artykułu (sprawdź `get_act` z `include_toc=1`); pusty `results` – zmień frazę, usuń filtry. Nie ujawniaj klucza.
