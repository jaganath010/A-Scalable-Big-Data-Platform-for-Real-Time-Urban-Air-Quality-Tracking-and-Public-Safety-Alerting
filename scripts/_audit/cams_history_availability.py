"""
Test how far back Open-Meteo / CAMS air-quality history actually goes.
Measures, does not assume. Delhi coordinates used as the probe point.
"""
import json, sys, time, urllib.parse, urllib.request

AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
LAT, LON = 28.65195, 77.23149  # Delhi, from our existing manifest

VARS = ["pm10", "pm2_5", "carbon_monoxide", "nitrogen_dioxide",
        "sulphur_dioxide", "ozone", "ammonia", "us_aqi"]


def probe(start, end):
    params = {
        "latitude": LAT, "longitude": LON,
        "hourly": ",".join(VARS),
        "timezone": "Asia/Kolkata",
        "start_date": start, "end_date": end,
    }
    full = AQ_URL + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(full, headers={"User-Agent": "airquality-bigdata-project/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        return f"HTTP {e.code}: {body}"
    except Exception as e:
        return f"ERROR: {e}"

    h = data.get("hourly") or {}
    times = h.get("time") or []
    if not times:
        return "no hourly data returned"

    # how many of each var are actually non-null?
    counts = {}
    for v in VARS:
        vals = h.get(v) or []
        counts[v] = sum(1 for x in vals if x is not None)
    n = len(times)
    filled = {k: f"{100.0*c/n:.0f}%" for k, c in counts.items()}
    return f"{n} hours [{times[0]} .. {times[-1]}]  fill: " + " ".join(f"{k}={v}" for k, v in filled.items())


tests = [
    ("2010-01-01", "2010-01-07"),
    ("2012-06-01", "2012-06-07"),
    ("2013-01-01", "2013-01-07"),
    ("2015-03-01", "2015-03-07"),
    ("2018-11-01", "2018-11-07"),
    ("2020-01-01", "2020-01-07"),
    ("2021-06-01", "2021-06-07"),
    ("2022-01-01", "2022-01-07"),
    ("2023-03-01", "2023-03-07"),
    ("2024-01-01", "2024-01-07"),
    ("2025-06-01", "2025-06-07"),
]

print("Probing CAMS air-quality history availability at Delhi\n")
for s, e in tests:
    res = probe(s, e)
    print(f"  {s} -> {e}")
    print(f"      {res}")
    sys.stdout.flush()
    time.sleep(1.5)
