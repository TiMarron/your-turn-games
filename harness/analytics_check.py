"""Check a game's analytics.py before it reaches the portal.

    python -m harness --analytics --game games/<slug> [--seed N] [--players N] [--moves N]

Plays one random game with the reducer (random legal action each move, in the
same subprocess sandbox the harness uses for reducer calls), then replays it
through the analytics loop in a fresh subprocess, exactly as the platform
recomputes a finished game: on_step for every move, on_finish once. Reports
format errors, exceptions, timeouts and a replay that does not reproduce the
played game (a non-deterministic apply_action).
"""
from __future__ import annotations

import json
import random
import subprocess
import sys
from pathlib import Path

from harness.sandbox_runner import ReducerError, ReducerMissing, RunnerError, run

ROOT = Path(__file__).resolve().parents[1]
TIMEOUT = 45            # the platform's analytics budget (wall clock) per game
MAX_SOURCE_BYTES = 200_000

# Fixed child program: reads the job from stdin, runs harness.analytics_loop.run_job,
# writes one JSON line to the real stdout (author prints are swallowed).
_CHILD = r"""
import io, json, sys
real = sys.stdout
job = json.loads(sys.stdin.read())
sys.path.insert(0, job["root"])
from harness.analytics_loop import AnalyticsError, run_job
sys.stdout = io.StringIO()
try:
    result = run_job(job["engine"], job["analytics"], job["initial"], job["moves"],
                     job["step_ctx"], job["finish_ctx"])
    out = {"ok": True, "result": result}
except AnalyticsError as exc:
    out = {"ok": False, "message": str(exc)}
real.write(json.dumps(out))
"""


def _seats_to_move(state: dict, n_players: int) -> list[int]:
    """Seats that may act: players_to_move ([] = every seat, per CONTRACT.md),
    else current_player (-1 = nobody)."""
    ptm = state.get("players_to_move")
    if isinstance(ptm, list):
        return list(ptm) if ptm else list(range(n_players))
    seat = state.get("current_player", 0)
    return [] if seat == -1 else [seat]


def _options(actions: dict) -> list[tuple[str, dict]]:
    out = []
    for action_type, entry in actions.items():
        if isinstance(entry, list):
            out += [(action_type, d) for d in entry if isinstance(d, dict)] or [(action_type, {})]
        elif isinstance(entry, dict):
            out.append((action_type, entry))
        else:
            out.append((action_type, {}))
    return out


def random_playthrough(source: str, n_players: int, seed: int,
                       max_moves: int = 300) -> tuple[dict, list[list], dict]:
    """(initial, moves, final): moves are [move_number, seat, action_type, data]."""
    rng = random.Random(seed)
    state = run(source, "new_game", [{}])
    try:
        state = run(source, "initialize_for_players", [state, n_players])
    except ReducerMissing:
        pass                                   # optional function
    initial = state
    moves: list[list] = []
    while len(moves) < max_moves and state.get("phase") != "finished":
        choices = []
        for seat in _seats_to_move(state, n_players):
            options = _options(run(source, "legal_actions", [state, seat]) or {})
            if options:
                choices.append((seat, options))
        if not choices:
            break
        seat, options = rng.choice(choices)
        action_type, data = rng.choice(options)
        state = run(source, "apply_action", [state, seat, action_type, data])
        moves.append([len(moves) + 1, seat, action_type, data])
    return initial, moves, state


def check_analytics(game_dir: Path, seed: int = 1, n_players: int | None = None,
                    max_moves: int = 300) -> tuple[list[str], dict | None]:
    """(problems, result). result is run_job's output plus "moves", or None on a problem."""
    game_dir = Path(game_dir)
    engine = (game_dir / "engine.py").read_text(encoding="utf-8")
    analytics_file = game_dir / "analytics.py"
    analytics = analytics_file.read_text(encoding="utf-8")
    meta = json.loads((game_dir / "game.json").read_text(encoding="utf-8"))

    if len(analytics.encode("utf-8")) > MAX_SOURCE_BYTES:
        return [f"analytics.py is larger than {MAX_SOURCE_BYTES} bytes"], None
    try:
        compile(analytics, str(analytics_file), "exec")
    except SyntaxError as exc:
        return [f"analytics.py: SyntaxError: {exc}"], None

    n = n_players or meta.get("max_players", 2)
    try:
        initial, moves, final = random_playthrough(engine, n, seed, max_moves)
    except (ReducerError, ReducerMissing, RunnerError) as exc:
        return [f"random game failed: {exc}"], None
    if not moves:
        return ["the random game played no moves (nobody had a legal action), so "
                "on_step was never called; the portal analyses only games with moves"], None

    step_ctx = {"engine_version": f"{meta.get('game_type', game_dir.name)}@local",
                "version": 0, "n_players": n}
    job = json.dumps({"root": str(ROOT), "engine": engine, "analytics": analytics,
                      "initial": initial, "moves": moves, "step_ctx": step_ctx,
                      "finish_ctx": {**step_ctx, "resigned_seat": None}})
    try:
        proc = subprocess.run([sys.executable, "-c", _CHILD], input=job, capture_output=True,
                              text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return [f"analytics timed out after {TIMEOUT}s"], None
    out = proc.stdout.strip()
    if not out:
        return [f"analytics produced no output (exit {proc.returncode}): "
                f"{proc.stderr.strip()[-500:]}"], None
    resp = json.loads(out.splitlines()[-1])
    if not resp["ok"]:
        return [resp["message"]], None
    result = resp["result"]
    if result["final_state"] != final:
        diff = sorted(k for k in final.keys() | result["final_state"].keys()
                      if final.get(k) != result["final_state"].get(k))
        return ["replay diverged from the played game (fields: " + ", ".join(diff) + ") — "
                "apply_action is not deterministic"], None
    result["moves"] = len(moves)
    return [], result


def report(result: dict) -> str:
    lines = [f"moves played: {result['moves']}"]
    by_name: dict[str, list] = {}
    for e in result["events"]:
        by_name.setdefault(e["name"], []).append(e)
    if not by_name:
        lines.append("events: none")
    for name, events in sorted(by_name.items()):
        example = json.dumps(events[0]["props"], ensure_ascii=False)
        lines.append(f"event {name}: {len(events)}, e.g. {example}")
    for p in result["players"]:
        lines.append(f"seat {p['seat']}: {json.dumps(p['props'], ensure_ascii=False)}")
    return "\n".join(lines)
