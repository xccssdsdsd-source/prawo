"""Dociąga: (1) teksty ujednolicone (typ 'U') dla Dz.U., (2) obowiązujące akty Monitora Polskiego."""
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from kategorie import kategoria

B = "https://api.sejm.gov.pl/eli"
D = Path(__file__).parent / "dane"
S = requests.Session()
S.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=16, max_retries=3))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

OK = ("obowiązujący", "akt posiada tekst jednolity")


def get(url, **kw):
    for _ in range(4):
        try:
            r = S.get(url, timeout=90, **kw)
            if r.status_code in (200, 404):
                return r if r.status_code == 200 else None
        except requests.RequestException:
            pass
    return None


def lata(pub, statusy):
    ys = get(f"{B}/acts/{pub}").json()["years"]

    def one(y):
        d = get(f"{B}/acts/{pub}/{y}")
        return [a for a in d.json()["items"] if a["status"] in statusy] if d else []

    with ThreadPoolExecutor(8) as ex:
        return [a for l in ex.map(one, ys) for a in l]


# --- 1. teksty ujednolicone Dz.U. -------------------------------------------------
du = lata("DU", OK)
print("Dz.U. kandydaci:", len(du), flush=True)
(D / "ujednolicone").mkdir(exist_ok=True)


def uj(a):
    f = D / "ujednolicone" / f"U-DU_{a['year']}_{a['pos']}.pdf"
    if f.exists():
        return a, "juz"
    det = get(f"{B}/acts/DU/{a['year']}/{a['pos']}")
    if not det:
        return a, "brak"
    for t in det.json().get("texts", []):
        if t.get("type") == "U":
            r = get(f"{B}/acts/DU/{a['year']}/{a['pos']}/text/U/{t['fileName']}")
            if r:
                f.write_bytes(r.content)
                return a, "ok"
    return a, "brak"


c, ujed = Counter(), []
with ThreadPoolExecutor(12) as ex:
    for i, (a, res) in enumerate(ex.map(uj, du), 1):
        c[res] += 1
        if res in ("ok", "juz"):
            ujed.append(a)
        if i % 1000 == 0:
            print("DU", i, dict(c), flush=True)
for a in ujed:
    a["kategoria"] = "ujednolicone"
(D / "indeks_ujednolicone.json").write_text(json.dumps(ujed, ensure_ascii=False, indent=1), "utf-8")
print("ujednolicone:", dict(c), flush=True)

# --- 2. Monitor Polski ----------------------------------------------------------
mp = lata("MP", ("obowiązujący",))
for a in mp:
    a["kategoria"] = "mp"
(D / "mp").mkdir(exist_ok=True)
(D / "indeks_mp.json").write_text(json.dumps(mp, ensure_ascii=False, indent=1), "utf-8")
print("M.P. obowiązujących:", len(mp), flush=True)


def tekst(a):
    base = D / "mp" / f"MP_{a['year']}_{a['pos']}"
    if base.with_suffix(".html").exists() or base.with_suffix(".pdf").exists():
        return "juz"
    for ext, flag in (("html", "textHTML"), ("pdf", "textPDF")):
        if a.get(flag):
            r = get(f"{B}/acts/MP/{a['year']}/{a['pos']}/text.{ext}")
            if r:
                base.with_suffix("." + ext).write_bytes(r.content)
                return ext
    return "brak"


c = Counter()
with ThreadPoolExecutor(12) as ex:
    for i, res in enumerate(ex.map(tekst, mp), 1):
        c[res] += 1
        if i % 1000 == 0:
            print("MP", i, dict(c), flush=True)
print("KONIEC", dict(c))
