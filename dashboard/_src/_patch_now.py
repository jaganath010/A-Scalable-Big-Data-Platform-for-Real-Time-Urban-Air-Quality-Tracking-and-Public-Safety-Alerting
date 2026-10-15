"""One-off patch: cards, banner and table show the warnings for the NEXT HOURS (relative to now),
not each city's peak over the whole run."""
import os
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard_template.html")
s = open(p, encoding="utf-8").read()
assert "HORIZON_H" not in s

old_start = "const warned = (D.alert_summary||[]).map(a => {"
old_end = "}).sort((x,y) => y.worst_forecast_aqi - x.worst_forecast_aqi);"
a = s.index(old_start)
b = s.index(old_end, a) + len(old_end)
NEW = """/* ---------- WHICH WARNINGS: the next hours after "now", not each city's peak over the whole run ----------
   Reference time: live (served over http) = the clock; static snapshot = the last scored hour.
   If the live data is more than 3 h older than the clock we say so and fall back to the data's own time. */
const HORIZON_H = 6;
const parseTs = (x) => new Date(String(x).replace(' ', 'T'));
const dataEnd = parseTs((D.run_window || {}).observed_to || D.generated_utc);
const isLiveMode = /^https?:/.test(location.protocol);
const nowClock = new Date();
const staleHours = isLiveMode ? (nowClock - dataEnd) / 36e5 : 0;
const dataStale = isLiveMode && staleHours > 3;
const refTime = (isLiveMode && !dataStale) ? nowClock : dataEnd;
const refEnd = new Date(refTime.getTime() + HORIZON_H * 36e5);
const pad2 = (n) => String(n).padStart(2, '0');
const fmtTs = (d) => d.getFullYear() + '-' + pad2(d.getMonth()+1) + '-' + pad2(d.getDate()) + ' ' + pad2(d.getHours()) + ':' + pad2(d.getMinutes());
let warned;
if (Array.isArray(D.alerts_window) && D.alerts_window.length && D.alerts_window[0].pm25_now !== undefined) {
  const best = {};
  for (const r of D.alerts_window) {
    const t = parseTs(r.forecast_for);
    if (!(t > refTime && t <= refEnd)) continue;
    const c = (best[r.city] ||= {rows: 0, top: r});
    c.rows += 1;
    if (r.aqi_forecast > c.top.aqi_forecast) c.top = r;
  }
  warned = Object.entries(best).map(([city, c]) => {
    const r = c.top, live = liveByCity[city] || {};
    return {city, state: live.state || '', alert_count: c.rows, worst_forecast_aqi: r.aqi_forecast,
            peak_forecast_for: r.forecast_for, peak_observed_at: r.observed_at, peak_pm25_now: r.pm25_now,
            peak_pm25_forecast: r.pm25_forecast, pm25_now: r.pm25_now, driver: r.aqi_dominant_pollutant,
            band: bandOf(r.aqi_forecast), nowIdx: pm25Index(r.pm25_now), message: r.message};
  }).sort((x,y) => y.worst_forecast_aqi - x.worst_forecast_aqi);
} else {   // older data file without the upcoming-hours export: fall back to the run's peak per city
  warned = (D.alert_summary||[]).map(a => {
    const live = liveByCity[a.city] || {};
    return {...a, state: live.state || '', pm25_now: a.peak_pm25_now, driver: a.peak_driver,
            band: bandOf(a.worst_forecast_aqi), nowIdx: pm25Index(a.peak_pm25_now)};
  }).sort((x,y) => y.worst_forecast_aqi - x.worst_forecast_aqi);
}"""
s = s[:a] + NEW + s[b:]
s = s.replace("const liveByCity = Object.fromEntries((D.live_latest||[]).map(r => [r.city, r]));\nconst HORIZON_H", "const HORIZON_H", 1) if s.count("const liveByCity") > 1 else s

# banner text
_bs = s.index("section('banner'")
old_b = s[s.index("  document.getElementById('b-p').textContent", _bs): s.index("  const w = warned[0];", _bs)]
new_b = """  const asOf = fmtTs(refTime);
  document.getElementById('b-p').textContent = `Forecast above AQI 150 within the next ${HORIZON_H} hours (after ${asOf}) \\u00b7 ${(D.live_latest||[]).length} cities monitored` +
    (dataStale ? ` \\u00b7 DATA IS ${Math.round(staleHours)} h OLD - showing the last scored hour; run a scoring cycle for fresh warnings` : (isLiveMode ? '' : ' \\u00b7 snapshot as of the last scored hour'));
  if (dataStale) document.getElementById('banner').style.borderLeftColor = '#8a6a00';
"""
s = s.replace(old_b, new_b, 1)
s = s.replace("document.getElementById('b-h').textContent = 'cities under an air-quality warning';", "document.getElementById('b-h').textContent = warned.length ? 'cities under an air-quality warning' : 'cities under warning for the next hours \\u2014 none forecast above AQI 150';", 1)

# card facts
s = s.replace('<span>Warnings in this run <b class="mono">${w.alert_count}</b></span>', '<span>Warned hours ahead <b class="mono">${w.alert_count} of ${HORIZON_H}</b></span>', 1)
s = s.replace('<span class="mono when">peak of ${w.alert_count} warnings · ${date}</span>', '<span class="mono when">worst of the next ${HORIZON_H} h · ${date}</span>', 1)

# table: from the same upcoming warnings
t0 = s.index("  document.querySelector('#alert-table tbody').innerHTML")
t1 = s.index("}).join('');", t0) + len("}).join('');")
NEWT = """  document.querySelector('#alert-table tbody').innerHTML = warned.slice(0,20).map(w => {
    const b = w.band;
    const msg = w.message || `Air quality warning for ${w.city}: forecast AQI ${fmt(w.worst_forecast_aqi)} (${b.name}), driven by ${w.driver}. Forecast PM2.5 ${fmt(w.peak_pm25_forecast,1)} ug/m3 by ${String(w.peak_forecast_for).slice(0,16)}.`;
    return `<tr><td><b>${esc(w.city)}</b></td><td class="mono">${esc(String(w.peak_forecast_for).slice(0,16))}</td>
      <td class="num mono">${fmt(w.pm25_now,1)}</td><td class="num mono">${fmt(w.peak_pm25_forecast,1)}</td><td class="num mono"><b>${fmt(w.worst_forecast_aqi)}</b></td>
      <td><span class="band ${b.light?'light':''}" style="--b:${col(b)}">${b.name}</span></td><td>${POL[w.driver]||esc(w.driver)}</td>
      <td class="msg">${esc(msg)}</td></tr>`;}).join('');"""
s = s[:t0] + NEWT + s[t1:]

# the two whole-run charts are labelled as such
s = s.replace("<h2>Warnings issued per hour<small>forecast hour</small></h2>", "<h2>Warnings issued per hour<small>whole run, 1\\u201315 Oct \\u00b7 forecast hour</small></h2>", 1)
s = s.replace("<h2>What is causing the warnings<small>dominant pollutant</small></h2>", "<h2>What is causing the warnings<small>whole run, 1\\u201315 Oct \\u00b7 dominant pollutant</small></h2>", 1)
s = s.replace("<h2>Strongest warnings<small>highest forecast AQI · the exact message issued</small></h2>", "<h2>Strongest warnings right now<small>highest forecast AQI in the next hours \\u00b7 the message issued</small></h2>", 1)
open(p, "w", encoding="utf-8").write(s)
print("patched")
