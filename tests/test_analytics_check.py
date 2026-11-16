"""python -m harness --analytics: a random game, then analytics.py over it."""
import json

import pytest

from harness import analytics_check
from harness.__main__ import main
from harness.analytics_check import check_analytics, random_playthrough
from tests.conftest import TURN_REDUCER

GOOD = (
    "def on_step(p, pl, t, d, n, c):\n"
    "    return [{'name': 'inc', 'props': {'by': pl}}]\n"
    "def on_finish(f, c):\n"
    "    return [{'seat': s, 'props': {'count': f['count'][s]}} for s in range(c['n_players'])]\n"
)


def make_game_dir(tmp_path, analytics=GOOD, engine=TURN_REDUCER):
    game = tmp_path / "g"
    game.mkdir(parents=True)
    (game / "engine.py").write_text(engine, encoding="utf-8")
    (game / "game.json").write_text(json.dumps(
        {"game_type": "g", "title": "G", "authors": ["x"], "min_players": 2, "max_players": 2}),
        encoding="utf-8")
    if analytics is not None:
        (game / "analytics.py").write_text(analytics, encoding="utf-8")
    return game


def test_random_playthrough_reaches_the_end():
    initial, moves, final = random_playthrough(TURN_REDUCER, 2, seed=1)
    assert initial["move_number"] == 0 and final["phase"] == "finished"
    assert [m[0] for m in moves] == [1, 2, 3] and [m[1] for m in moves] == [0, 1, 0]


def test_good_analytics_reports_events(tmp_path):
    problems, result = check_analytics(make_game_dir(tmp_path))
    assert problems == []
    assert [e["name"] for e in result["events"]] == ["inc"] * 3
    assert len(result["players"]) == 2


def test_bad_event_name_is_a_problem(tmp_path):
    src = "def on_step(p, pl, t, d, n, c):\n    return [{'name': 'Bad-Name', 'props': {}}]\n"
    problems, result = check_analytics(make_game_dir(tmp_path, src))
    assert result is None and any("must match" in p for p in problems)


def test_endless_loop_times_out(tmp_path, monkeypatch):
    monkeypatch.setattr(analytics_check, "TIMEOUT", 3)
    src = "def on_finish(f, c):\n    while True:\n        pass\n"
    problems, _ = check_analytics(make_game_dir(tmp_path, src))
    assert any("timed out" in p for p in problems)


def test_syntax_error_reported_without_running(tmp_path):
    problems, result = check_analytics(make_game_dir(tmp_path, "def on_step(:\n"))
    assert result is None and any("SyntaxError" in p for p in problems)


def test_nondeterministic_replay_is_a_problem(tmp_path):
    engine = TURN_REDUCER.replace(
        "    s['move_number'] = state['move_number'] + 1\n",
        "    import random\n    s['move_number'] = state['move_number'] + 1\n"
        "    s['noise'] = random.random()\n")
    problems, _ = check_analytics(make_game_dir(tmp_path, engine=engine))
    assert any("not deterministic" in p for p in problems)


def test_cli_exit_codes(tmp_path, capsys):
    assert main(["--analytics", "--game", str(make_game_dir(tmp_path))]) == 0
    assert "inc" in capsys.readouterr().out
    bad = make_game_dir(tmp_path / "b", "def on_step(p, pl, t, d, n, c):\n    return 5\n")
    assert main(["--analytics", "--game", str(bad)]) == 1
    none = make_game_dir(tmp_path / "c", analytics=None)
    assert main(["--analytics", "--game", str(none)]) == 2


SIMULTANEOUS = (
    "def new_game(config):\n"
    "    return {'phase': 'playing', 'winner': None, 'move_number': 0,\n"
    "            'players_to_move': [], 'done': [False, False]}\n"
    "def legal_actions(state, player):\n"
    "    if state['phase'] == 'finished' or state['done'][player]:\n"
    "        return {}\n"
    "    return {'commit': [{}]}\n"
    "def apply_action(state, player, action_type, data):\n"
    "    s = dict(state); s['done'] = list(state['done']); s['done'][player] = True\n"
    "    s['move_number'] = state['move_number'] + 1\n"
    "    if all(s['done']):\n"
    "        s['phase'] = 'finished'; s['winner'] = 0\n"
    "    return s\n"
    "def snapshot(state):\n"
    "    return dict(state)\n"
)


def test_empty_players_to_move_means_everyone_may_move():
    initial, moves, final = random_playthrough(SIMULTANEOUS, 2, seed=1)
    assert sorted(m[1] for m in moves) == [0, 1] and final["phase"] == "finished"


def test_a_game_with_no_moves_played_is_a_problem(tmp_path):
    stuck = TURN_REDUCER.replace("    return {'inc': [{}]}\n", "    return {}\n")
    problems, _ = check_analytics(make_game_dir(tmp_path, engine=stuck))
    assert any("no moves" in p for p in problems)
