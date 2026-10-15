"""One-off patch: the page uses D.live_forecast (live API warnings, injected by serve_live.py on every page load)."""
import os
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard_template.html")
s = open(p, encoding="utf-8").read()
assert "live_forecast" not in s
a = "let warned;\nif (Array.isArray(D.alerts_window)"
assert a in s
NEW = """const LF = D.live_forecast && Array.isArray(D.live_forecast.warnings) ? D.live_forecast : null;
let warned;
if (LF) {   // live API warnings, computed by serve_live.py when this page was loaded
  warned = LF.warnings.map(w => ({city: w.city, state: w.state || (liveByCity[w.city]||{}).state || '', alert_count: w.alert_count,
    worst_forecast_aqi: w.aqi_forecast, peak_forecast_for: w.forecast_for, peak_observed_at: w.observed_at,
    peak_pm25_now: w.pm25_now, peak_pm25_forecast: w.pm25_forecast, pm25_now: w.pm25_now, driver: w.driver,
    band: bandOf(w.aqi_forecast), nowIdx: pm25Index(w.pm25_now)})).sort((x,y) => y.worst_forecast_aqi - x.worst_forecast_aqi);
} else if (Array.isArray(D.alerts_window)"""
s = s.replace(a, NEW, 1)
# banner text for live mode
b = "  const asOf = fmtTs(refTime);"
assert b in s
s = s.replace(b, """  if (LF) {
    document.getElementById('b-p').textContent = `LIVE forecast from the CAMS API, fetched ${LF.fetched_at.slice(11,16)} \u00b7 AQI above 150 within the next ${LF.horizon_h} hours after ${LF.as_of} \u00b7 ${LF.cities_checked} cities checked`;
    document.getElementById('m-updated').textContent = LF.fetched_at.slice(0,16) + ' IST';
  } else {
""" + b, 1)
c = "  const w = warned[0];\n  if (w) {"
assert c in s
s = s.replace(c, "  }\n" + c, 1)
# live badge: also reload when the live warnings change
d = "if (v.generated_utc && v.generated_utc !== mine)"
assert d in s
s = s.replace(d, "const myLive = (D.live_forecast || {}).digest;\n      if ((v.generated_utc && v.generated_utc !== mine) || (v.live_digest && myLive && v.live_digest !== myLive))", 1)
open(p, "w", encoding="utf-8").write(s)
print("patched")
