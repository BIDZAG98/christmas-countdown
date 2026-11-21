#!/usr/bin/env python3
"""Local-only Codex quota dashboard. Binds to loopback and never serves credentials."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import time
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 8765
USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
ALLOWED_HOSTS = {f"{HOST}:{PORT}", f"localhost:{PORT}"}
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}


class DashboardError(Exception):
    pass


def load_auth() -> tuple[str, str | None]:
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    auth_path = codex_home / "auth.json"
    try:
        auth = json.loads(auth_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DashboardError("Codex sign-in file not found. Sign in with Codex, then refresh.") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise DashboardError("Could not read Codex sign-in data. Check that Codex is signed in.") from exc

    tokens = auth.get("tokens") or {}
    access_token = tokens.get("access_token")
    account_id = tokens.get("account_id")
    if not isinstance(access_token, str) or not access_token:
        raise DashboardError("Codex sign-in data is incomplete. Run `codex login`, then refresh.")
    return access_token, account_id if isinstance(account_id, str) and account_id else None


def read_usage() -> dict:
    access_token, account_id = load_auth()
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}",
        "User-Agent": "CodexLocalUsageDashboard/1.0",
    }
    if account_id:
        headers["chatgpt-account-id"] = account_id

    request = urllib.request.Request(USAGE_URL, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise DashboardError("Codex sign-in expired. Run `codex login`, then refresh.") from exc
        if exc.code == 429:
            raise DashboardError("The usage service is rate limiting refreshes. Try again in a little while.") from exc
        raise DashboardError(f"The usage request failed (HTTP {exc.code}). Try refreshing later.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise DashboardError("Could not reach chatgpt.com. Check your connection and refresh.") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DashboardError("The usage service returned an unreadable response.") from exc

    rate_limit = data.get("rate_limit") or {}
    primary = sanitize_window(rate_limit.get("primary_window"))
    secondary = sanitize_window(rate_limit.get("secondary_window"))
    if not primary and not secondary:
        raise DashboardError("Codex returned no rate-limit window. Refresh later or check the VS Code extension log.")
    return {"primary": primary, "secondary": secondary, "updatedAt": int(time.time() * 1000)}


def sanitize_window(raw: object) -> dict | None:
    if not isinstance(raw, dict):
        return None
    try:
        used = float(raw["used_percent"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (used >= 0 and used <= 1000):
        return None

    window_seconds = as_positive_number(raw.get("limit_window_seconds"))
    reset_after = as_positive_number(raw.get("reset_after_seconds"))
    reset_at = as_positive_number(raw.get("reset_at"))
    if reset_after is None and reset_at is not None:
        reset_after = max(0, reset_at - time.time())
    reset_epoch = time.time() + reset_after if reset_after is not None else None
    return {
        "usedPercent": min(100, used),
        "windowSeconds": window_seconds,
        "resetAt": int(reset_epoch * 1000) if reset_epoch is not None else None,
    }


def as_positive_number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


class Handler(BaseHTTPRequestHandler):
    server_version = "CodexLocalDashboard/1.0"

    def log_message(self, _format: str, *args: object) -> None:
        # Do not log request details or account data to the terminal.
        return

    def send_headers(self, status: int, content_type: str, length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; connect-src 'self'; style-src 'self'; script-src 'self'; "
            "img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
        )
        self.end_headers()

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_headers(status, "application/json; charset=utf-8", len(body))
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.headers.get("Host", "") not in ALLOWED_HOSTS:
            self.send_json(403, {"error": "This dashboard is available only from this computer."})
            return
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://{host}" for host in ALLOWED_HOSTS}:
            self.send_json(403, {"error": "Cross-origin requests are not allowed."})
            return

        if self.path == "/api/usage":
            try:
                self.send_json(200, read_usage())
            except DashboardError as exc:
                self.send_json(503, {"error": str(exc)})
            return

        entry = STATIC_FILES.get(self.path)
        if not entry:
            self.send_json(404, {"error": "Not found."})
            return
        filename, content_type = entry
        body = (ROOT / filename).read_bytes()
        self.send_headers(200, content_type, len(body))
        self.wfile.write(body)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    print(f"Codex Usage is running locally at {url}")
    print("Keep this Terminal window open while you use the dashboard. Press Ctrl+C to stop.")
    if sys.platform == "darwin":
        subprocess.Popen(
            ["open", "-a", "Brave Browser", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        import webbrowser
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nCodex Usage stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
