"""One-off patch: adds the 'Alert me' panel (browser notification + WhatsApp share) to the template."""
import os
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard_template.html")
s = open(p, encoding="utf-8").read()
assert "alertme" not in s

CSS = """
  .alertme{display:flex;gap:12px;flex-wrap:wrap;align-items:center;background:var(--panel);border:1px solid var(--line);border-left:5px solid var(--accent);
    border-radius:8px;padding:14px 16px;box-shadow:var(--shadow);margin-bottom:18px}
  .alertme h2{margin:0;font-size:16px}
  .alertme small{display:block;color:var(--muted);font-weight:400;font-size:12px;margin-top:2px}
  .alertme select,.alertme button,.btnwa{padding:10px 14px;border-radius:6px;border:1px solid var(--line);font:inherit;background:#fff;color:inherit}
  .alertme button.go{background:var(--accent);color:#fff;border-color:var(--accent);font-weight:600;cursor:pointer}
  .alertme .status{flex-basis:100%;font-size:13px;margin:0}
  .btnwa{display:inline-block;margin-top:8px;font-size:12px;text-decoration:none;color:#0b6b3a;border-color:#bfe3cf;background:#f2fbf6}
"""
s = s.replace("</style>", CSS + "</style>", 1)

HTML = """
  <section class="alertme" id="alertme">
    <div><h2>Get this warning on your phone</h2><small>Pick your city. When it is under a warning you get a notification on this device.</small></div>
    <select id="am-city" aria-label="City to alert"></select>
    <button class="go" id="am-go">Alert me</button>
    <p class="status" id="am-status" aria-live="polite"></p>
  </section>
"""
s = s.replace('  <section class="panel" style="padding-top:14px">', HTML + '\n  <section class="panel" style="padding-top:14px">', 1)

# WhatsApp share button on every card
s = s.replace("""      <div class="facts">""", """      <a class="btnwa" target="_blank" rel="noopener" href="https://wa.me/?text=${encodeURIComponent('Air quality warning - ' + w.city + ': forecast AQI ' + Math.round(w.worst_forecast_aqi) + ' (' + w.band.name + ') by ' + when + ' on ' + date + '. ' + w.band.act)}">Share this warning on WhatsApp</a>
      <div class="facts">""", 1)

JS = """
/* ---------- 'Alert me': a real browser notification for the chosen city ---------- */
section('alertme', () => {
  const sel = document.getElementById('am-city'), st = document.getElementById('am-status'), go = document.getElementById('am-go');
  const cities = [...new Set([...(D.live_latest||[]).map(r=>r.city), ...warned.map(w=>w.city)])].sort();
  sel.innerHTML = cities.map(c => `<option>${esc(c)}</option>`).join('');
  const KEY = 'airwatch_city';
  let saved = null; try { saved = localStorage.getItem(KEY); } catch(e) {}
  if (saved && cities.includes(saved)) sel.value = saved;

  const msgFor = (c) => {
    const w = warned.find(x => x.city === c);
    if (!w) return {warn:false, title:'No warning for ' + c, body:'Air quality in ' + c + ' is not forecast to cross AQI 150 in this run.'};
    const when = String(w.peak_forecast_for||'').slice(11,16);
    return {warn:true, title:'Air quality warning - ' + c,
            body:'Expected AQI ' + fmt(w.worst_forecast_aqi) + ' (' + w.band.name + ') by ' + when + '. ' + w.band.act};
  };
  const notify = (m) => {
    st.textContent = m.title + ' - ' + m.body;
    st.style.color = m.warn ? css('--severe') : css('--accent');
    if ('Notification' in window && Notification.permission === 'granted') {
      try { new Notification(m.title, {body: m.body}); } catch(e) {}
    }
  };
  go.addEventListener('click', async () => {
    try { localStorage.setItem(KEY, sel.value); } catch(e) {}
    let perm = 'unsupported';
    if ('Notification' in window) { try { perm = await Notification.requestPermission(); } catch(e) { perm = 'denied'; } }
    notify(msgFor(sel.value));
    if (perm !== 'granted') st.textContent += '  (Browser notifications are blocked or unavailable here - the message above is shown on the page instead.)';
  });
  if (saved && cities.includes(saved)) notify(msgFor(saved));
});

/* ---------- SVG helpers ---------- */"""
s = s.replace("\n/* ---------- SVG helpers ---------- */", JS, 1)
open(p, "w", encoding="utf-8").write(s)
print("patched")
