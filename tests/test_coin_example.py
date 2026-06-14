"""Structural tests for the coin Vue example (no npm build run here)."""
import json
from pathlib import Path

import pytest

from harness.fake_match import FakeMatch
from harness.sandbox_runner import ReducerError
from harness.validate import validate

ROOT = Path(__file__).resolve().parents[1]
COIN = ROOT / "games" / "coin"
ENGINE = (COIN / "engine.py").read_text(encoding="utf-8")
META = json.loads((COIN / "game.json").read_text(encoding="utf-8"))


def test_coin_reducer_is_contract_valid():
    assert validate(ENGINE) == []


def test_coin_plays_to_a_loss_for_last_taker():
    m = FakeMatch(ENGINE)
    m.apply(0, "take", {"n": 2})          # 3 -> 1, seat 1's turn
    snap = m.apply(1, "take", {"n": 1})   # 1 -> 0, seat 1 took the last -> seat 0 wins
    assert snap["phase"] == "finished"
    assert snap["winner"] == 0


def test_coin_rejects_out_of_turn():
    m = FakeMatch(ENGINE)
    with pytest.raises(ReducerError):
        m.apply(1, "take", {"n": 1})


def test_coin_game_json_has_build_manifest():
    assert META["game_type"] == "coin"
    assert META["build"]["output"] == "client/dist"
    assert "npm" in META["build"]["command"]


def test_coin_client_uses_vite_vue_and_sdk():
    client = COIN / "client"
    pkg = json.loads((client / "package.json").read_text(encoding="utf-8"))
    assert "vue" in pkg["dependencies"]
    assert "vite" in pkg["devDependencies"]
    assert pkg["scripts"]["build"] == "vite build"

    vite_cfg = (client / "vite.config.ts").read_text(encoding="utf-8")
    assert 'base: "./"' in vite_cfg

    main_ts = (client / "src" / "main.ts").read_text(encoding="utf-8")
    assert 'from "./sdk.js"' in main_ts
    assert "connect({ onState" in main_ts

    app_vue = (client / "src" / "App.vue").read_text(encoding="utf-8")
    assert 'sendAction("take"' in app_vue


def test_coin_client_sdk_copy_matches_canonical():
    canonical = (ROOT / "sdk" / "client.js").read_text(encoding="utf-8")
    copy = (COIN / "client" / "src" / "sdk.js").read_text(encoding="utf-8")
    assert copy == canonical, "games/coin/client/src/sdk.js is out of sync with sdk/client.js"
