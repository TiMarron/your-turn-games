import pytest

from harness.sandbox_runner import run, ReducerError, ReducerMissing, RunnerError
from tests.conftest import TURN_REDUCER


def test_run_new_game():
    state = run(TURN_REDUCER, "new_game", [{}])
    assert state["phase"] == "playing"
    assert state["current_player"] == 0


def test_run_apply_action_increments():
    state = run(TURN_REDUCER, "new_game", [{}])
    state = run(TURN_REDUCER, "apply_action", [state, 0, "inc", {}])
    assert state["count"] == [1, 0]
    assert state["current_player"] == 1


def test_reducer_exception_maps_to_reducer_error():
    state = run(TURN_REDUCER, "new_game", [{}])
    with pytest.raises(ReducerError):
        run(TURN_REDUCER, "apply_action", [state, 1, "inc", {}])  # seat 1 out of turn


def test_missing_function_maps_to_reducer_missing():
    with pytest.raises(ReducerMissing):
        run("x = 1", "new_game", [{}])


def test_syntax_error_in_source_maps_to_runner_error():
    with pytest.raises(RunnerError):
        run("def new_game(config)\n    return {}", "new_game", [{}])  # missing colon
