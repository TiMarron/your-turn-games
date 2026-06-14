"""The SDK is a copyable file; guard its shape and (later) that copies match."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT / "sdk" / "client.js"


def test_sdk_exists_and_exports_connect():
    text = SDK.read_text(encoding="utf-8")
    assert "export function connect(" in text
    assert "WebSocket(" in text
    assert "/api/ws/" in text
    assert "game_ended" in text
    assert 'method: "POST"' in text  # sendAction posts moves over HTTP


def test_tic_tac_toe_sdk_copy_matches_canonical():
    canonical = SDK.read_text(encoding="utf-8")
    copy = (ROOT / "games" / "tic-tac-toe" / "client" / "sdk.js").read_text(encoding="utf-8")
    assert copy == canonical, "games/tic-tac-toe/client/sdk.js is out of sync with sdk/client.js"


def test_template_sdk_copy_matches_canonical():
    canonical = SDK.read_text(encoding="utf-8")
    copy = (ROOT / "template" / "client" / "sdk.js").read_text(encoding="utf-8")
    assert copy == canonical, "template/client/sdk.js is out of sync with sdk/client.js"
