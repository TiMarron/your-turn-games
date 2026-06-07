"""Validate a reducer against the your-turn game contract, using the sandbox.

Returns a list of human-readable problems (empty = valid). Mirrors the platform's
own checks behaviorally (it does not import platform code)."""
from __future__ import annotations

from pathlib import Path

from harness.sandbox_runner import ReducerError, ReducerMissing, RunnerError, run

REQUIRED_STATE_FIELDS = ("phase", "winner", "move_number", "current_player")


def _turn_fields_ok(state: dict) -> list[str]:
    problems: list[str] = []
    has_ptm = "players_to_move" in state
    for field in REQUIRED_STATE_FIELDS:
        if field == "current_player" and has_ptm:
            continue  # players_to_move is an accepted alternative
        if field not in state:
            problems.append(f"state is missing required field {field!r}")
    return problems


def validate(source: str) -> list[str]:
    """Return a list of contract problems; empty list means the reducer is valid."""
    problems: list[str] = []

    try:
        state = run(source, "new_game", [{}])
    except ReducerMissing:
        return ["reducer does not define new_game(config)"]
    except (ReducerError, RunnerError) as exc:
        return [f"new_game(config) failed: {exc}"]
    if not isinstance(state, dict):
        return ["new_game(config) must return a dict state"]
    problems += _turn_fields_ok(state)

    try:
        snap = run(source, "snapshot", [state])
        if not isinstance(snap, dict):
            problems.append("snapshot(state) must return a dict")
        else:
            for field in REQUIRED_STATE_FIELDS:
                if field == "current_player" and "players_to_move" in snap:
                    continue
                if field not in snap:
                    problems.append(f"snapshot(state) is missing required field {field!r}")
    except ReducerMissing:
        problems.append("reducer does not define snapshot(state)")
    except (ReducerError, RunnerError) as exc:
        problems.append(f"snapshot(state) failed: {exc}")

    seat = state.get("current_player", 0)
    if seat == -1:
        seat = 0
    try:
        actions = run(source, "legal_actions", [state, seat])
    except ReducerMissing:
        return problems + ["reducer does not define legal_actions(state, player)"]
    except (ReducerError, RunnerError) as exc:
        return problems + [f"legal_actions(state, {seat}) failed: {exc}"]
    if not isinstance(actions, dict) or not actions:
        problems.append(
            f"legal_actions(state, {seat}) is empty — the starting player must be "
            "able to act (players are 0-indexed; the first mover is current_player)"
        )
        return problems

    action_type = next(iter(actions))
    entry = actions[action_type]
    if isinstance(entry, list) and entry and isinstance(entry[0], dict):
        data = entry[0]
    elif isinstance(entry, dict):
        data = entry
    else:
        data = {}
    try:
        run(source, "apply_action", [state, seat, action_type, data])
    except ReducerMissing:
        problems.append("reducer does not define apply_action(state, player, action_type, data)")
    except (ReducerError, RunnerError) as exc:
        problems.append(
            f"apply_action rejected its own offered action {action_type!r} "
            f"(data={data!r}): {exc} — keys of legal_actions() must be action_types "
            "that apply_action() accepts"
        )
    return problems


def build_bundle_dir(game_dir: Path, metadata: dict) -> Path:
    """Resolve the client bundle dir from game.json's optional build manifest.

    No `build` key -> the static `client/` dir IS the bundle.
    With `build` -> returns `game_dir / build["output"]` (the caller runs the
    build command itself before shipping)."""
    game_dir = Path(game_dir)
    build = metadata.get("build")
    if not build:
        return game_dir / "client"
    return game_dir / build["output"]
