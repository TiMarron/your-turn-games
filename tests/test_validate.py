from harness.validate import validate
from tests.conftest import TURN_REDUCER

GOOD = TURN_REDUCER  # defines all 4 fns, current_player turn flip, reaches finished


def test_good_reducer_has_no_problems():
    assert validate(GOOD) == []


def test_missing_required_field_reported():
    src = GOOD.replace("'move_number': 0,", "")  # new_game omits move_number
    problems = validate(src)
    assert any("move_number" in p for p in problems)


def test_empty_initial_legal_actions_reported():
    src = (
        "def new_game(c):\n"
        "    return {'phase':'playing','winner':None,'move_number':0,'current_player':0}\n"
        "def legal_actions(s, p):\n"
        "    return {}\n"                       # nobody can ever act
        "def apply_action(s, p, t, d):\n"
        "    return s\n"
        "def snapshot(s):\n"
        "    return {'phase':s['phase'],'winner':s['winner'],"
        "'move_number':s['move_number'],'current_player':s['current_player']}\n"
    )
    problems = validate(src)
    assert any("legal_actions" in p for p in problems)


def test_action_not_round_tripping_reported():
    src = (
        "def new_game(c):\n"
        "    return {'phase':'playing','winner':None,'move_number':0,'current_player':0}\n"
        "def legal_actions(s, p):\n"
        "    return {'go': [{}]}\n"
        "def apply_action(s, p, t, d):\n"
        "    raise ValueError('always fails')\n"   # rejects its own offered action
        "def snapshot(s):\n"
        "    return {'phase':s['phase'],'winner':s['winner'],"
        "'move_number':s['move_number'],'current_player':s['current_player']}\n"
    )
    problems = validate(src)
    assert any("apply_action" in p for p in problems)


def test_missing_function_reported():
    problems = validate("x = 1")
    assert any("new_game" in p for p in problems)
