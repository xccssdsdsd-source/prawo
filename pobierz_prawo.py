"""Pobiera obowiązujące akty Dz.U. z API ELI Sejmu do prawo/dane. Wznawialny."""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

B = "https://api.sejm.gov.pl/eli"
OUT = Path(__file__).parent / "dane"
OUT.mkdir(exist_ok=True)
S = requests.Session()
S.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=16, max_retries=3))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def get(url, **kw):
    for _ in range(4):
        try:
            r = S.get(url, timeout=60, **kw)
            if r.status_code == 200:
                return r
            if r.status_code == 404:
                return None
        except requests.RequestException:
            pass
    return None


from kategorie import kategoria  # noqa
def _stara(a):
    t = a["title"].lower()
    if "jednolitego tekstu" in t or "tekst jednolity" in t:
        return "jednolite"
    if re.search(r"o zmianie|zmieniając|zmieniając|w sprawie zmiany|o zmianie ustawy", t):
        return "zmieniajace"
    return "podstawowe"


# 1. metadane wszystkich lat
meta_path = OUT / "indeks_obowiazujacych.json"
if meta_path.exists():
    acts = json.loads(meta_path.read_text(encoding="utf-8"))
else:
    years = get(f"{B}/acts/DU").json()["years"]

    def year(y):
        d = get(f"{B}/acts/DU/{y}")
        return [a for a in d.json()["items"] if a["status"] == "obowiązujący"] if d else []

    with ThreadPoolExecutor(8) as ex:
        acts = [a for lst in ex.map(year, years) for a in lst]
    for a in acts:
        a["kategoria"] = kategoria(a)
    meta_path.write_text(json.dumps(acts, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"Obowiązujących aktów Dz.U.: {len(acts)}")
for k in ("jednolite", "podstawowe", "zmieniajace"):
    print(f"  {k}: {sum(a['kategoria'] == k for a in acts)}")


# 2. pełne teksty
def tekst(a):
    d = OUT / a["kategoria"]
    d.mkdir(exist_ok=True)
    base = f"DU_{a['year']}_{a['pos']}"
    if (d / f"{base}.html").exists() or (d / f"{base}.pdf").exists():
        return "juz"
    for ext, flag in (("html", "textHTML"), ("pdf", "textPDF")):
        if a.get(flag):
            r = get(f"{B}/acts/DU/{a['year']}/{a['pos']}/text.{ext}")
            if r:
                (d / f"{base}.{ext}").write_bytes(r.content)
                return ext
    return "brak"


from collections import Counter

c = Counter()
with ThreadPoolExecutor(12) as ex:
    for i, res in enumerate(ex.map(tekst, acts), 1):
        c[res] += 1
        if i % 500 == 0:
            print(i, dict(c), flush=True)
print("KONIEC", dict(c))
