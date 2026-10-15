"""Test a single full-range (2022-08-01 -> today) request: does it work, how big, how slow."""
import json, time, urllib.parse, urllib.request
from datetime import date

AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
LAT, LON = 28.65195, 77.23149
VARS = ["pm10", "pm2_5", "carbon_monoxide", "nitrogen_dioxide",
        "sulphur_dioxide", "ozone", "ammonia", "us_aqi"]

START = "2022-08-01"
END = date.today().isoformat()

params = {"latitude": LAT, "longitude": LON, "hourly": ",".join(VARS),
          "timezone": "Asia/Kolkata", "start_date": START, "end_date": END}
full = AQ_URL + "?" + urllib.parse.urlencode(params)

print(f"Requesting {START} -> {END} ...")
t0 = time.time()
try:
    req = urllib.request.Request(full, headers={"User-Agent": "airquality-bigdata-project/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read()
    dt = time.time() - t0
    data = json.loads(raw.decode("utf-8"))
    h = data.get("hourly") or {}
    times = h.get("time") or []
    n = len(times)
    filled = {v: sum(1 for x in (h.get(v) or []) if x is not None) for v in VARS}
    print(f"  OK in {dt:.1f}s")
    print(f"  raw response size : {len(raw)/1024/1024:.2f} MB")
    print(f"  hourly records    : {n:,}")
    print(f"  range             : {times[0]} .. {times[-1]}")
    print("  fill rates        : " + " ".join(f"{k}={100.0*c/n:.0f}%" for k, c in filled.items()))
    print()
    print(f"  ESTIMATE for 234 cities: {234*len(raw)/1024/1024/1024:.2f} GB raw JSON, "
          f"{234*n:,} records, ~{234*dt/60:.0f} min at this speed (no politeness delay)")
except urllib.error.HTTPError as e:
    print(f"  HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:400]}")
except Exception as e:
    print(f"  ERROR: {e}")
