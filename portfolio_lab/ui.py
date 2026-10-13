"""שרת מקומי לסימולטור: `python3 -m portfolio_lab.ui [--port 8765]`.

כלי מחקר מקומי בלבד — לא ממשק פרודקשן. מאזין ל-127.0.0.1 בלבד (אין אפשרות --host),
ספריית התקנים בלבד, לא מחובר ל-app.py, ל-Airtable או ל-LLM, ללא אימות כי אין נתונים רגישים.
מסרב לעלות בסביבת פרודקשן (ראו `production_reason`).
"""

import argparse
import json
import os
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .simulator_view import DEFAULTS, build_simulator_view

PAGE = Path(__file__).with_name("ui_page.html")
MAX_BODY = 64 * 1024
REQUEST_TIMEOUT = 10  # שניות; מגן מפני חיבורים תלויים (slowloris)
_COMPUTE = threading.BoundedSemaphore(2)  # סימולציה אחת ~0.3 שנ' במקרה הגרוע; מגביל עומס CPU
_PRODUCTION_ENV = ("RENDER", "RENDER_SERVICE_ID", "DYNO", "KUBERNETES_SERVICE_HOST", "GUNICORN_CMD_ARGS")
_PRODUCTION_VALUES = {"production", "prod"}


def production_reason(environ=None):
    """סיבה לסירוב להרצה (סביבת פרודקשן/פריסה), או None."""
    env = os.environ if environ is None else environ
    for name in _PRODUCTION_ENV:
        if env.get(name):
            return f"{name} is set"
    for name in ("ENV", "APP_ENV", "FLASK_ENV", "ENVIRONMENT"):
        if str(env.get(name, "")).lower() in _PRODUCTION_VALUES:
            return f"{name}={env[name]}"
    return None


class Handler(BaseHTTPRequestHandler):
    timeout = REQUEST_TIMEOUT
    server_version = "PortfolioLabLocal"
    sys_version = ""

    def _allowed_hosts(self):
        port = self.server.server_address[1]
        return {f"127.0.0.1:{port}", f"localhost:{port}"}

    def _send(self, status, body, content_type, nonce=None):
        csp = "default-src 'none'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
        if nonce:
            csp += f"; script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'"
        self.send_response(status)
        for key, value in (("Content-Type", content_type), ("Content-Length", str(len(body))), ("Cache-Control", "no-store"),
                           ("X-Content-Type-Options", "nosniff"), ("X-Frame-Options", "DENY"),
                           ("Referrer-Policy", "no-referrer"), ("Content-Security-Policy", csp)):
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status, payload):
        self._send(status, json.dumps(payload, ensure_ascii=False, allow_nan=False).encode(), "application/json; charset=utf-8")

    def _guard(self):
        """הגנת DNS-rebinding: Host חייב להיות loopback; Origin (אם נשלח) חייב להיות אותו מקור."""
        if self.headers.get("Host") not in self._allowed_hosts():
            self._json(403, {"error": "forbidden host"})
            return False
        origin = self.headers.get("Origin")
        if origin is not None and origin not in {f"http://{h}" for h in self._allowed_hosts()}:
            self._json(403, {"error": "forbidden origin"})
            return False
        return True

    def do_GET(self):
        if not self._guard():
            return
        path = urlsplit(self.path).path
        if path in ("/", "/index.html"):
            nonce = secrets.token_urlsafe(16)
            html = PAGE.read_text(encoding="utf-8").replace("__NONCE__", nonce)
            self._send(200, html.encode(), "text/html; charset=utf-8", nonce)
        elif path == "/api/defaults":
            self._json(200, DEFAULTS)
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if not self._guard():
            return
        if urlsplit(self.path).path != "/api/simulate":
            return self._json(404, {"error": "not found"})
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            return self._json(415, {"error": "Content-Type must be application/json"})
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self._json(411, {"error": "Content-Length required"})
        if not 0 < length <= MAX_BODY:
            return self._json(413, {"error": "body too large"})
        try:
            params = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError):
            return self._json(400, {"error": "invalid JSON"})
        if not _COMPUTE.acquire(timeout=REQUEST_TIMEOUT):
            return self._json(503, {"error": "busy"})
        try:
            self._json(200, build_simulator_view(params))
        except (ValueError, TypeError, OverflowError, KeyError) as error:
            self._json(400, {"error": str(error)})
        except Exception:  # לא חושפים פרטים פנימיים
            self._json(500, {"error": "internal error"})
        finally:
            _COMPUTE.release()

    def log_message(self, *args):
        pass


def make_server(port=8765):
    if not isinstance(port, int) or not 0 <= port <= 65535:
        raise ValueError("port must be 0-65535")
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Portfolio Lab — סימולטור מקומי (מחקר בלבד, לא פרודקשן)")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    reason = production_reason()
    if reason:
        raise SystemExit(f"refusing to start: production-like environment ({reason}); this is a local research tool")
    server = make_server(args.port)
    print(f"Portfolio Lab simulator (LOCAL RESEARCH ONLY): http://127.0.0.1:{server.server_address[1]}/  (Ctrl+C לעצירה)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
