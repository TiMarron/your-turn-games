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
