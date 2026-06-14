"""Harness HTTP + WS server tests (aiohttp)."""
import pytest
import pytest_asyncio
from aiohttp.test_utils import TestClient, TestServer

from harness.server import Harness, make_app
from tests.conftest import TURN_REDUCER

META = {"game_type": "turn", "title": "Turn", "author": "Tester",
        "min_players": 2, "max_players": 2}


@pytest_asyncio.fixture
async def client(tmp_path):
    client_dir = tmp_path / "client"
    client_dir.mkdir()
    (client_dir / "index.html").write_text("<!doctype html><title>c</title>hi", encoding="utf-8")
    harness = Harness(source=TURN_REDUCER, metadata=META, client_dir=client_dir)
    cl = TestClient(TestServer(make_app(harness)))
    await cl.start_server()
    yield cl
    await cl.close()


async def test_match_token_returns_seat_token(client):
    r = await client.post("/api/games/LOCAL/match-token?seat=0")
    assert r.status == 200
    body = await r.json()
    assert body["token"] == "seat0"
    assert body["expires_in_minutes"] > 0


async def test_state_has_your_seat(client):
    tok = (await (await client.post("/api/games/LOCAL/match-token?seat=0")).json())["token"]
    r = await client.get("/api/games/LOCAL/state", headers={"Authorization": f"Bearer {tok}"})
    assert r.status == 200
    snap = await r.json()
    assert snap["current_player"] == 0
    assert snap["your_seat"] == 0


async def test_play_to_win_over_http(client):
    t0 = (await (await client.post("/api/games/LOCAL/match-token?seat=0")).json())["token"]
    t1 = (await (await client.post("/api/games/LOCAL/match-token?seat=1")).json())["token"]
    h0 = {"Authorization": f"Bearer {t0}", "Content-Type": "application/json"}
    h1 = {"Authorization": f"Bearer {t1}", "Content-Type": "application/json"}
    await client.post("/api/games/LOCAL/action", headers=h0, json={"type": "inc", "data": {}})
    await client.post("/api/games/LOCAL/action", headers=h1, json={"type": "inc", "data": {}})
    r = await client.post("/api/games/LOCAL/action", headers=h0, json={"type": "inc", "data": {}})
    snap = await r.json()
    assert snap["phase"] == "finished"
    assert snap["winner"] == 0


async def test_illegal_move_returns_400(client):
    t1 = (await (await client.post("/api/games/LOCAL/match-token?seat=1")).json())["token"]
    r = await client.post("/api/games/LOCAL/action",
                          headers={"Authorization": f"Bearer {t1}", "Content-Type": "application/json"},
                          json={"type": "inc", "data": {}})
    assert r.status == 400


async def test_action_without_token_returns_401(client):
    r = await client.post("/api/games/LOCAL/action", json={"type": "inc", "data": {}})
    assert r.status == 401


async def test_actions_endpoint(client):
    t0 = (await (await client.post("/api/games/LOCAL/match-token?seat=0")).json())["token"]
    r = await client.get("/api/games/LOCAL/actions", headers={"Authorization": f"Bearer {t0}"})
    assert r.status == 200
    assert await r.json() == {"inc": [{}]}


async def test_cors_header_present(client):
    r = await client.post("/api/games/LOCAL/match-token?seat=0")
    assert r.headers.get("Access-Control-Allow-Origin") == "*"


async def test_options_preflight(client):
    r = await client.options("/api/games/LOCAL/action")
    assert r.status in (200, 204)
    assert r.headers.get("Access-Control-Allow-Origin") == "*"


async def test_play_page_has_sandboxed_iframe(client):
    r = await client.get("/play?seat=0")
    html = await r.text()
    assert 'sandbox="allow-scripts"' in html
    assert "/client/index.html" in html
    assert "seat0" in html


async def test_static_client_served(client):
    r = await client.get("/client/index.html")
    assert r.status == 200
    assert "hi" in await r.text()


async def test_ws_initial_state_and_live_broadcast(client):
    t0 = (await (await client.post("/api/games/LOCAL/match-token?seat=0")).json())["token"]
    t1 = (await (await client.post("/api/games/LOCAL/match-token?seat=1")).json())["token"]

    ws0 = await client.ws_connect(f"/api/ws/LOCAL?token={t0}")
    ws1 = await client.ws_connect(f"/api/ws/LOCAL?token={t1}")

    # Each socket gets an initial game_state with its own seat.
    init0 = await ws0.receive_json()
    init1 = await ws1.receive_json()
    assert init0["type"] == "game_state" and init0["your_seat"] == 0
    assert init1["type"] == "game_state" and init1["your_seat"] == 1
    assert init0["current_player"] == 0

    # Seat 0 plays over HTTP -> BOTH sockets receive a pushed game_state.
    await client.post("/api/games/LOCAL/action",
                      headers={"Authorization": f"Bearer {t0}", "Content-Type": "application/json"},
                      json={"type": "inc", "data": {}})
    push0 = await ws0.receive_json()
    push1 = await ws1.receive_json()
    assert push0["type"] == "game_state" and push0["current_player"] == 1
    assert push1["type"] == "game_state" and push1["current_player"] == 1
    assert push0["your_seat"] == 0 and push1["your_seat"] == 1   # personalized

    await ws0.close()
    await ws1.close()
