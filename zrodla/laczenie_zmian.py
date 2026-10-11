#!/usr/bin/env python3
"""Laczy pliki zmian (stan/zmiany.json z update_data.py oraz stan/zmiany_<id>.json z fetcherow zrodel dodatkowych)
w jeden plik dla `pipeline/load_to_postgres.py --sync`.

  python zrodla/laczenie_zmian.py --out stan/zmiany_razem.json stan/zmiany.json stan/zmiany_saos.json stan/zmiany_eurlex.json

Brakujace pliki sa pomijane (np. zrodlo uspione). Wynik: {"run_at", "added", "changed", "removed", "zrodla":[...]}; doc_id bez duplikatow.
Dokument obecny jednoczesnie w `removed` jednego pliku i `added`/`changed` innego trafia do `changed` (nowsza wersja wygrywa).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402


def merge(paths) -> dict:
    added, changed, removed, used = [], [], [], []
    for p in paths:
        p = Path(p)
        if not p.is_file():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        used.append(p.name)
        added += [str(x) for x in d.get("added") or []]
        changed += [str(x) for x in d.get("changed") or []]
        removed += [str(x) for x in d.get("removed") or []]
    a, c, r = dict.fromkeys(added), dict.fromkeys(changed), dict.fromkeys(removed)
    for k in list(r):
        if k in a or k in c:
            del r[k]
            c[k] = None
    for k in list(a):
        if k in c:
            del a[k]
    return {"run_at": C.now_iso(), "added": list(a), "changed": list(c), "removed": list(r), "zrodla": used}


def main(argv=None) -> int:
    C.setup_console()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("pliki", nargs="+")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    res = merge(a.pliki)
    C.atomic_write_json(Path(a.out), res)
    C.log(f"Polaczono {len(res['zrodla'])} plikow: nowe {len(res['added'])}, zmienione {len(res['changed'])}, "
          f"usuniete {len(res['removed'])} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
