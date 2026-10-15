"""Narrow down the exact date CAMS air-quality data starts having real values."""
import json, sys, time, urllib.parse, urllib.request

AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
LAT, LON = 28.65195, 77.23149


def fill_pct(start, end):
    params = {"latitude": LAT, "longitude": LON, "hourly": "pm2_5",
              "timezone": "Asia/Kolkata", "start_date": start, "end_date": end}
    full = AQ_URL + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(full, headers={"User-Agent": "airquality-bigdata-project/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return None, f"ERR {e}"
    h = data.get("hourly") or {}
    vals = h.get("pm2_5") or []
    if not vals:
        return None, "no data"
    n = len(vals)
    c = sum(1 for x in vals if x is not None)
    return 100.0 * c / n, f"{c}/{n}"


# month-by-month through the transition window
months = []
for y in (2022, 2023):
    for m in range(1, 13):
        if y == 2023 and m > 6:
            break
        last = {1:31,2:28,3:31,4:30,5:31,6:30,7:31,8:31,9:30,10:31,11:30,12:31}[m]
        months.append((f"{y}-{m:02d}-01", f"{y}-{m:02d}-{last:02d}"))

print("Month-by-month pm2_5 fill rate at Delhi:\n")
for s, e in months:
    pct, detail = fill_pct(s, e)
    flag = "  <-- DATA STARTS" if pct and pct > 0 else ""
    print(f"  {s[:7]}   fill={pct if pct is None else f'{pct:5.1f}%'}   ({detail}){flag}")
    sys.stdout.flush()
    time.sleep(1.2)
