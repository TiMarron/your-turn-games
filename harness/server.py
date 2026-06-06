"""Stdlib HTTP server: the platform's game API, backed by one FakeMatch.

Routes (mirror the platform):
  POST /api/games/{room}/match-token?seat=N -> {"token":"seatN","expires_in_minutes":30}
  GET  /api/games/{room}/state              -> snapshot + room_code/your_seat/players
  GET  /api/games/{room}/actions            -> legal_actions(seat)
  POST /api/games/{room}/action             -> apply(seat, type, data) -> snapshot (400 on rule error)
  GET  /                                     -> seat picker page
  GET  /play?seat=N                          -> host page (sandboxed iframe)
  GET  /client/...                           -> author's client bundle (static)
CORS: allow any origin (dev) so the sandboxed opaque-origin iframe can call us.
The match token is a stub `seat{N}`; the seat is read back from the bearer token.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from harness.fake_match import FakeMatch
from harness.sandbox_runner import ReducerError
from harness.host_page import host_page_html

ROOM = "LOCAL"
TOKEN_TTL_MINUTES = 30


@dataclass
class Harness:
    source: str
    metadata: dict
    client_dir: Path
    match: FakeMatch = field(init=False)

    def __post_init__(self):
        self.client_dir = Path(self.client_dir)
        self.match = FakeMatch(self.source, self.metadata.get("max_players", 2))

    def reset(self):
        self.match = FakeMatch(self.source, self.metadata.get("max_players", 2))


def _seat_from_token(token: str | None) -> int | None:
    if token and token.startswith("seat"):
        try:
            return int(token[len("seat"):])
        except ValueError:
            return None
    return None


def make_handler(harness: Harness):
    class Handler(BaseHTTPRequestHandler):
        def _cors(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")

        def _json(self, status: int, payload: dict):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _html(self, status: int, html: str):
            body = html.encode()
            self.send_response(status)
            self._cors()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _token(self) -> str | None:
            auth = self.headers.get("Authorization", "")
            return auth[len("Bearer "):] if auth.startswith("Bearer ") else None

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length", 0) or 0)
            if not length:
                return {}
            try:
                return json.loads(self.rfile.read(length).decode())
            except json.JSONDecodeError:
                return {}

        def _snapshot_for(self, seat: int | None) -> dict:
            snap = harness.match.snapshot()
            snap["room_code"] = ROOM
            snap["your_seat"] = seat
            snap["engine_version"] = f"{harness.metadata.get('game_type', 'game')}@dev"
            snap["players"] = [
                {"seat": i, "username": f"player{i}"}
                for i in range(harness.metadata.get("max_players", 2))
            ]
            return snap

        def log_message(self, *args):
            pass

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self):
            parsed = urlparse(self.path)
            path, qs = parsed.path, parse_qs(parsed.query)

            if path == "/":
                links = "".join(
                    f'<li><a href="/play?seat={i}">Open as seat {i} '
                    f'({"X" if i == 0 else "O"})</a></li>'
                    for i in range(harness.metadata.get("max_players", 2))
                )
                self._html(200, f"<!doctype html><meta charset=utf-8>"
                                f"<title>{harness.metadata.get('title','game')} — harness</title>"
                                f"<h1>{harness.metadata.get('title','game')}</h1>"
                                f"<p>Open one tab per seat:</p><ul>{links}</ul>")
                return

            if path == "/play":
                seat = int((qs.get("seat", ["0"])[0]))
                self._html(200, host_page_html(harness.metadata.get("title", "game"), seat, ROOM))
                return

            if path.startswith("/client/"):
                self._serve_client(path[len("/client/"):])
                return

            if re.fullmatch(r"/api/games/([^/]+)/state", path):
                self._json(200, self._snapshot_for(_seat_from_token(self._token())))
                return

            if re.fullmatch(r"/api/games/([^/]+)/actions", path):
                seat = _seat_from_token(self._token())
                self._json(200, harness.match.legal_actions(seat if seat is not None else 0))
                return

            self._json(404, {"detail": "not found"})

        def do_POST(self):
            parsed = urlparse(self.path)
            path, qs = parsed.path, parse_qs(parsed.query)

            if re.fullmatch(r"/api/games/([^/]+)/match-token", path):
                seat = int(qs.get("seat", ["0"])[0])
                self._json(200, {"token": f"seat{seat}", "expires_in_minutes": TOKEN_TTL_MINUTES})
                return

            if re.fullmatch(r"/api/games/([^/]+)/action", path):
                seat = _seat_from_token(self._token())
                if seat is None:
                    self._json(401, {"detail": "missing/invalid token"})
                    return
                body = self._body()
                try:
                    harness.match.apply(seat, body.get("type", ""), body.get("data", {}))
                except ReducerError as exc:
                    self._json(400, {"detail": str(exc)})
                    return
                self._json(200, self._snapshot_for(seat))
                return

            self._json(404, {"detail": "not found"})

        def _serve_client(self, rel: str):
            rel = rel or "index.html"
            root = harness.client_dir.resolve()
            target = (root / rel).resolve()
            if not str(target).startswith(str(root)):
                self._json(403, {"detail": "forbidden"})
                return
            if not target.is_file():
                self._json(404, {"detail": "no such file"})
                return
            ctype = ("text/html; charset=utf-8" if target.suffix == ".html"
                     else "application/javascript" if target.suffix == ".js"
                     else "text/css" if target.suffix == ".css"
                     else "application/octet-stream")
            data = target.read_bytes()
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def serve(harness: Harness, host: str = "127.0.0.1", port: int = 8080) -> ThreadingHTTPServer:
    """Build (do not start) a ThreadingHTTPServer. Caller runs serve_forever()."""
    return ThreadingHTTPServer((host, port), make_handler(harness))
