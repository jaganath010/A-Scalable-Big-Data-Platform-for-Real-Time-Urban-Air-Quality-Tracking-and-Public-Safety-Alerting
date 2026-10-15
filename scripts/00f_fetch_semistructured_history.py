"""
================================================================================
PHASE 0f - SEMI-STRUCTURED LAYER (HISTORICAL): CAMS HOURLY ARCHIVE
================================================================================
Project : A Scalable Big Data Platform for Real-Time Urban Air Quality Tracking
Course  : 23AID302 - Big Data Analytics

WHAT THIS DOES
  Extends the semi-structured layer from a 7-day live window to the FULL
  available CAMS archive - measured to begin 2022-08 - for every city already
  geocoded by 00e_fetch_semistructured_json.py.

  Result per city: ~36,000 hourly records instead of 192.
  Across ~230 cities: ~8.4 million REAL hourly records, ~0.5 GB of raw JSON.

WHY 2022-08 AND NOT 2010
  Measured, not assumed (scratchpad probes, 5 Sep 2026):

    before 2013-01-01   API rejects: "out of allowed range from 2013-01-01"
    2013-01 .. 2022-07  timestamps returned but EVERY value is null (0% fill)
    2022-08             89.7% fill  <- real data begins
    2022-09 onward      100% fill on all pollutants except ammonia

  So a request for 2010-2023 would return ~10 years of empty rows that LOOK
  like coverage. This script deliberately starts at the first date that
  carries real values. The structured layer (2010 - 2023-03) therefore
  overlaps this one only over 2022-08 .. 2023-03 - about 8 months where both
  sources describe the same cities over the same hours, which is the only
  window in which the two layers can be cross-validated against each other.

HONESTY NOTES
  - ammonia is null for 100% of records. That is a real CAMS coverage gap for
    this region, not a processing artifact. It is kept in the schema as null
    rather than dropped, so the gap stays visible.
  - CAMS is a modelled/reanalysis product (assimilated satellite + ground
    observations), not a raw ground-sensor feed. Real, widely used, but it is
    model output and should be described that way - not as "station readings".
  - Responses are stored exactly as returned. No flattening, no perturbation,
    no interpolation.

RESUMABLE
  A city whose output file already exists is skipped, so an interrupted run
  (rate limit, network drop, machine sleep) can simply be re-run.

RUN
    python 00f_fetch_semistructured_history.py \
        --out "F:\\...\\airquality_expanded\\semistructured_history" \
        --manifest "F:\\...\\airquality_expanded\\semistructured_json\\manifest.json"
================================================================================
"""

import argparse
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone

AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

HOURLY_VARS = [
    "pm10", "pm2_5", "carbon_monoxide", "nitrogen_dioxide",
    "sulphur_dioxide", "ozone", "ammonia", "us_aqi",
]

# First date CAMS actually carries values for this region (measured - see header).
DEFAULT_START = "2022-08-01"

_print_lock = threading.Lock()
_rate_limited = threading.Event()


def log(msg):
    with _print_lock:
        print(msg, flush=True)


def http_get(url, params, retries=4, timeout=180):
    """GET with backoff. Sets the global rate-limit flag on 429."""
    full = url + "?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(1, retries + 1):
        if _rate_limited.is_set():
            raise RuntimeError("aborting: rate limit already hit")
        try:
            req = urllib.request.Request(full, headers={"User-Agent": "airquality-bigdata-project/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:300]
            if e.code == 429 or "limit" in body.lower():
                _rate_limited.set()
                raise RuntimeError(f"RATE LIMITED (HTTP {e.code}): {body}")
            last = f"HTTP {e.code}: {body}"
            if 400 <= e.code < 500:
                raise RuntimeError(last)          # client error - retrying won't help
        except Exception as e:
            last = str(e)
        time.sleep(3 * attempt)
    raise RuntimeError(f"failed after {retries} attempts: {last}")


def fetch_city(entry, out_dir, start, end, sleep_s):
    """Fetch one city's full history. Returns (city, status, records)."""
    city = entry["city"]
    fname = os.path.basename(entry["file"])           # reuse the 00e slug
    path = os.path.join(out_dir, "raw_json", fname)

    if os.path.exists(path) and os.path.getsize(path) > 1024:
        return (city, "skipped (already fetched)", None)

    params = {
        "latitude": round(float(entry["latitude"]), 4),
        "longitude": round(float(entry["longitude"]), 4),
        "hourly": ",".join(HOURLY_VARS),
        "timezone": "Asia/Kolkata",
        "start_date": start,
        "end_date": end,
    }
    raw = http_get(AQ_URL, params)
    data = json.loads(raw.decode("utf-8"))
    h = data.get("hourly") or {}
    n = len(h.get("time") or [])
    if n == 0:
        return (city, "EMPTY - no hourly block", 0)

    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(raw)                                   # stored verbatim
    os.replace(tmp, path)

    time.sleep(sleep_s)
    filled = {v: sum(1 for x in (h.get(v) or []) if x is not None) for v in HOURLY_VARS}
    return (city, "ok", {"records": n, "filled": filled,
                         "first": (h["time"][0] if n else None),
                         "last": (h["time"][-1] if n else None)})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="Output directory for the historical layer")
    ap.add_argument("--manifest", required=True, help="manifest.json from 00e (supplies geocoded coords)")
    ap.add_argument("--start", default=DEFAULT_START, help=f"Start date (default {DEFAULT_START}, first date with real values)")
    ap.add_argument("--end", default=date.today().isoformat(), help="End date (default: today)")
    ap.add_argument("--workers", type=int, default=4, help="Concurrent requests (default 4 - be polite)")
    ap.add_argument("--sleep", type=float, default=0.5, help="Pause after each successful fetch, per worker")
    ap.add_argument("--limit", type=int, default=0, help="Only fetch the first N cities (0 = all)")
    args = ap.parse_args()

    with open(args.manifest, encoding="utf-8") as f:
        manifest = json.load(f)
    cities = manifest["cities"]
    if args.limit:
        cities = cities[:args.limit]

    os.makedirs(os.path.join(args.out, "raw_json"), exist_ok=True)

    log(f"Fetching {len(cities)} cities  {args.start} -> {args.end}  "
        f"({args.workers} workers)")
    log("")

    done = failed = skipped = 0
    total_records = 0
    results = []
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(fetch_city, c, args.out, args.start, args.end, args.sleep): c
                   for c in cities}
        for i, fut in enumerate(as_completed(futures), 1):
            entry = futures[fut]
            city = entry["city"]
            try:
                _, status, info = fut.result()
            except Exception as e:
                failed += 1
                log(f"[{i:3d}/{len(cities)}] {city:22} FAILED: {e}")
                if _rate_limited.is_set():
                    log("\n*** RATE LIMIT HIT - stopping. Re-run later; finished cities are skipped. ***")
                    break
                continue

            if status.startswith("skipped"):
                skipped += 1
                log(f"[{i:3d}/{len(cities)}] {city:22} skipped (already have it)")
            elif status == "ok":
                done += 1
                total_records += info["records"]
                results.append({"city": city, "state": entry.get("state"),
                                "latitude": entry.get("latitude"), "longitude": entry.get("longitude"),
                                "file": f"raw_json/{os.path.basename(entry['file'])}",
                                "hourly_records": info["records"],
                                "first_hour": info["first"], "last_hour": info["last"],
                                "non_null_counts": info["filled"]})
                log(f"[{i:3d}/{len(cities)}] {city:22} OK  {info['records']:,} records")
            else:
                failed += 1
                log(f"[{i:3d}/{len(cities)}] {city:22} {status}")

    dt = time.time() - t0
    log("")
    log(f"fetched={done}  skipped={skipped}  failed={failed}  "
        f"records_this_run={total_records:,}  elapsed={dt/60:.1f} min")

    # Merge into a manifest that survives resumed runs
    man_path = os.path.join(args.out, "manifest.json")
    prior = []
    if os.path.exists(man_path):
        try:
            prior = json.load(open(man_path, encoding="utf-8")).get("cities", [])
        except Exception:
            prior = []
    by_city = {c["city"]: c for c in prior}
    for r in results:
        by_city[r["city"]] = r

    with open(man_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "source_air_quality": AQ_URL,
            "attribution": "Open-Meteo.com (CC-BY 4.0); data from Copernicus Atmosphere "
                           "Monitoring Service (CAMS), ECMWF",
            "note": "Historical hourly CAMS air quality, saved verbatim as returned. "
                    "CAMS is a modelled/reanalysis product, not raw ground-sensor readings. "
                    "Real values begin 2022-08; earlier dates return nulls and are not requested.",
            "date_range": {"start": args.start, "end": args.end},
            "ammonia_note": "ammonia is null for all records - a real CAMS coverage gap for this region",
            "cities": sorted(by_city.values(), key=lambda c: c["city"]),
        }, f, indent=2)

    total_all = sum(c.get("hourly_records", 0) for c in by_city.values())
    log(f"manifest: {man_path}  ({len(by_city)} cities, {total_all:,} records total)")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
