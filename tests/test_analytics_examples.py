"""The shipped analytics.py examples pass the same check CI runs."""
from pathlib import Path

import pytest

from harness.analytics_check import check_analytics

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("game", ["template", "games/infinite-xo"])
def test_example_analytics_pass_the_check(game):
    problems, result = check_analytics(ROOT / game, seed=3)
    assert problems == []
    assert result["events"] and len(result["players"]) == 2


def test_infinite_xo_marks_add_up():
    _, result = check_analytics(ROOT / "games/infinite-xo", seed=5)
    marks = sum(p["props"]["marks"] for p in result["players"])
    assert marks == len([e for e in result["events"] if e["name"] == "mark_placed"])
