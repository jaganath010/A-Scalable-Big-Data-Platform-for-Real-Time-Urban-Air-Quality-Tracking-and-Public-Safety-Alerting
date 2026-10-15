"""
================================================================================
PHASE 0e - SEMI-STRUCTURED LAYER: LIVE JSON AIR-QUALITY FEED
================================================================================
Project : A Scalable Big Data Platform for Real-Time Urban Air Quality Tracking
Course  : 23AID302 - Big Data Analytics

WHAT THIS DOES
  The project's main dataset (00c_expand_dataset.py output, 27.48 GB) is
  entirely flat, fixed-schema CSV/Parquet - structured data. This script adds
  a second, genuinely semi-structured source to sit alongside it, to satisfy
  a Variety requirement without touching or reformatting the existing data.

  It pulls REAL, LIVE hourly air-quality records for ALL 241 Indian cities
  that appear in this project's own city_profiles.csv (Dataset final/) from
  Open-Meteo's public Air Quality API (backed by Copernicus CAMS
  atmospheric composition analysis/forecast - the same modelled+observed data
  source used by many production air-quality apps). Responses are saved
  EXACTLY as returned - nested JSON, no flattening, no reformatting.

  NOT simulated by this project. NOT noise-injected. Every value is what the
  live API returned when the request was made. Fields are genuinely optional
  per record (e.g. ammonia is frequently null over India in CAMS output -
  that is a property of the real upstream model, not something faked here).

WHY THIS IS ACTUALLY SEMI-STRUCTURED (not just "CSV renamed to JSON")
  - Self-describing: each response carries its own `hourly_units` schema
    alongside the data, rather than relying on an externally imposed schema.
  - Nested: `hourly` is an object of parallel arrays; per-city responses can
    (and do) have missing keys/nulls where a pollutant has no CAMS coverage.
  - Irregular across cities: two cities' JSON payloads are not guaranteed to
    carry identical fields byte-for-byte (elevation, timezone abbreviation,
    coverage of ammonia, etc. vary), unlike a CSV with one fixed header.

SOURCES (both free, public, NO API key / NO account required)
  Geocoding    : https://geocoding-api.open-meteo.com/v1/search
  Air quality  : https://air-quality-api.open-meteo.com/v1/air-quality
  Attribution  : Open-Meteo.com (CC-BY 4.0) / Copernicus Atmosphere
                 Monitoring Service (CAMS), ECMWF.

OUTPUT
  <out>/raw_json/<city_slug>.json        - one real API response per city
  <out>/manifest.json                    - what was fetched, when, from where
  <out>/semistructured_flat.csv          - OPTIONAL flattened view for joining
                                            back to the structured layer (kept
                                            separate; the JSON is the artifact
                                            of record)

RUN
    python 00e_fetch_semistructured_json.py --out "F:\\...\\airquality_semistructured" --days 7
================================================================================
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# Default location of this project's own city list (city, state), the same
# 241 cities the structured dataset covers. Falls back to a small built-in
# list only if the file can't be found, so the script still runs standalone.
DEFAULT_CITY_PROFILES = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "Dataset final", "city_profiles.csv"
)

FALLBACK_CITIES = [
    ("Delhi", "Delhi"), ("Mumbai", "Maharashtra"), ("Bengaluru", "Karnataka"),
    ("Chennai", "Tamil Nadu"), ("Kolkata", "West Bengal"), ("Hyderabad", "Telangana"),
]


def load_cities(path: str):
    """Read (city, state) pairs from this project's city_profiles.csv."""
    if not path or not os.path.isfile(path):
        print(f"WARNING: city list not found at {path!r} - using {len(FALLBACK_CITIES)} fallback cities")
        return list(FALLBACK_CITIES)
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    cities = [(r["city"], r["state"]) for r in rows]
    return cities

HOURLY_VARS = [
    "pm10", "pm2_5", "carbon_monoxide", "nitrogen_dioxide",
    "sulphur_dioxide", "ozone", "ammonia", "us_aqi",
]


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def http_get_json(url: str, params: dict, retries: int = 3, timeout: int = 20) -> dict:
    q = urllib.parse.urlencode(params)
    full = f"{url}?{q}"
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(full, headers={"User-Agent": "airquality-bigdata-project/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                return json.loads(raw.decode("utf-8")), raw
        except Exception as e:  # network hiccups, 429s, etc.
            last_err = e
            time.sleep(2 * attempt)
    raise RuntimeError(f"GET failed after {retries} attempts: {full}\n  {last_err}")


def geocode(city: str, state: str):
    data, _ = http_get_json(GEOCODE_URL, {
        "name": city, "country": "IN", "count": 5, "language": "en", "format": "json",
    })
    results = data.get("results") or []
    if not results:
        return None
    # prefer a result whose admin1 (state) matches, else take the first hit
    for r in results:
        if state.lower() in (r.get("admin1", "") or "").lower():
            return r
    return results[0]


def fetch_air_quality(lat: float, lon: float, days: int):
    params = {
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "hourly": ",".join(HOURLY_VARS),
        "timezone": "Asia/Kolkata",
        "past_days": days,
        "forecast_days": 1,
    }
    data, raw = http_get_json(AQ_URL, params)
    return data, raw


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="Output directory")
    ap.add_argument("--days", type=int, default=7, help="Days of past hourly history to fetch (default 7)")
    ap.add_argument("--sleep", type=float, default=1.0, help="Seconds between API calls (be polite to a free API)")
    ap.add_argument("--city-profiles", default=DEFAULT_CITY_PROFILES,
                     help="Path to city_profiles.csv (city,state,... columns). Defaults to this "
                          "project's own Dataset final/city_profiles.csv (241 cities).")
    ap.add_argument("--limit", type=int, default=0, help="Only fetch the first N cities (0 = all)")
    args = ap.parse_args()

    cities = load_cities(args.city_profiles)
    if args.limit:
        cities = cities[:args.limit]
    print(f"Fetching {len(cities)} cities from {args.city_profiles}")

    out_dir = args.out
    json_dir = os.path.join(out_dir, "raw_json")
    os.makedirs(json_dir, exist_ok=True)

    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_geocoding": GEOCODE_URL,
        "source_air_quality": AQ_URL,
        "attribution": "Open-Meteo.com (CC-BY 4.0); data from Copernicus Atmosphere "
                        "Monitoring Service (CAMS), ECMWF",
        "note": "Real, live API responses saved verbatim as JSON. Not generated, "
                "not perturbed, not reformatted by this project.",
        "days_requested": args.days,
        "cities_requested": len(cities),
        "cities": [],
    }

    flat_rows = []
    ok, failed = 0, []

    for i, (city, state) in enumerate(cities, 1):
        print(f"[{i:3d}/{len(cities)}] {city}, {state} ...", end=" ", flush=True)
        try:
            geo = geocode(city, state)
            if geo is None:
                print("GEOCODE MISS - skipped")
                failed.append(city)
                continue
            lat, lon = geo["latitude"], geo["longitude"]
            time.sleep(args.sleep)

            aq, raw = fetch_air_quality(lat, lon, args.days)
            time.sleep(args.sleep)

            fname = f"{slug(city)}.json"
            with open(os.path.join(json_dir, fname), "wb") as f:
                f.write(raw)

            n_hours = len(aq.get("hourly", {}).get("time", []))
            manifest["cities"].append({
                "city": city, "state": state,
                "geocoded_name": geo.get("name"), "geocoded_admin1": geo.get("admin1"),
                "latitude": lat, "longitude": lon, "elevation_m": geo.get("elevation"),
                "population": geo.get("population"),
                "file": f"raw_json/{fname}",
                "hourly_records": n_hours,
                "fields_present": sorted(aq.get("hourly", {}).keys()),
            })

            hourly = aq.get("hourly", {})
            times = hourly.get("time", [])
            for idx, t in enumerate(times):
                row = {"city": city, "state": state, "latitude": lat, "longitude": lon, "time": t}
                for var in HOURLY_VARS:
                    vals = hourly.get(var)
                    row[var] = vals[idx] if vals else None
                flat_rows.append(row)

            print(f"OK  ({n_hours} hourly records, fields={len(aq.get('hourly', {}))})")
            ok += 1
        except Exception as e:
            print(f"FAILED: {e}")
            failed.append(city)

    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    flat_path = os.path.join(out_dir, "semistructured_flat.csv")
    if flat_rows:
        cols = ["city", "state", "latitude", "longitude", "time"] + HOURLY_VARS
        with open(flat_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(flat_rows)

    print()
    print(f"Done: {ok}/{len(cities)} cities fetched, {len(failed)} failed {failed if failed else ''}")
    print(f"Raw JSON      : {json_dir}")
    print(f"Manifest      : {os.path.join(out_dir, 'manifest.json')}")
    print(f"Flattened CSV : {flat_path}  ({len(flat_rows)} rows)")


if __name__ == "__main__":
    main()
