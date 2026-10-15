"""
================================================================================
PHASE 10 (build) - EMBED THE EXPORTED DATA INTO THE DASHBOARD PAGE
================================================================================
Project : 23AID302 - Big Data Analytics

Reads ../dashboard_data.json (written by export_dashboard_data.py from the Hive
serving layer) and inlines it into dashboard_template.html, producing the ONE
file to open:

    dashboard/AirWatch_India.html

WHY THE TEMPLATE LIVES IN _src/
  The template contains `const D = null` - it has no data and renders as an
  empty shell on purpose. When it sat next to the built page it was the file
  people opened first, and "everything looks blank" was the result. Keeping it
  out of sight leaves exactly one obvious file to open.

WHY INLINE RATHER THAN fetch()
  A file opened by double-click is served from file://, where browsers block
  fetch() of a sibling JSON. Inlining means the same page works opened locally,
  hosted, or published as an artifact - one file, no server, no CORS, and no
  external script that can fail to load.

RUN
    python _src/build_dashboard.py         (from the dashboard/ folder)
================================================================================
"""
import json
import os
from datetime import datetime

SRC = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.dirname(SRC)

data = json.load(open(os.path.join(DASH, "dashboard_data.json"), encoding="utf-8"))
tpl = open(os.path.join(SRC, "dashboard_template.html"), encoding="utf-8").read()

# </script> inside a JSON string would end the tag early; escape defensively.
blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
html = tpl.replace("/*__DASHBOARD_DATA__*/null", blob)
html = html.replace("__BUILT_AT__", datetime.now().strftime("%d %b %Y %H:%M"))

out = os.path.join(DASH, "AirWatch_India.html")
open(out, "w", encoding="utf-8").write(html)
print(f"wrote {out}  ({len(html)/1024:.0f} KB)")
