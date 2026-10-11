"""Generuje vercel/public/data-info.json: dokładne daty aktualności danych (liczone z metadanych, nie wpisywane ręcznie).

Uruchamiaj po każdym ponownym pobraniu danych:  python pipeline/build_data_info.py
"""
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DANE = ROOT / "dane"
OUT = ROOT / "vercel" / "public" / "data-info.json"


def load(name):
    return json.loads((DANE / name).read_text("utf-8"))


def latest(items):
    return max(items, key=lambda x: (x.get("promulgation") or "", x["pos"]))


du, mp, uj = load("indeks_obowiazujacych.json"), load("indeks_mp.json"), load("indeks_ujednolicone.json")
# data pobrania = czas zapisu najświeższego pliku z metadanymi
pobrano = max((DANE / n).stat().st_mtime for n in
              ("indeks_obowiazujacych.json", "indeks_mp.json", "indeks_ujednolicone.json"))
pobrano_dt = datetime.fromtimestamp(pobrano, timezone.utc)

l_du, l_mp, l_uj = latest(du), latest(mp), latest(uj)
chunks = ROOT / "pipeline" / "out" / "chunks.jsonl"
info = {
    "data_as_of": pobrano_dt.date().isoformat(),
    "downloaded_at_utc": pobrano_dt.isoformat(timespec="minutes"),
    "source": "API ELI Sejmu RP (https://api.sejm.gov.pl/eli)",
    "scope": "Dz.U. i M.P. – tylko akty o statusie 'obowiązujący' (+ teksty ujednolicone ISAP)",
    "dz_u": {
        "documents": len(du),
        "latest_act": l_du["displayAddress"],
        "latest_promulgation_date": l_du.get("promulgation"),
        "latest_api_change_date": max(x.get("changeDate") or "" for x in du)[:10],
    },
    "m_p": {
        "documents": len(mp),
        "latest_act": l_mp["displayAddress"],
        "latest_promulgation_date": l_mp.get("promulgation"),
    },
    "consolidated_texts": {
        "documents": len(uj),
        "latest_act_with_consolidated_text": l_uj["displayAddress"],
        "latest_promulgation_date_among_them": l_uj.get("promulgation"),
        "note": "Tekst ujednolicony odzwierciedla stan prawny na dzień jego sporządzenia; zmiany ogłoszone później mogą nie być w nim ujęte.",
    },
    "categories": dict(Counter(x.get("kategoria") for x in du + mp + uj)),
    "not_covered": [
        "akty uchylone i wygasłe",
        "prawo UE",
        "orzecznictwo sądów (poza wyrokami TK ogłaszanymi w Dz.U.)",
        "akty prawa miejscowego i dzienniki wojewódzkie",
        "akty ogłoszone po dacie data_as_of",
    ],
    "legal_notice": "Narzędzie pomocnicze, nie porada prawna. Aktualne brzmienie przepisu zawsze zweryfikuj w ISAP (isap.sejm.gov.pl).",
}
if chunks.exists():
    info["indexed_chunks_file_mb"] = round(chunks.stat().st_size / 1e6, 1)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(info, ensure_ascii=False, indent=2), "utf-8")
sys.stdout.reconfigure(encoding="utf-8")
print(json.dumps(info, ensure_ascii=False, indent=2))
