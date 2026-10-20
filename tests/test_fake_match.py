import pytest

from harness.fake_match import FakeMatch
from harness.sandbox_runner import ReducerError
from tests.conftest import TURN_REDUCER


def test_initial_turn_and_snapshot():
    m = FakeMatch(TURN_REDUCER, n_players=2)
    assert m.players_to_move() == [0]
    snap = m.snapshot()
    assert snap["phase"] == "playing"
    assert snap["current_player"] == 0


def test_apply_alternates_turn():
    m = FakeMatch(TURN_REDUCER, n_players=2)
    m.apply(0, "inc", {})
    assert m.players_to_move() == [1]
    m.apply(1, "inc", {})
    assert m.players_to_move() == [0]


def test_play_to_a_win():
    m = FakeMatch(TURN_REDUCER, n_players=2)
    m.apply(0, "inc", {})
    m.apply(1, "inc", {})
    snap = m.apply(0, "inc", {})
    assert snap["phase"] == "finished"
    assert snap["winner"] == 0
    assert m.players_to_move() == []


def test_out_of_turn_raises():
    m = FakeMatch(TURN_REDUCER, n_players=2)
    with pytest.raises(ReducerError):
        m.apply(1, "inc", {})


def test_legal_actions_only_for_current_player():
    m = FakeMatch(TURN_REDUCER, n_players=2)
    assert m.legal_actions(0) == {"inc": [{}]}
    assert m.legal_actions(1) == {}


CONFIG_ECHO_REDUCER = (
    "def new_game(config):\n"
    "    return {'phase': 'playing', 'winner': None, 'move_number': 0,\n"
    "            'current_player': 0, 'config': config}\n"
    "def legal_actions(state, player):\n"
    "    return {}\n"
    "def apply_action(state, player, action_type, data):\n"
    "    return state\n"
    "def snapshot(state):\n"
    "    return dict(state)\n"
)


def test_config_is_passed_to_new_game():
    m = FakeMatch(CONFIG_ECHO_REDUCER, config={"win_length": 4})
    assert m.snapshot()["config"] == {"win_length": 4}


def test_config_defaults_to_empty_dict():
    m = FakeMatch(CONFIG_ECHO_REDUCER)
    assert m.snapshot()["config"] == {}
