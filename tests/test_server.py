import json
import threading
import urllib.request
import urllib.error

import pytest

from harness.server import Harness, serve
from tests.conftest import TURN_REDUCER

META = {"game_type": "turn", "title": "Turn", "author": "Tester",
        "min_players": 2, "max_players": 2}


@pytest.fixture
def base_url(tmp_path):
    client_dir = tmp_path / "client"
    client_dir.mkdir()
    (client_dir / "index.html").write_text("<!doctype html><title>c</title>hi", encoding="utf-8")
    harness = Harness(source=TURN_REDUCER, metadata=META, client_dir=client_dir)
    httpd = serve(harness, host="127.0.0.1", port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()


def _req(method, url, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as r:
        return r.status, json.loads(r.read().decode()), dict(r.headers)


def test_match_token_returns_seat_token(base_url):
    status, body, _ = _req("POST", f"{base_url}/api/games/LOCAL/match-token?seat=0")
    assert status == 200
    assert body["token"] == "seat0"
    assert body["expires_in_minutes"] > 0


def test_state_and_play_to_win(base_url):
    _, t0, _ = _req("POST", f"{base_url}/api/games/LOCAL/match-token?seat=0")
    _, t1, _ = _req("POST", f"{base_url}/api/games/LOCAL/match-token?seat=1")
    tok0, tok1 = t0["token"], t1["token"]

    status, snap, _ = _req("GET", f"{base_url}/api/games/LOCAL/state", token=tok0)
    assert status == 200
    assert snap["current_player"] == 0
    assert snap["your_seat"] == 0

    _req("POST", f"{base_url}/api/games/LOCAL/action", token=tok0, body={"type": "inc", "data": {}})
    _req("POST", f"{base_url}/api/games/LOCAL/action", token=tok1, body={"type": "inc", "data": {}})
    _, snap, _ = _req("POST", f"{base_url}/api/games/LOCAL/action", token=tok0, body={"type": "inc", "data": {}})
    assert snap["phase"] == "finished"
    assert snap["winner"] == 0


def test_illegal_move_returns_400(base_url):
    _, t1, _ = _req("POST", f"{base_url}/api/games/LOCAL/match-token?seat=1")
    with pytest.raises(urllib.error.HTTPError) as exc:
        _req("POST", f"{base_url}/api/games/LOCAL/action", token=t1["token"],
             body={"type": "inc", "data": {}})   # seat 1 out of turn
    assert exc.value.code == 400


def test_actions_endpoint(base_url):
    _, t0, _ = _req("POST", f"{base_url}/api/games/LOCAL/match-token?seat=0")
    status, acts, _ = _req("GET", f"{base_url}/api/games/LOCAL/actions", token=t0["token"])
    assert status == 200
    assert acts == {"inc": [{}]}


def test_cors_header_present(base_url):
    _, _, headers = _req("POST", f"{base_url}/api/games/LOCAL/match-token?seat=0")
    assert headers.get("Access-Control-Allow-Origin") == "*"


def test_play_page_has_sandboxed_iframe(base_url):
    import urllib.request
    with urllib.request.urlopen(f"{base_url}/play?seat=0") as r:
        html = r.read().decode()
    assert 'sandbox="allow-scripts"' in html
    assert "/client/index.html" in html
    assert "seat0" in html  # the seat's match token is embedded for init
