from pathlib import Path

import pytest

from harness.fake_match import FakeMatch
from harness.sandbox_runner import ReducerError

ENGINE = (Path(__file__).resolve().parents[1] / "games" / "infinite-xo" / "engine.py").read_text(encoding="utf-8")


def play(m, cells):
    """Apply `place` for each (x, y), alternating seats starting from seat 0."""
    snap = None
    for i, (x, y) in enumerate(cells):
        snap = m.apply(i % 2, "place", {"x": x, "y": y})
    return snap


def interleave(x_cells, o_cells):
    """Merge X and O moves into one alternating sequence (X first)."""
    out = []
    for i, xc in enumerate(x_cells):
        out.append(xc)
        if i < len(o_cells):
            out.append(o_cells[i])
    return out


def row(n, y=0, x0=0):
    return [(x0 + i, y) for i in range(n)]


# --- start of game ---------------------------------------------------------

def test_new_game_is_empty_and_x_moves_first():
    snap = FakeMatch(ENGINE).snapshot()
    assert snap["cells"] == {}
    assert snap["phase"] == "playing"
    assert snap["winner"] is None
    assert snap["move_number"] == 0
    assert snap["current_player"] == 0
    assert snap["last_move"] is None
    assert snap["win_line"] is None


def test_default_win_length_is_five():
    assert FakeMatch(ENGINE).snapshot()["win_length"] == 5


def test_win_length_comes_from_config():
    assert FakeMatch(ENGINE, config={"win_length": 4}).snapshot()["win_length"] == 4


@pytest.mark.parametrize("bad", [2, 0, -1, True, 4.0, "5", None])
def test_invalid_win_length_is_rejected(bad):
    with pytest.raises(ReducerError):
        FakeMatch(ENGINE, config={"win_length": bad})


# --- placing marks ---------------------------------------------------------

def test_place_records_mark_and_passes_turn():
    m = FakeMatch(ENGINE)
    snap = m.apply(0, "place", {"x": 3, "y": -2})
    assert snap["cells"] == {"3,-2": 0}
    assert snap["last_move"] == [3, -2]
    assert snap["move_number"] == 1
    assert snap["current_player"] == 1
    snap = m.apply(1, "place", {"x": -7, "y": 40})
    assert snap["cells"] == {"3,-2": 0, "-7,40": 1}
    assert snap["current_player"] == 0


def test_far_away_cells_are_allowed():
    m = FakeMatch(ENGINE)
    snap = m.apply(0, "place", {"x": 10000, "y": -10000})
    assert snap["cells"] == {"10000,-10000": 0}


@pytest.mark.parametrize("data", [
    {"x": 10001, "y": 0},
    {"x": 0, "y": -10001},
    {"x": 1.5, "y": 0},
    {"x": "1", "y": 0},
    {"x": True, "y": 0},
    {"x": 0},
    {"y": 0},
    {},
])
def test_invalid_coordinates_raise(data):
    m = FakeMatch(ENGINE)
    with pytest.raises(ReducerError):
        m.apply(0, "place", data)


def test_unknown_action_raises():
    m = FakeMatch(ENGINE)
    with pytest.raises(ReducerError):
        m.apply(0, "pass", {})


def test_out_of_turn_raises():
    m = FakeMatch(ENGINE)
    with pytest.raises(ReducerError):
        m.apply(1, "place", {"x": 0, "y": 0})


def test_occupied_cell_raises():
    m = FakeMatch(ENGINE)
    m.apply(0, "place", {"x": 0, "y": 0})
    with pytest.raises(ReducerError):
        m.apply(1, "place", {"x": 0, "y": 0})


# --- legal_actions ---------------------------------------------------------

def test_first_move_offers_the_origin():
    m = FakeMatch(ENGINE)
    assert m.legal_actions(0) == {"place": [{"x": 0, "y": 0}]}
    assert m.legal_actions(1) == {}


def test_legal_actions_are_free_cells_next_to_marks():
    m = FakeMatch(ENGINE)
    m.apply(0, "place", {"x": 5, "y": 5})
    offered = m.legal_actions(1)["place"]
    expected = [{"x": 5 + dx, "y": 5 + dy}
                for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0)]
    assert sorted(offered, key=lambda c: (c["x"], c["y"])) == sorted(expected, key=lambda c: (c["x"], c["y"]))
    assert m.legal_actions(0) == {}


# --- winning ---------------------------------------------------------------

def _play_x_line(x_cells, win_length=None):
    """X plays x_cells; O plays harmless far-apart cells that never line up."""
    o_cells = [(1000 + 10 * i, 1000) for i in range(len(x_cells))]
    m = FakeMatch(ENGINE, config={"win_length": win_length} if win_length else None)
    return m, interleave(x_cells, o_cells)


@pytest.mark.parametrize("name,cells", [
    ("horizontal", [(i, 0) for i in range(5)]),
    ("vertical", [(0, i) for i in range(5)]),
    ("diagonal", [(i, i) for i in range(5)]),
    ("anti-diagonal", [(i, -i) for i in range(5)]),
    ("negative coords", [(-3 - i, -4 - i) for i in range(5)]),
])
def test_five_in_a_row_wins_in_every_direction(name, cells):
    m, seq = _play_x_line(cells)
    snap = play(m, seq[:-1] if len(seq) % 2 == 0 else seq)
    assert snap["phase"] == "finished"
    assert snap["winner"] == 0
    assert snap["current_player"] == -1
    assert sorted(map(tuple, snap["win_line"])) == sorted(cells)


def test_four_in_a_row_does_not_win_by_default():
    m, seq = _play_x_line(row(4))
    snap = play(m, seq[:7])
    assert snap["phase"] == "playing"
    assert snap["winner"] is None
    assert snap["win_line"] is None


def test_four_in_a_row_wins_when_win_length_is_four():
    m, seq = _play_x_line(row(4), win_length=4)
    snap = play(m, seq[:7])
    assert snap["phase"] == "finished"
    assert snap["winner"] == 0


def test_o_can_win_too():
    m = FakeMatch(ENGINE)
    x_cells = [(1000 + 10 * i, 1000) for i in range(5)]
    seq = interleave(x_cells, row(5))
    snap = play(m, seq)
    assert snap["winner"] == 1
    assert snap["current_player"] == -1


def test_more_than_five_in_a_row_wins():
    # X builds 0,1,2,3 and 5, then fills 4 -> an unbroken run of six.
    x_cells = [(0, 0), (1, 0), (2, 0), (3, 0), (5, 0), (4, 0)]
    o_cells = [(1000 + 10 * i, 1000) for i in range(5)]
    m = FakeMatch(ENGINE)
    snap = play(m, interleave(x_cells, o_cells))
    assert snap["winner"] == 0
    assert sorted(map(tuple, snap["win_line"])) == [(i, 0) for i in range(6)]


def test_opponent_mark_breaks_the_line():
    # X: 0,1,3,4 with O sitting on (2,0) -> no five.
    x_cells = [(0, 0), (1, 0), (3, 0), (4, 0)]
    o_cells = [(2, 0), (1000, 1000), (2000, 1000), (3000, 1000)]
    m = FakeMatch(ENGINE)
    snap = play(m, interleave(x_cells, o_cells))
    assert snap["phase"] == "playing"
    assert snap["winner"] is None


def test_no_moves_after_game_over():
    m, seq = _play_x_line(row(5))
    play(m, seq[:9])
    assert m.snapshot()["phase"] == "finished"
    assert m.legal_actions(0) == {}
    assert m.legal_actions(1) == {}
    with pytest.raises(ReducerError):
        m.apply(1, "place", {"x": 50, "y": 50})
