"""Po zakończeniu pobierania: nowa klasyfikacja, przeniesienie plików, aktualizacja indeksów."""
import json
import sqlite3
from pathlib import Path

from kategorie import kategoria

R = Path(__file__).parent
D = R / "dane"
p = D / "indeks_obowiazujacych.json"
acts = json.loads(p.read_text("utf-8"))
moved = 0
for a in acts:
    new = kategoria(a)
    old = a.get("kategoria")
    a["kategoria"] = new
    if old != new:
        for ext in ("html", "pdf"):
            f = D / old / f"DU_{a['year']}_{a['pos']}.{ext}"
            if f.exists():
                (D / new).mkdir(exist_ok=True)
                f.rename(D / new / f.name)
                moved += 1
p.write_text(json.dumps(acts, ensure_ascii=False, indent=1), "utf-8")
db = R / "indeks.sqlite"
if db.exists():
    c = sqlite3.connect(db)
    for a in acts:
        c.execute("update akty set kategoria=? where eli=?", (a["kategoria"], a["ELI"]))
    c.commit()
print("przeniesiono plików:", moved)
