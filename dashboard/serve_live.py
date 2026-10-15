"""
LIVE MODE for the warning board - the page re-checks every 10 seconds
================================================================================
Project : 23AID302 - Big Data Analytics

WHAT IT DOES
  Serves the warning board over http://localhost:8000 and builds the page FRESH
  from dashboard_data.json on every request. The page polls /api/version every
  10 seconds; the moment the pipeline publishes new data (dashboard_data.json
  changes) the page reloads itself with the new warnings.

  The pipeline publishes new data when a scoring cycle finishes:
      python scripts/run_hourly_cycle.py --once score --manage-docker
  (it re-exports from Hive into dashboard/dashboard_data.json).

HONEST LIMITS
  - The page checks every 10 s, but the numbers only change when a scoring cycle
    has finished and published; CAMS itself refreshes a few times a day.
  - Opened as a plain file (AirWatch_India.html) or on GitHub Pages the page is a
    static snapshot and says so in its badge.

RUN
    python dashboard/serve_live.py            # then open http://localhost:8000
================================================================================
"""
import json
import os
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DASH = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(DASH, "_src", "dashboard_template.html")
DATA = os.path.join(DASH, "dashboard_data.json")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000


def version():
    d = json.load(open(DATA, encoding="utf-8"))
    return {"generated_utc": d.get("generated_utc"), "observed_to": (d.get("run_window") or {}).get("observed_to"),
            "mtime": os.path.getmtime(DATA)}


def page():
    data = json.load(open(DATA, encoding="utf-8"))
    html = open(TEMPLATE, encoding="utf-8").read()
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    html = html.replace("/*__DASHBOARD_DATA__*/null", blob).replace("__BUILT_AT__", datetime.now().strftime("%d %b %Y %H:%M"))
    return html.encode("utf-8")


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            p = self.path.split("?")[0]
            if p in ("/", "/index.html"):
                self._send(200, page(), "text/html; charset=utf-8")
            elif p == "/api/version":
                self._send(200, json.dumps(version()).encode(), "application/json")
            else:
                self._send(404, b"not found", "text/plain")
        except Exception as e:
            self._send(500, str(e).encode(), "text/plain")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print(f"live warning board: http://localhost:{PORT}   (page checks every 10 s; Ctrl-C to stop)")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
