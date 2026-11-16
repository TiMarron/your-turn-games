"""Mirror of the platform's analytics loop (your-turn: server/api/sandbox/analytics_loop.py).

Keep in sync by hand: the harness must not import platform code. The platform
re-checks everything it gets back, so a drift here only means "fine in the
harness, failed on the portal" — never a hole.

    on_step(prev, player, action_type, data, next, ctx) -> [{"name", "props"}, ...]
    on_finish(final, ctx) -> [{"seat", "props"}, ...]

ctx["memo"] is a per-game scratch dict shared by every hook call of one game
(e.g. to count something in on_step and report it in on_finish); it is the
only argument hooks may mutate, and it starts empty for each game.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any, Callable

NAME_RE = re.compile(r"^[a-z0-9_]{1,40}$")
# Fields the platform attaches itself; an author's prop must not shadow them.
RESERVED_PROPS = frozenset(
    {"game", "game_id", "engine_version", "n_players", "move_number", "seat", "seat_won", "won"})
MAX_PROPS = 20
MAX_STR = 100
MAX_EVENTS_PER_STEP = 50
MAX_EVENTS_PER_GAME = 20_000


class AnalyticsError(Exception):
    """The author's analytics code or its output is wrong, or the replay failed.
    The message is shown to the author in «Мои игры»."""


def _copy(value: Any) -> Any:
    return json.loads(json.dumps(value))


def _int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def check_props(props: object) -> dict:
    if not isinstance(props, dict):
        raise AnalyticsError(f"props must be a dict, got {type(props).__name__}")
    if len(props) > MAX_PROPS:
        raise AnalyticsError(f"props has {len(props)} keys, at most {MAX_PROPS} allowed")
    for key, value in props.items():
        if not isinstance(key, str) or not NAME_RE.match(key):
            raise AnalyticsError(f"prop name {key!r} must match [a-z0-9_]{{1,40}}")
        if key in RESERVED_PROPS:
            raise AnalyticsError(f"prop name {key!r} is reserved by the platform")
        if isinstance(value, str):
            if len(value) > MAX_STR:
                raise AnalyticsError(f"prop {key!r}: string longer than {MAX_STR} chars")
        elif isinstance(value, float):
            if not math.isfinite(value):
                raise AnalyticsError(f"prop {key!r}: float must be finite")
        elif value is not None and not isinstance(value, (int, bool)):
            raise AnalyticsError(
                f"prop {key!r}: value must be str, int, float, bool or None, "
                f"got {type(value).__name__}")
    return props


def check_events(raw: object, where: str) -> list[dict]:
    if not isinstance(raw, list):
        raise AnalyticsError(f"{where}: must return a list, got {type(raw).__name__}")
    if len(raw) > MAX_EVENTS_PER_STEP:
        raise AnalyticsError(
            f"{where}: {len(raw)} events, at most {MAX_EVENTS_PER_STEP} per move")
    out = []
    for ev in raw:
        try:
            if not isinstance(ev, dict):
                raise AnalyticsError(f"event must be a dict, got {type(ev).__name__}")
            name = ev.get("name")
            if not isinstance(name, str) or not NAME_RE.match(name):
                raise AnalyticsError(f"event name {name!r} must match [a-z0-9_]{{1,40}}")
            out.append({"name": name, "props": check_props(ev.get("props", {}))})
        except AnalyticsError as exc:
            raise AnalyticsError(f"{where}: {exc}") from None
    return out


def check_summaries(raw: object, n_players: int) -> list[dict]:
    if not isinstance(raw, list):
        raise AnalyticsError(f"on_finish: must return a list, got {type(raw).__name__}")
    out, seen = [], set()
    for item in raw:
        try:
            if not isinstance(item, dict):
                raise AnalyticsError(f"summary must be a dict, got {type(item).__name__}")
            seat = item.get("seat")
            if not _int(seat) or not 0 <= seat < n_players:
                raise AnalyticsError(f"summary seat {seat!r} is not a seat of this game")
            if seat in seen:
                raise AnalyticsError(f"more than one summary for seat {seat}")
            seen.add(seat)
            out.append({"seat": seat, "props": check_props(item.get("props", {}))})
        except AnalyticsError as exc:
            raise AnalyticsError(f"on_finish: {exc}") from None
    return out


def run_analytics(
    apply: Callable[[dict, int, str, dict], dict],
    on_step: Callable | None,
    on_finish: Callable | None,
    initial_state: dict,
    moves: list[list],
    step_ctx: dict,
    finish_ctx: dict,
) -> dict:
    """Replay `moves` ([move_number, seat, action_type, data]) from initial_state.

    Hooks get copies, so an author mutating prev/next/data cannot change the
    replay; the reducer gets a copy too, so one that edits its input in place
    (fine in live play, where every call gets a fresh state) cannot corrupt
    `prev`. Raises AnalyticsError on any failure, SystemExit included.
    """
    state = initial_state
    events: list[dict] = []
    memo: dict = {}
    for move_number, seat, action_type, data in moves:
        prev = _copy(state)
        try:
            nxt = apply(_copy(state), seat, action_type, _copy(data))
        except (Exception, SystemExit) as exc:
            raise AnalyticsError(
                f"replay failed at move #{move_number}: {type(exc).__name__}: {exc}") from None
        if on_step is not None:
            where = f"on_step, move #{move_number}"
            try:
                raw = on_step(prev, seat, action_type, _copy(data), _copy(nxt),
                              {**step_ctx, "memo": memo})
            except (Exception, SystemExit) as exc:
                raise AnalyticsError(f"{where}: {type(exc).__name__}: {exc}") from None
            for ev in check_events(raw, where):
                events.append({"move_number": move_number, "seat": seat, **ev})
            if len(events) > MAX_EVENTS_PER_GAME:
                raise AnalyticsError(f"more than {MAX_EVENTS_PER_GAME} events in one game")
        state = nxt

    players: list[dict] = []
    if on_finish is not None:
        if isinstance(state, dict) and state.get("phase") == "finished":
            outcome = "normal"
        elif finish_ctx.get("resigned_seat") is not None:
            outcome = "resign"
        else:
            outcome = "draw"
        try:
            raw = on_finish(_copy(state), {**finish_ctx, "outcome": outcome, "memo": memo})
        except (Exception, SystemExit) as exc:
            raise AnalyticsError(f"on_finish: {type(exc).__name__}: {exc}") from None
        players = check_summaries(raw, step_ctx["n_players"])
    return {"final_state": state, "events": events, "players": players}


def _load(source: str, label: str) -> dict:
    namespace: dict = {"__name__": label}
    try:
        exec(source, namespace)  # noqa: S102 — runs in the sandbox (or our own built-ins)
    except (Exception, SystemExit) as exc:
        raise AnalyticsError(f"{label}.py failed to load: {type(exc).__name__}: {exc}") from None
    return namespace


def run_job(engine_source: str, analytics_source: str, initial_state: Any, moves: list,
            step_ctx: dict, finish_ctx: dict) -> dict:
    """Load the game's reducer and analytics module separately, then replay."""
    engine = _load(engine_source, "engine")
    analytics = _load(analytics_source, "analytics")
    apply = engine.get("apply_action")
    if not callable(apply):
        raise AnalyticsError("engine.py does not define apply_action")
    hook = lambda name: analytics.get(name) if callable(analytics.get(name)) else None  # noqa: E731
    return run_analytics(apply, hook("on_step"), hook("on_finish"), initial_state, moves,
                         step_ctx, finish_ctx)


def check_result(result: object, n_players: int) -> dict:
    """Validate a run_job result received from the sandbox (untrusted)."""
    if not isinstance(result, dict):
        raise AnalyticsError("analytics result is not an object")
    if not isinstance(result.get("final_state"), dict):
        raise AnalyticsError("analytics result has no final state")
    events = result.get("events")
    if not isinstance(events, list):
        raise AnalyticsError("analytics result events are not a list")
    if len(events) > MAX_EVENTS_PER_GAME:
        raise AnalyticsError(f"more than {MAX_EVENTS_PER_GAME} events in one game")
    checked = []
    for ev in events:
        if not isinstance(ev, dict) or not _int(ev.get("move_number")) or not _int(ev.get("seat")):
            raise AnalyticsError("analytics result has a malformed event")
        (body,) = check_events([{"name": ev.get("name"), "props": ev.get("props")}], "event")
        checked.append({"move_number": ev["move_number"], "seat": ev["seat"], **body})
    players = check_summaries(result.get("players"), n_players)
    return {"final_state": result["final_state"], "events": checked, "players": players}
