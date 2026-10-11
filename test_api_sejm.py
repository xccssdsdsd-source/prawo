import subprocess
import sys

try:
    import requests
except ImportError:
    print("Biblioteka 'requests' nie jest zainstalowana - instaluję...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# https://sejm.gov.pl to tylko strona WWW (przekierowanie 302 do HTML).
# Właściwe API ELI (akty prawne) działa na subdomenie api.sejm.gov.pl.
URL = "https://api.sejm.gov.pl/eli/acts/DU/2024"
PARAMS = {"limit": 3, "offset": 0}

response = requests.get(URL, params=PARAMS, timeout=30)
response.raise_for_status()
data = response.json()

# API zwraca obiekt {"count": ..., "items": [...]} - lista aktów jest w "items"
items = data["items"] if isinstance(data, dict) else data
first = items[0]

print("=" * 70)
print("🟢 POTWIERDZENIE: Claude Code uzyskał pełny dostęp do globalnego API Sejmu RP!")
print("=" * 70)
print(f"Endpoint:            {response.url}")
print(f"Kod statusu HTTP:    {response.status_code}")
print(f"Typ odpowiedzi:      {type(data).__name__} (obiekt główny)")
print(f"Pole 'items':        {type(items).__name__} z {len(items)} aktami (list: {isinstance(items, list)})")
print(f"Łącznie aktów (rok): {data.get('count') if isinstance(data, dict) else 'n/d'}")
print("-" * 70)
print(f"Tytuł 1. aktu: {first.get('title')}")
print(f"pos: {first.get('pos')}  |  id/ELI: {first.get('ELI', first.get('id'))}")
print("=" * 70)
