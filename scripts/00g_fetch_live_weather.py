"""
================================================================================
PHASE 8b (ingest) - LIVE WEATHER PULL
================================================================================
Project : 23AID302 - Big Data Analytics

WHY THIS EXISTS
  The trained model needs 54 numeric features. Raw CAMS air-quality JSON
  carries only 28 of them. Eight of the missing ones are weather
  (temperature, humidity, wind speed, wind direction, rainfall, pressure,
  solar radiation) and five more are derived from those. This pulls them from
  Open-Meteo's weather API - the same provider as the air-quality feed, also
  free and key-less - for the same cities, same hours, same timezone.

  This is deliberately a thin HTTP ingestion client, NOT a Spark job: it is
  ~230 API calls producing a few MB. The actual join/derivation work is the
  Spark job (LiveEnrichment.scala), which is where distribution is warranted.

UNITS REQUESTED EXPLICITLY
  wind_speed_unit=ms  - the API defaults to km/h, but the structured schema
                        (and therefore the model) expects m/s. Requesting the
                        right unit is safer than converting afterwards.
  Pressure comes back in hPa and solar radiation in W/m2; the hPa -> mmHg
  conversion is done in LiveEnrichment.scala next to the other conversions.

OUTPUT
  <out>/raw_json/<city_slug>.json   one real API response per city, verbatim
  <out>/manifest.json               what was fetched, when, from where

RUN
    python 00g_fetch_live_weather.py \
        --out "F:\\...\\airquality_expanded\\live_weather" \
        --manifest "F:\\...\\airquality_expanded\\semistructured_json\\manifest.json" \
        --days 2
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
from datetime import datetime, timezone

WX_URL = "https://api.open-meteo.com/v1/forecast"

HOURLY_VARS = [
    "temperature_2m", "relative_humidity_2m", "wind_speed_10m",
    "wind_direction_10m", "precipitation", "surface_pressure",
    "shortwave_radiation", "weather_code",
]

_lock = threading.Lock()
_rate_limited = threading.Event()


def log(msg):
    with _lock:
        print(msg, flush=True)


def http_get(params, retries=4, timeout=60):
    full = WX_URL + "?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(1, retries + 1):
        if _rate_limited.is_set():
            raise RuntimeError("aborting: rate limit already hit")
        try:
            req = urllib.request.Request(full, headers={"User-Agent": "airquality-bigdata-project/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:300]
            if e.code == 429 or "limit" in body.lower():
                _rate_limited.set()
                raise RuntimeError(f"RATE LIMITED (HTTP {e.code}): {body}")
            last = f"HTTP {e.code}: {body}"
            if 400 <= e.code < 500:
                raise RuntimeError(last)
        except Exception as e:
            last = str(e)
        time.sleep(2 * attempt)
    raise RuntimeError(f"failed after {retries} attempts: {last}")


def fetch_city(entry, out_dir, days, forecast_days, sleep_s):
    city = entry["city"]
    fname = os.path.basename(entry["file"])          # reuse the air-quality slug
    path = os.path.join(out_dir, "raw_json", fname)
    if os.path.exists(path) and os.path.getsize(path) > 512:
        return city, "skipped", None

    raw = http_get({
        "latitude": round(float(entry["latitude"]), 4),
        "longitude": round(float(entry["longitude"]), 4),
        "hourly": ",".join(HOURLY_VARS),
        "timezone": "Asia/Kolkata",
        "wind_speed_unit": "ms",                     # match the structured schema
        "past_days": days,
        "forecast_days": forecast_days,
    })
    data = json.loads(raw.decode("utf-8"))
    n = len(((data.get("hourly") or {}).get("time")) or [])
    if n == 0:
        return city, "EMPTY", 0

    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(raw)                                  # stored verbatim
    os.replace(tmp, path)
    time.sleep(sleep_s)
    return city, "ok", n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--manifest", required=True,
                    help="manifest.json from the air-quality fetch - supplies city coords AND "
                         "guarantees both feeds cover exactly the same cities")
    ap.add_argument("--days", type=int, default=2, help="past days of hourly weather (default 2)")
    ap.add_argument("--forecast-days", type=int, default=1)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--sleep", type=float, default=0.4)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    cities = json.load(open(args.manifest, encoding="utf-8"))["cities"]
    if args.limit:
        cities = cities[:args.limit]
    os.makedirs(os.path.join(args.out, "raw_json"), exist_ok=True)

    log(f"Fetching weather for {len(cities)} cities "
        f"(past {args.days}d + {args.forecast_days}d forecast, {args.workers} workers)\n")

    ok = failed = skipped = 0
    results = []
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(fetch_city, c, args.out, args.days,
                            args.forecast_days, args.sleep): c for c in cities}
        for i, fut in enumerate(as_completed(futs), 1):
            entry = futs[fut]
            city = entry["city"]
            try:
                _, status, n = fut.result()
            except Exception as e:
                failed += 1
                log(f"[{i:3d}/{len(cities)}] {city:22} FAILED: {e}")
                if _rate_limited.is_set():
                    log("\n*** RATE LIMIT - stopping. Re-run later; done cities are skipped. ***")
                    break
                continue
            if status == "skipped":
                skipped += 1
            elif status == "ok":
                ok += 1
                results.append({"city": city, "state": entry.get("state"),
                                "latitude": entry.get("latitude"),
                                "longitude": entry.get("longitude"),
                                "file": f"raw_json/{os.path.basename(entry['file'])}",
                                "hourly_records": n})
                log(f"[{i:3d}/{len(cities)}] {city:22} OK  {n} records")
            else:
                failed += 1
                log(f"[{i:3d}/{len(cities)}] {city:22} {status}")

    log(f"\nfetched={ok} skipped={skipped} failed={failed} elapsed={(time.time()-t0)/60:.1f} min")

    man = os.path.join(args.out, "manifest.json")
    prior = []
    if os.path.exists(man):
        try:
            prior = json.load(open(man, encoding="utf-8")).get("cities", [])
        except Exception:
            prior = []
    by_city = {c["city"]: c for c in prior}
    for r in results:
        by_city[r["city"]] = r

    with open(man, "w", encoding="utf-8") as f:
        json.dump({
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "source": WX_URL,
            "attribution": "Open-Meteo.com (CC-BY 4.0)",
            "note": "Real live weather responses saved verbatim. wind_speed requested in m/s "
                    "to match the structured schema; pressure returned in hPa and converted "
                    "to mmHg downstream in LiveEnrichment.scala.",
            "hourly_vars": HOURLY_VARS,
            "cities": sorted(by_city.values(), key=lambda c: c["city"]),
        }, f, indent=2)
    log(f"manifest: {man} ({len(by_city)} cities)")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
