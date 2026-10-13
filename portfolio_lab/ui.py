"""שרת מקומי לסימולטור: `python3 -m portfolio_lab.ui [--port 8765]`.

מאזין ל-127.0.0.1 בלבד; ספריית התקנים בלבד; לא מחובר ל-app.py, ל-Airtable או ל-LLM.
"""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .simulator_view import DEFAULTS, build_simulator_view

PAGE = Path(__file__).with_name("ui_page.html")
MAX_BODY = 64 * 1024


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status, payload):
        self._send(status, json.dumps(payload, ensure_ascii=False, allow_nan=False).encode(), "application/json; charset=utf-8")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/defaults":
            self._json(200, DEFAULTS)
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/api/simulate":
            return self._json(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self._json(411, {"error": "Content-Length required"})
        if not 0 < length <= MAX_BODY:
            return self._json(413, {"error": "body too large"})
        try:
            params = json.loads(self.rfile.read(length))
            self._json(200, build_simulator_view(params))
        except (ValueError, TypeError, OverflowError) as error:
            self._json(400, {"error": str(error)})

    def log_message(self, *args):
        pass


def make_server(port=8765):
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Portfolio Lab — סימולטור מקומי")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    server = make_server(args.port)
    print(f"Portfolio Lab simulator: http://127.0.0.1:{server.server_address[1]}/  (Ctrl+C לעצירה)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
