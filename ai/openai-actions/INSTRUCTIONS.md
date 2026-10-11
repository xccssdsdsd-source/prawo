# Custom GPT Actions, Gemini i function calling

## 1. Custom GPT (ChatGPT)
1. ChatGPT > Explore GPTs > Create > Configure > Actions > Create new action.
2. Import from URL: `https://TWOJA-DOMENA.vercel.app/openapi.json`.
3. Authentication: API jest publiczne – wybierz **None**. Tylko jeśli właściciel włączył tryb zamknięty (`API_KEY`): API Key > Auth Type **Bearer** > wklej klucz (alternatywa: Custom, nagłówek `x-api-key`).
4. Privacy policy: wymagana przy publikacji; dla prywatnego GPT można pominąć.
5. W polu Instructions wklej tekst poniżej. Wyłącz przeglądanie internetu, jeśli chcesz opierać się tylko na API.

### Instructions dla GPT
```
Jesteś asystentem informacji o prawie polskim. Masz Action z endpointami searchLaw (/api/search), getArticle (/api/article), getAct (/api/act).
ZASADY:
1. Szukaj krótką frazą kluczową (2–4 słowa), ewentualnie "art. N" + nazwa aktu. Nie wklejaj całego pytania.
2. Każdy przepis, który cytujesz, zweryfikuj przez getArticle (id = eli, np. DU/1964/93; art = numer, np. 446; artykuły z indeksem: 46[1]).
3. NIGDY nie wymyślaj numerów artykułów ani treści. Brak wyniku nie oznacza braku przepisu – powiedz to.
4. Hierarchia: ujednolicone > jednolite > podstawowe (brzmienie z dnia ogłoszenia, może być nieaktualne) > zmieniające (nowelizacje, nie obowiązująca treść). Orzeczenia i umowy to nie przepisy.
5. Przekaż użytkownikowi pole warnings; przy truncated=true zaznacz obcięcie.
6. Cytuj: art. N § M k.c. (display_address, kategoria) + source_url; cytat dosłowny w cudzysłowie.
7. Dopytaj (1–2 pytania), gdy wynik zależy od daty zdarzenia, rodzaju umowy, stron, rodzaju sprawy.
8. OBOWIĄZKOWO w każdej odpowiedzi opartej na API podaj "Stan danych na dzień <data_as_of>" (pole data_as_of z odpowiedzi lub /api/health) i ostrzeż: przepisy ogłoszone po tej dacie nie są uwzględnione; teksty ujednolicone mogą być starsze niż data_as_of.
9. Nie udzielaj pewnych porad; unikaj "na pewno". Zakończ: "To informacja ogólna, nie porada prawna; sprawdź aktualność w ISAP lub skonsultuj się z prawnikiem."
10. Odpowiadaj w języku użytkownika.
```

Rozwiązywanie: "Could not parse OpenAPI" – sprawdź, czy `/openapi.json` jest publiczny i w wersji 3.1 (ewentualnie 3.0.x); 401 – tylko w trybie zamkniętym: klucz w Authentication.

## 2. Gemini / inne modele – function calling
Aplikacja pośrednia wykonuje wywołanie HTTP do API (z Bearer) i zwraca wynik modelowi. Definicje (JSON Schema; w Gemini `functionDeclarations`, w OpenAI `tools[].function`):

```json
[
  {
    "name": "searchLaw",
    "description": "Full-text search w polskich aktach prawnych. Krótka fraza kluczowa, opcjonalnie 'art. N' i nazwa aktu. Zwraca snippety; dokładne brzmienie sprawdź getArticle.",
    "parameters": {
      "type": "object",
      "properties": {
        "q": {"type": "string", "description": "Fraza kluczowa, np. 'zadośćuczynienie śmierć najbliższego'"},
        "kategoria": {"type": "string", "enum": ["ujednolicone","jednolite","podstawowe","zmieniajace","mp","orzeczenie","umowa","inne","wyrok","ue"]},
        "act": {"type": "string", "description": "eli aktu, np. DU/1964/93"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 20}
      },
      "required": ["q"]
    }
  },
  {
    "name": "getArticle",
    "description": "Dokładne brzmienie artykułu aktu. Używaj do weryfikacji przed cytowaniem.",
    "parameters": {
      "type": "object",
      "properties": {
        "id": {"type": "string", "description": "eli (DU/1964/93) lub doc_id (DU/1964/93#U)"},
        "art": {"type": "string", "description": "Numer artykułu, np. '445' lub '46[1]'"},
        "variant": {"type": "string", "enum": ["U"], "description": "U = tekst ujednolicony"}
      },
      "required": ["id", "art"]
    }
  },
  {
    "name": "getAct",
    "description": "Metadane aktu i opcjonalnie spis artykułów.",
    "parameters": {
      "type": "object",
      "properties": {
        "id": {"type": "string"},
        "variant": {"type": "string", "enum": ["U"]},
        "include_toc": {"type": "string", "enum": ["1"]}
      },
      "required": ["id"]
    }
  }
]
```

Mapowanie na HTTP: `searchLaw` -> `GET /api/search`, `getArticle` -> `GET /api/article`, `getAct` -> `GET /api/act`, nagłówek `Authorization: Bearer KLUCZ` tylko w trybie zamkniętym (API otwarte działa bez klucza). Do odpowiedzi modelu dołączaj `data_as_of` (zasada obowiązkowa jak wyżej). Jako system prompt użyj `ai/SYSTEM_PROMPT.md`.

Przykład (Python, Gemini): zdefiniuj powyższe jako `tools=[{"function_declarations": [...]}]`, przy `function_call` wykonaj `requests.get(BASE+path, params=args, headers=...)` i odeślij `.json()` jako `function_response`.
