"""
LIVE WARNINGS STRAIGHT FROM THE LIVE API - computed on every page load
================================================================================
Project : 23AID302 - Big Data Analytics

Why this exists
  The Spark pipeline (fetch -> enrich -> stream -> GBT) takes 15-20 minutes per run, so
  a page that only shows the last Spark run is always a little old. To ALERT PEOPLE with
  what is happening now, serve_live.py also asks the live Open-Meteo / CAMS API directly,
  for all 230 cities in a few multi-location calls (seconds), and converts the CAMS hourly
  pollutant forecast to the official CPCB AQI with the same breakpoints and averaging
  windows as the pipeline (AirQualityStream.scala).

  IMPORTANT: this is the CAMS model's own forecast turned into AQI - it does NOT use our
  trained GBT (that needs the Spark cluster). The page labels it as "Live CAMS forecast".
  The GBT forecasts remain the project's modelling result; this is the fast alert path.

Result is cached for CACHE_S seconds, so refreshing the page never hammers the API.
================================================================================
"""
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "dashboard_data.json")
API = "https://air-quality-api.open-meteo.com/v1/air-quality"
CACHE_S = 300
HORIZON_H = 6
THRESHOLD = 150          # project rule: warn when AQI > 150

# same breakpoints as AirQualityStream.scala  (conc_lo, conc_hi, aqi_lo, aqi_hi)
BP = {
    "pm25": [(0, 30, 0, 50), (30, 60, 51, 100), (60, 90, 101, 200), (90, 120, 201, 300), (120, 250, 301, 400), (250, 1000, 401, 500)],
    "pm10": [(0, 50, 0, 50), (50, 100, 51, 100), (100, 250, 101, 200), (250, 350, 201, 300), (350, 430, 301, 400), (430, 1000, 401, 500)],
    "no2": [(0, 40, 0, 50), (40, 80, 51, 100), (80, 180, 101, 200), (180, 280, 201, 300), (280, 400, 301, 400), (400, 1000, 401, 500)],
    "so2": [(0, 40, 0, 50), (40, 80, 51, 100), (80, 380, 101, 200), (380, 800, 201, 300), (800, 1600, 301, 400), (1600, 3000, 401, 500)],
    "co": [(0, 1, 0, 50), (1, 2, 51, 100), (2, 10, 101, 200), (10, 17, 201, 300), (17, 34, 301, 400), (34, 100, 401, 500)],
    "o3": [(0, 50, 0, 50), (50, 100, 51, 100), (100, 168, 101, 200), (168, 208, 201, 300), (208, 748, 301, 400), (748, 1000, 401, 500)],
}
WIN = {"pm25": 24, "pm10": 24, "no2": 24, "so2": 24, "co": 8, "o3": 8}          # CPCB averaging hours
FIELD = {"pm25": "pm2_5", "pm10": "pm10", "no2": "nitrogen_dioxide", "so2": "sulphur_dioxide", "co": "carbon_monoxide", "o3": "ozone"}
BANDS = [(50, "Good"), (100, "Satisfactory"), (200, "Moderate"), (300, "Poor"), (400, "Very Poor"), (10**9, "Severe")]

_cache = {"t": 0.0, "value": None}


def sub_index(p, c):
    for lo, hi, ilo, ihi in BP[p]:
        if c <= hi:
            return ilo + (ihi - ilo) * (c - lo) / (hi - lo)
    return 500.0


def band(aqi):
    return next(n for m, n in BANDS if aqi <= m)


def _trailing_avg(vals, i, n, min_valid):
    w = [v for v in vals[max(0, i - n + 1): i + 1] if v is not None]
    return sum(w) / len(w) if len(w) >= min_valid else None


def _cities():
    d = json.load(open(DATA, encoding="utf-8"))
    return [c for c in d["live_latest"] if c.get("latitude") is not None]


def _fetch(batch):
    q = {"latitude": ",".join(str(c["latitude"]) for c in batch), "longitude": ",".join(str(c["longitude"]) for c in batch),
         "hourly": ",".join(FIELD.values()), "past_days": 2, "forecast_days": 2, "timezone": "Asia/Kolkata"}
    with urllib.request.urlopen(API + "?" + urllib.parse.urlencode(q), timeout=40) as r:
        out = json.load(r)
    return out if isinstance(out, list) else [out]


def compute(now=None):
    """Warnings for the next HORIZON_H hours for every city, from the live API."""
    now = now or datetime.now().replace(minute=0, second=0, microsecond=0)
    cities = _cities()
    warnings, checked, failed = [], 0, 0
    for k in range(0, len(cities), 40):
        batch = cities[k:k + 40]
        try:
            res = _fetch(batch)
        except Exception:
            failed += len(batch)
            continue
        for c, r in zip(batch, res):
            h = r.get("hourly") or {}
            times = h.get("time") or []
            if not times:
                failed += 1
                continue
            checked += 1
            ts = [datetime.fromisoformat(t) for t in times]
            series = {p: [(None if v is None else (v / 1000.0 if p == "co" else v)) for v in h.get(FIELD[p], [])] for p in BP}
            best = None
            hours = 0
            cur = next((i for i, t in enumerate(ts) if t == now), None)
            pm25_now = series["pm25"][cur] if cur is not None else None
            for i, t in enumerate(ts):
                if not (now < t <= now + timedelta(hours=HORIZON_H)):
                    continue
                sis = {}
                for p in BP:
                    a = _trailing_avg(series[p], i, WIN[p], 6 if WIN[p] == 8 else 16)
                    if a is not None:
                        sis[p] = sub_index(p, a)
                if not sis:
                    continue
                dom = max(sis, key=sis.get)
                aqi = sis[dom]
                if aqi > THRESHOLD:
                    hours += 1
                    if best is None or aqi > best["aqi"]:
                        best = {"aqi": aqi, "t": t, "dom": dom, "pm25": series["pm25"][i]}
            if best:
                warnings.append({"city": c["city"], "state": c.get("state", ""), "aqi_forecast": round(best["aqi"], 1), "band": band(best["aqi"]),
                                 "forecast_for": best["t"].strftime("%Y-%m-%d %H:%M:%S"),
                                 "observed_at": (best["t"] - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
                                 "driver": best["dom"], "pm25_now": pm25_now, "pm25_forecast": best["pm25"], "alert_count": hours})
    warnings.sort(key=lambda w: -w["aqi_forecast"])
    digest = hashlib.md5("|".join(f'{w["city"]}:{round(w["aqi_forecast"])}' for w in warnings).encode()).hexdigest()[:10]
    return {"source": "Open-Meteo CAMS live API, converted to CPCB AQI (not the GBT model)", "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "as_of": now.strftime("%Y-%m-%d %H:%M"), "horizon_h": HORIZON_H, "cities_checked": checked, "cities_failed": failed, "digest": digest, "warnings": warnings}


def get(force=False):
    """Cached live result; None if the API cannot be reached and nothing is cached."""
    if not force and _cache["value"] and time.time() - _cache["t"] < CACHE_S:
        return _cache["value"]
    try:
        v = compute()
        if v["cities_checked"] > 0:
            _cache.update(t=time.time(), value=v)
            return v
    except Exception:
        pass
    return _cache["value"]


if __name__ == "__main__":
    v = compute()
    print(v["as_of"], "checked", v["cities_checked"], "failed", v["cities_failed"], "warned", len(v["warnings"]))
    for w in v["warnings"][:8]:
        print(f'  {w["city"]:<14} AQI {w["aqi_forecast"]:>6}  {w["band"]:<10} {w["forecast_for"]}  {w["driver"]}  pm25 {w["pm25_now"]}->{w["pm25_forecast"]}')
