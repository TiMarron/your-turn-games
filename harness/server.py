"""Harness HTTP + WebSocket server (aiohttp): the platform's game API + live push.

One origin/port, one event loop. The HTTP API mirrors the platform; the WS route
/api/ws/{room}?token=seatN pushes {"type":"game_state",...} on connect and on
every action (mirroring the platform's HTTP-action -> WS-broadcast). FakeMatch
calls run in a thread executor (they spawn subprocesses) under an asyncio.Lock so
they never block the loop. The match token is the stub `seat{N}`.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from aiohttp import web

from harness.fake_match import FakeMatch
from harness.host_page import host_page_html
from harness.sandbox_runner import ReducerError

ROOM = "LOCAL"
TOKEN_TTL_MINUTES = 30


@dataclass
class Harness:
    source: str
    metadata: dict
    client_dir: Path
    match: FakeMatch = field(init=False)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    connections: dict = field(default_factory=dict, init=False)  # {WebSocketResponse: seat}

    def __post_init__(self):
        self.client_dir = Path(self.client_dir)
        self.match = FakeMatch(self.source, self.metadata.get("max_players", 2))


def _seat_from_token(token):
    if token and token.startswith("seat"):
        try:
            return int(token[len("seat"):])
        except ValueError:
            return None
    return None


def _token(request) -> str | None:
    auth = request.headers.get("Authorization", "")
    return auth[len("Bearer "):] if auth.startswith("Bearer ") else None


async def _run(harness: Harness, method: str, *args):
    """Run a (blocking, subprocess-spawning) FakeMatch method off the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: getattr(harness.match, method)(*args))


def _base_state(harness: Harness, snap: dict) -> dict:
    """Snapshot enriched with room-level fields (NOT your_seat — set per recipient)."""
    n = harness.metadata.get("max_players", 2)
    return {
        **snap,
        "room_code": ROOM,
        "engine_version": f"{harness.metadata.get('game_type', 'game')}@dev",
        "players": [{"seat": i, "username": f"player{i}"} for i in range(n)],
    }


@web.middleware
async def _cors(request, handler):
    if request.method == "OPTIONS":
        resp = web.Response(status=204)
    else:
        resp = await handler(request)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    return resp


async def _broadcast(harness: Harness, snap: dict) -> None:
    """Push game_state to every connected socket, personalized with its seat."""
    base = _base_state(harness, snap)
    for ws, seat in list(harness.connections.items()):
        try:
            await ws.send_json({"type": "game_state", **base, "your_seat": seat})
        except ConnectionError:
            harness.connections.pop(ws, None)


def make_app(harness: Harness) -> web.Application:
    async def match_token(request):
        try:
            seat = int(request.query.get("seat", "0"))
        except ValueError:
            return web.json_response({"detail": "invalid seat"}, status=400)
        return web.json_response({"token": f"seat{seat}", "expires_in_minutes": TOKEN_TTL_MINUTES})

    async def state(request):
        seat = _seat_from_token(_token(request))
        async with harness.lock:
            snap = await _run(harness, "snapshot")
        return web.json_response({**_base_state(harness, snap), "your_seat": seat})

    async def actions(request):
        seat = _seat_from_token(_token(request))
        async with harness.lock:
            acts = await _run(harness, "legal_actions", seat if seat is not None else 0)
        return web.json_response(acts)

    async def action(request):
        seat = _seat_from_token(_token(request))
        if seat is None:
            return web.json_response({"detail": "missing/invalid token"}, status=401)
        try:
            body = await request.json()
        except Exception:
            body = {}
        async with harness.lock:
            try:
                snap = await _run(harness, "apply", seat, body.get("type", ""), body.get("data", {}))
            except ReducerError as exc:
                return web.json_response({"detail": str(exc)}, status=400)
        await _broadcast(harness, snap)
        return web.json_response({**_base_state(harness, snap), "your_seat": seat})

    async def index(request):
        n = harness.metadata.get("max_players", 2)
        links = "".join(
            f'<li><a href="/play?seat={i}">Open as seat {i}</a></li>' for i in range(n)
        )
        title = harness.metadata.get("title", "game")
        return web.Response(
            content_type="text/html",
            text=f"<!doctype html><meta charset=utf-8><title>{title} — harness</title>"
                 f"<h1>{title}</h1><p>Open one tab per seat:</p><ul>{links}</ul>",
        )

    async def play(request):
        try:
            seat = int(request.query.get("seat", "0"))
        except ValueError:
            return web.json_response({"detail": "invalid seat"}, status=400)
        return web.Response(content_type="text/html",
                            text=host_page_html(harness.metadata.get("title", "game"), seat, ROOM))

    async def client_static(request):
        rel = request.match_info.get("tail", "") or "index.html"
        root = harness.client_dir.resolve()
        target = (root / rel).resolve()
        if target != root and not target.is_relative_to(root):
            return web.json_response({"detail": "forbidden"}, status=403)
        if not target.is_file():
            return web.json_response({"detail": "no such file"}, status=404)
        return web.FileResponse(target)

    async def websocket(request):
        seat = _seat_from_token(request.query.get("token"))
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        harness.connections[ws] = seat
        try:
            async with harness.lock:
                snap = await _run(harness, "snapshot")
            await ws.send_json({"type": "game_state", **_base_state(harness, snap), "your_seat": seat})
            async for _msg in ws:
                pass
        finally:
            harness.connections.pop(ws, None)
        return ws

    app = web.Application(middlewares=[_cors])
    app.router.add_post("/api/games/{room}/match-token", match_token)
    app.router.add_get("/api/games/{room}/state", state)
    app.router.add_get("/api/games/{room}/actions", actions)
    app.router.add_post("/api/games/{room}/action", action)
    app.router.add_get("/api/ws/{room}", websocket)
    app.router.add_get("/", index)
    app.router.add_get("/play", play)
    app.router.add_get("/client/{tail:.*}", client_static)
    return app
