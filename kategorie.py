import re

UMOWY = ("Umowa międzynarodowa", "Konwencja", "Protokół", "Układ", "Porozumienie", "Traktat")


def kategoria(a):
    t, ty = a["title"].lower(), a.get("type", "")
    if ty == "Orzeczenie":
        return "orzeczenie"
    if ty in UMOWY:
        return "umowa"
    if ty == "Obwieszczenie":
        if "ogłoszenia jednolitego tekstu" in t or "tekst jednolity" in t:
            return "jednolite"
        if re.search(r"utracie mocy|sprostowani|wynik", t):
            return "inne"
    if "tekst jednolity" in t:
        return "jednolite"
    if re.search(r"w sprawie zmiany (nazw|granic|obszaru|siedzib|zakresu)|o zmianie (nazwy|granic)", t):
        return "podstawowe"
    if re.match(r"^(rozporządzenie|ustawa|dekret|uchwała).{0,250}?\b(zmieniając\w+|"
                r"o zmianie (ustaw|niektórych|kodeks|dekret|rozporządzeni)\w*|"
                r"w sprawie zmiany rozporządzeni\w*|o zmianach)\b", t):
        return "zmieniajace"
    return "podstawowe"
