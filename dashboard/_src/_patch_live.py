"""One-off patch: live badge + 10 s polling in the dashboard template."""
import os
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard_template.html")
s = open(p, encoding="utf-8").read()
assert "live-badge" not in s

CSS = """
  .livebadge{display:inline-flex;align-items:center;gap:8px;font-size:12px;padding:5px 10px;border-radius:999px;border:1px solid var(--line);background:var(--panel);margin-top:6px}
  .livebadge i{width:9px;height:9px;border-radius:50%;background:#9aa5b1;display:inline-block}
  .livebadge.on i{background:#1e8e5a;animation:lp 1.4s infinite}
  .livebadge.off i{background:#c9342b}
  @keyframes lp{0%{opacity:1}50%{opacity:.25}100%{opacity:1}}
"""
s = s.replace("</style>", CSS + "</style>", 1)

s = s.replace('<div class="updated">Latest data hour<b class="mono" id="m-updated">—</b></div>',
              '<div class="updated">Latest data hour<b class="mono" id="m-updated">—</b><span class="livebadge" id="live-badge"><i></i><span id="live-text">Snapshot</span></span></div>', 1)
assert "live-badge" in s

JS = """
/* ---------- live mode: when served by dashboard/serve_live.py the page re-checks every 10 s ---------- */
(function(){
  const badge = document.getElementById('live-badge'), txt = document.getElementById('live-text');
  if (!badge || !D) return;
  const hh = () => new Date().toLocaleTimeString('en-GB');
  if (!/^https?:/.test(location.protocol)) { txt.textContent = 'Snapshot of the 1\\u201315 Oct run (open via serve_live.py for live mode)'; return; }
  const mine = D.generated_utc;
  async function tick(){
    try {
      const r = await fetch('/api/version?_=' + Date.now(), {cache:'no-store'});
      if (!r.ok) throw new Error(r.status);
      const v = await r.json();
      if (v.generated_utc && v.generated_utc !== mine) { txt.textContent = 'New data published - reloading\\u2026'; location.reload(); return; }
      badge.className = 'livebadge on';
      txt.textContent = 'LIVE \\u00b7 checked ' + hh() + ' (every 10 s) \\u00b7 data from ' + String(v.observed_to||'').slice(0,16);
    } catch (e) {
      badge.className = 'livebadge off';
      txt.textContent = 'Live server not reachable \\u00b7 last check ' + hh();
    }
  }
  tick(); setInterval(tick, 10000);
})();
"""
i = s.rindex("</script>")
s = s[:i] + JS + s[i:]
open(p, "w", encoding="utf-8").write(s)
print("patched")
