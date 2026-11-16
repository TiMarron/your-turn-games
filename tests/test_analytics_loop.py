"""The harness's mirror of the platform analytics loop."""
import pytest

from harness.analytics_loop import AnalyticsError, run_job
from tests.conftest import TURN_REDUCER

INITIAL = {"phase": "playing", "winner": None, "move_number": 0, "current_player": 0,
           "count": [0, 0]}
MOVES = [[1, 0, "inc", {}], [2, 1, "inc", {}], [3, 0, "inc", {}]]
CTX = {"engine_version": "t@local", "version": 0, "n_players": 2}
FIN = {**CTX, "resigned_seat": None}

GOOD = (
    "def on_step(prev, p, t, d, n, ctx):\n"
    "    ctx['memo'][p] = ctx['memo'].get(p, 0) + 1\n"
    "    return [{'name': 'inc', 'props': {'count': n['count'][p]}}]\n"
    "def on_finish(f, ctx):\n"
    "    return [{'seat': s, 'props': {'moves': ctx['memo'].get(s, 0), 'outcome': ctx['outcome']}}\n"
    "            for s in range(ctx['n_players'])]\n"
)


def test_events_and_summaries():
    r = run_job(TURN_REDUCER, GOOD, INITIAL, MOVES, CTX, FIN)
    assert r["final_state"]["phase"] == "finished"
    assert [(e["move_number"], e["seat"], e["props"]["count"]) for e in r["events"]] == \
        [(1, 0, 1), (2, 1, 1), (3, 0, 2)]
    assert r["players"] == [{"seat": 0, "props": {"moves": 2, "outcome": "normal"}},
                            {"seat": 1, "props": {"moves": 1, "outcome": "normal"}}]


@pytest.mark.parametrize("ret, needle", [
    ("[{'name': 'Bad Name', 'props': {}}]", "name"),
    ("[{'name': 'x', 'props': {'seat': 1}}]", "reserved"),
    ("[{'name': 'x', 'props': {}}] * 51", "50"),
])
def test_bad_output(ret, needle):
    src = f"def on_step(prev, p, t, d, n, ctx):\n    return {ret}\n"
    with pytest.raises(AnalyticsError, match=needle):
        run_job(TURN_REDUCER, src, INITIAL, MOVES, CTX, FIN)


def test_system_exit_in_hook_is_analytics_error():
    src = "import sys\ndef on_finish(f, ctx):\n    sys.exit(3)\n"
    with pytest.raises(AnalyticsError, match="on_finish: SystemExit"):
        run_job(TURN_REDUCER, src, INITIAL, MOVES, CTX, FIN)


def test_memo_is_fresh_per_game():
    a = run_job(TURN_REDUCER, GOOD, INITIAL, MOVES, CTX, FIN)
    b = run_job(TURN_REDUCER, GOOD, INITIAL, MOVES, CTX, FIN)
    assert a["players"] == b["players"]
