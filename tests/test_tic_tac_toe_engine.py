from pathlib import Path

import pytest

from harness.fake_match import FakeMatch
from harness.sandbox_runner import ReducerError

ENGINE = (Path(__file__).resolve().parents[1] / "games" / "tic-tac-toe" / "engine.py").read_text(encoding="utf-8")


def test_new_game_empty_board():
    m = FakeMatch(ENGINE)
    snap = m.snapshot()
    assert snap["board"] == [None] * 9
    assert snap["current_player"] == 0
    assert snap["phase"] == "playing"


def test_row_win_for_player_0():
    m = FakeMatch(ENGINE)
    m.apply(0, "place", {"cell": 0})   # X
    m.apply(1, "place", {"cell": 3})   # O
    m.apply(0, "place", {"cell": 1})   # X
    m.apply(1, "place", {"cell": 4})   # O
    snap = m.apply(0, "place", {"cell": 2})   # X completes top row
    assert snap["phase"] == "finished"
    assert snap["winner"] == 0


def test_draw():
    m = FakeMatch(ENGINE)
    # X O X / X O O / O X X  -> full board, no line
    # board[0..8] = X O X X O O O X X (5 X, 4 O)
    order = [(0, 0), (1, 1), (0, 2), (1, 4), (0, 3), (1, 5),
             (0, 7), (1, 6), (0, 8)]
    snap = None
    for seat, cell in order:
        snap = m.apply(seat, "place", {"cell": cell})
    assert snap["phase"] == "finished"
    assert snap["winner"] is None


def test_cannot_take_occupied_cell():
    m = FakeMatch(ENGINE)
    m.apply(0, "place", {"cell": 0})
    with pytest.raises(ReducerError):
        m.apply(1, "place", {"cell": 0})


def test_out_of_turn_rejected():
    m = FakeMatch(ENGINE)
    with pytest.raises(ReducerError):
        m.apply(1, "place", {"cell": 0})


def test_legal_actions_lists_empty_cells_for_current_player_only():
    m = FakeMatch(ENGINE)
    acts = m.legal_actions(0)
    assert acts == {"place": [{"cell": i} for i in range(9)]}
    assert m.legal_actions(1) == {}
