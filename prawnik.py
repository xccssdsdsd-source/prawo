"""Lokalna wyszukiwarka obowiązującego prawa (Dz.U.).

  python prawnik.py index   - buduje indeks pełnotekstowy z prawo/dane (wznawialny)
  python prawnik.py serve   - uruchamia wyszukiwarkę na http://localhost:8765
  python prawnik.py szukaj "zadośćuczynienie art. 445"   - wyszukiwanie w terminalu
"""
import html
import json
import re
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

ROOT = Path(__file__).parent
DANE = ROOT / "dane"
DB = ROOT / "indeks.sqlite"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def db():
    c = sqlite3.connect(DB, timeout=60)
    c.execute("pragma journal_mode=wal")
    c.execute("create table if not exists akty(eli text primary key, tytul, kategoria, "
              "dziennik, data, plik)")
    c.execute("create virtual table if not exists tresc using fts5("
              "eli unindexed, tytul, tekst, tokenize='unicode61 remove_diacritics 2')")
    return c


def z_html(b):
    s = b.decode("utf-8", "replace")
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"(?i)</(p|div|tr|h\d|li)>|<br\s*/?>", "\n", s)
    return re.sub(r"[ \t]+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s)))


def z_pdf(p):
    from pypdf import PdfReader
    try:
        return "\n".join((pg.extract_text() or "") for pg in PdfReader(p).pages)
    except Exception:
        return ""


def wczytaj_meta():
    meta = {}
    for nazwa, sufiks in (("indeks_obowiazujacych.json", ""), ("indeks_mp.json", ""),
                          ("indeks_ujednolicone.json", "#U")):
        f = DANE / nazwa
        if f.exists():
            for x in json.loads(f.read_text("utf-8")):
                meta[x["ELI"] + sufiks] = x
    return meta


def klucz(p):
    """Nazwa pliku -> klucz aktu: DU_2024_1 -> DU/2024/1, U-DU_2024_1 -> DU/2024/1#U."""
    n, u = (p.stem[2:], "#U") if p.stem.startswith("U-") else (p.stem, "")
    pub, y, pos = n.split("_")
    return f"{pub}/{y}/{pos}{u}"


def index():
    meta = wczytaj_meta()
    c = db()
    done = {r[0] for r in c.execute("select eli from akty")}
    from concurrent.futures import ProcessPoolExecutor
    n = 0
    todo = []
    for p in DANE.glob("*/*_*_*.*"):
        if p.suffix not in (".html", ".pdf"):
            continue
        eli = klucz(p)
        if eli not in done and eli in meta:
            todo.append((p.suffix != ".html", p, eli))  # HTML (szybkie) najpierw
    todo.sort(key=lambda t: (t[0], str(t[1])))

    with ProcessPoolExecutor() as ex:
        wyniki = ex.map(_tekst, [(t[1], ) for t in todo], chunksize=8)
        for (pdf, p, eli), txt in zip(todo, wyniki):
            a = meta[eli]
            c.execute("insert into akty values(?,?,?,?,?,?)",
                      (eli, a["title"], p.parent.name, a["displayAddress"],
                       a.get("announcementDate"), str(p.relative_to(ROOT))))
            c.execute("insert into tresc values(?,?,?)", (eli, a["title"], txt))
            n += 1
            if n % 200 == 0:
                c.commit()
                print("zaindeksowano", n, "/", len(todo), flush=True)
    c.commit()
    print("Gotowe, nowych aktów:", n)


def _tekst(args):
    p = args[0]
    return z_html(p.read_bytes()) if p.suffix == ".html" else z_pdf(p)


def rdzen(t):
    """Przybliżony rdzeń polskiego słowa: ucina końcówkę fleksyjną, szukamy po prefiksie."""
    t = t.lower()
    return t[:-2] if len(t) > 6 else (t[:-1] if len(t) > 4 else t)


def zapytanie(q):
    q = re.sub(r"(?i)\b(art|ust|pkt)\b\.?|§", " ", q)  # "art. 445" -> samo 445
    toks = re.findall(r"\w+", q, re.U)
    return " ".join(f'"{rdzen(t)}"*' if not t.isdigit() else f'"{t}"' for t in toks)


def plik_aktu(eli):
    pub, y, pos = eli.replace("#U", "").split("/")
    pref = "U-" if eli.endswith("#U") else ""
    for ext in ("html", "pdf"):
        for f in DANE.glob(f"*/{pref}{pub}_{y}_{pos}.{ext}"):
            return f
    return None


def licznik():
    c = db()
    return c.execute("select count(*) from akty").fetchone()[0], len(wczytaj_meta())


def szukaj(q, kat=None, limit=20):
    c = db()
    sql = ("select a.eli, a.tytul, a.kategoria, a.dziennik, a.data, '', "
           "snippet(tresc, 2, '<mark>', '</mark>', ' … ', 40) "
           "from tresc join akty a on a.eli = tresc.eli where tresc match ?")
    args = [zapytanie(q)]
    if kat:
        sql += " and a.kategoria = ?"
        args.append(kat)
    else:  # domyślnie bez orzeczeń TK, umów i obwieszczeń pobocznych
        sql += " and a.kategoria in ('ujednolicone','jednolite','podstawowe','zmieniajace','mp')"
    # trafność (tytuł waży więcej), z premią dla tekstów jednolitych i podstawowych
    sql += (" order by bm25(tresc, 0.0, 8.0, 1.0) - "
            "case a.kategoria when 'ujednolicone' then 4 when 'jednolite' then 3 when 'podstawowe' then 1 else 0 end "
            "limit ?")
    args.append(limit)
    return c.execute(sql, args).fetchall()


STRONA = """<!doctype html><meta charset=utf-8><title>Prawo – wyszukiwarka</title>
<meta name=viewport content="width=device-width,initial-scale=1">
<style>body{font:16px/1.5 system-ui;max-width:860px;margin:2rem auto;padding:0 1rem;color:#1a1a1a}
input[type=text]{width:70%;padding:.6rem;font-size:1rem}button,select{padding:.6rem}
.w{border-top:1px solid #ddd;padding:.8rem 0}.m{color:#666;font-size:.85rem}
mark{background:#ffe58a}.k{font-size:.75rem;padding:.1rem .4rem;border-radius:4px;background:#eee}
.u{background:#fff4e5;border-left:4px solid #e08a00;padding:.6rem;font-size:.85rem;margin:1rem 0}</style>
<h1>Obowiązujące prawo (Dz.U., M.P.)</h1>
<form><input type=text name=q value="%(q)s" placeholder="np. zadośćuczynienie, umowa zlecenia, art. 445" autofocus>
<select name=k><option value="">wszystko (bez orzeczeń TK i umów)
<option value=ujednolicone %(s0)s>teksty ujednolicone (aktualne)
<option value=jednolite %(s1)s>obwieszczenia o tekście jednolitym
<option value=podstawowe %(s2)s>podstawowe
<option value=zmieniajace %(s3)s>zmieniające
<option value=mp %(s6)s>Monitor Polski
<option value=orzeczenie %(s4)s>orzeczenia TK
<option value=umowa %(s5)s>umowy międzynarodowe</select>
<button>Szukaj</button></form>
<div class=u>Narzędzie pomocnicze, nie porada prawna. Źródło: API ELI Sejmu. Kategoria „ujednolicone” to tekst ujednolicony (najbliższy aktualnemu); pozostałe są w brzmieniu z dnia ogłoszenia; aktualne brzmienie zawsze zweryfikuj w ISAP/Dz.U. i sprawdź późniejsze zmiany.</div>
<div class=u style="background:#eef">%(pokrycie)s</div>
%(wyniki)s"""


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/plik":
            eli = parse_qs(u.query).get("e", [""])[0]
            p = plik_aktu(eli) if re.fullmatch(r"(DU|MP)/\d+/\d+(#U)?", eli) else None
            if p is None:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf" if p.suffix == ".pdf" else "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(p.read_bytes())
            return
        qs = parse_qs(u.query)
        q, k = qs.get("q", [""])[0], qs.get("k", [""])[0]
        wyn = ""
        if q.strip():
            for eli, t, kat, dz, d, plik, sn in szukaj(q, k or None):
                sn = html.escape(sn).replace("&lt;mark&gt;", "<mark>").replace("&lt;/mark&gt;", "</mark>")
                wyn += (f"<div class=w><b>{html.escape(t)}</b><br><span class=m>{dz} · {eli} · {d} "
                        f"· <span class=k>{kat}</span> · <a href='/plik?e={quote(eli)}'>otwórz tekst</a></span>"
                        f"<br>{sn}</div>")
            wyn = wyn or "<p>Brak wyników.</p>"
        n, ile = licznik()
        pok = (f"Zaindeksowano {n} z {ile} obowiązujących aktów Dz.U." + (" – INDEKS NIEPEŁNY, brak wyniku nie oznacza braku przepisu." if n < ile * 0.98 else ""))
        body = STRONA % {"pokrycie": pok, "q": html.escape(q), "wyniki": wyn,
                         "s1": "selected" if k == "jednolite" else "",
                         "s2": "selected" if k == "podstawowe" else "",
                         "s0": "selected" if k == "ujednolicone" else "",
                         "s6": "selected" if k == "mp" else "",
                         "s3": "selected" if k == "zmieniajace" else "",
                         "s4": "selected" if k == "orzeczenie" else "",
                         "s5": "selected" if k == "umowa" else ""}
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "index":
        index()
    elif cmd == "serve":
        print("http://localhost:8765")
        HTTPServer(("127.0.0.1", 8765), H).serve_forever()
    elif cmd == "szukaj":
        for eli, t, kat, dz, d, plik, sn in szukaj(" ".join(sys.argv[2:])):
            print(f"[{kat}] {dz} ({eli})\n  {t}\n  {re.sub('<[^>]+>', '', sn)}\n")
    else:
        print(__doc__)
