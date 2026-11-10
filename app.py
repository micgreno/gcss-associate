"""Start the local web app: static UI plus JSON API endpoints."""

from __future__ import annotations

import json
import mimetypes
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from api import MAX_REQUEST_BYTES, dispatch
from database import DB_PATH, connect


ROOT = Path(__file__).resolve().parent
UI_ROOT = ROOT / "ui"
STATIC_FILES = {
    "/assets/styles.css": UI_ROOT / "styles.css",
    "/assets/app.js": UI_ROOT / "app.js",
    "/assets/database.js": UI_ROOT / "database.js",
}
HTML_PAGES = {
    "/": UI_ROOT / "index.html",
    "/borrower": UI_ROOT / "index.html",
    "/database": UI_ROOT / "database.html",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "NorthstarTrainingApp/2"

    def send_json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_file(self, path: Path) -> None:
        try:
            payload = path.read_bytes()
        except FileNotFoundError:
            self.send_json(404, {"error": "Page not found."})
            return
        content_type, _ = mimetypes.guess_type(path.name)
        if path.suffix == ".js":
            content_type = "text/javascript"
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type or 'application/octet-stream'}; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler interface
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            status, payload = dispatch("GET", parsed.path, parsed.query)
            self.send_json(status, payload)
        elif parsed.path in HTML_PAGES:
            self.send_file(HTML_PAGES[parsed.path])
        elif parsed.path in STATIC_FILES:
            self.send_file(STATIC_FILES[parsed.path])
        elif parsed.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        else:
            self.send_json(404, {"error": "Page not found."})

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler interface
        parsed = urlparse(self.path)
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json(400, {"error": "Invalid request length."})
            return
        if content_length < 0 or content_length > MAX_REQUEST_BYTES:
            self.send_json(413, {"error": "The request must not exceed 20 KB."})
            return
        body = self.rfile.read(content_length)
        status, payload = dispatch("POST", parsed.path, parsed.query, body)
        self.send_json(status, payload)

    def log_message(self, format: str, *args) -> None:
        # Keep the local interview terminal readable while still showing errors.
        if len(args) >= 2 and str(args[1]).startswith(("4", "5")):
            super().log_message(format, *args)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run the Northstar Credit practical-assessment app")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    with closing(connect()) as db:
        db.execute("SELECT 1")
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Northstar Credit is running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Northstar Credit.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
