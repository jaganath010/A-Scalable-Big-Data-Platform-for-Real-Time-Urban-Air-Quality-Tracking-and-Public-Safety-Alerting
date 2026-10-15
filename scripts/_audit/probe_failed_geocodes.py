"""
Probe the 11 cities that failed geocoding, trying genuine name variants.

Strategy per city, in order of preference:
  1. exact name, country=IN            (what the original script did)
  2. known alternate transliterations  (real alternate spellings, not invented)
  3. name without country filter       (some small places are tagged oddly)

Reports EXACTLY what the API returns. Nothing is substituted or invented here -
this only shows what is findable, so a human can decide what is acceptable.
"""
import json, time, urllib.parse, urllib.request

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"

# (city_as_in_project, state, [genuine alternate spellings to try])
FAILED = [
    ("Bileipada",        "Odisha",            ["Bileipada", "Bileipara", "Baripada"]),
    ("Byrnihat",         "Meghalaya",         ["Byrnihat", "Birnihat"]),
    ("Chikkaballapur",   "Karnataka",         ["Chikkaballapur", "Chikkaballapura", "Chikballapur", "Chintamani"]),
    ("Davanagere",       "Karnataka",         ["Davanagere", "Davangere"]),
    ("Eloor",            "Kerala",            ["Eloor", "Elur", "Aluva"]),
    ("Gummidipoondi",    "Tamil Nadu",        ["Gummidipoondi", "Gummidipundi", "Gumudipoondi"]),
    ("Kunjemura",        "Odisha",            ["Kunjemura", "Kunjemura Odisha"]),
    ("Mandi Gobindgarh", "Punjab",            ["Mandi Gobindgarh", "Gobindgarh", "Mandi Govindgarh"]),
    ("Palkalaiperur",    "Tamil Nadu",        ["Palkalaiperur", "Palkalaipuram"]),
    ("Sivasagar",        "Assam",             ["Sivasagar", "Sibsagar", "Sivsagar"]),
    ("Vatva",            "Gujarat",           ["Vatva", "Vatwa"]),
]


def get(url, params, retries=3, timeout=20):
    q = urllib.parse.urlencode(params)
    full = f"{url}?{q}"
    last = None
    for a in range(1, retries + 1):
        try:
            req = urllib.request.Request(full, headers={"User-Agent": "airquality-bigdata-project/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last = e
            time.sleep(1.5 * a)
    print(f"      ! request failed: {last}")
    return {}


def try_name(name, country_filter=True):
    params = {"name": name, "count": 5, "language": "en", "format": "json"}
    if country_filter:
        params["country"] = "IN"
    data = get(GEOCODE_URL, params)
    return data.get("results") or []


print(f"{'PROJECT CITY':20} {'STATE':16} RESULT")
print("=" * 110)

resolved, unresolved = [], []

for city, state, variants in FAILED:
    hit = None
    how = None
    for v in variants:
        for cf in (True, False):
            res = try_name(v, country_filter=cf)
            time.sleep(1.1)
            if not res:
                continue
            # prefer a hit in the right state
            match = None
            for r in res:
                if state.lower() in (r.get("admin1", "") or "").lower():
                    match = r
                    break
            if match:
                hit, how = match, f"'{v}'" + ("" if cf else " (no country filter)")
                break
            # otherwise remember first Indian hit but keep looking
            if hit is None:
                for r in res:
                    if r.get("country_code") == "IN":
                        hit, how = r, f"'{v}' [STATE MISMATCH]" + ("" if cf else " (no country filter)")
                        break
        if hit and "STATE MISMATCH" not in (how or ""):
            break

    if hit:
        print(f"{city:20} {state:16} FOUND via {how}")
        print(f"{'':37} -> {hit.get('name')}, {hit.get('admin1')} "
              f"({hit.get('latitude'):.4f}, {hit.get('longitude'):.4f}) pop={hit.get('population')}")
        resolved.append((city, state, hit, how))
    else:
        print(f"{city:20} {state:16} NOT FOUND (no variant resolved)")
        unresolved.append((city, state))

print()
print("=" * 110)
print(f"RESOLVED: {len(resolved)}   STILL UNRESOLVED: {len(unresolved)}")
if unresolved:
    print("Unresolved:", ", ".join(c for c, _ in unresolved))

with open("probe_results.json", "w", encoding="utf-8") as f:
    json.dump({
        "resolved": [{"project_city": c, "project_state": s, "how": h, "geocode": g} for c, s, g, h in resolved],
        "unresolved": [{"project_city": c, "project_state": s} for c, s in unresolved],
    }, f, indent=2)
print("\nwrote probe_results.json")
