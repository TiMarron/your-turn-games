"""Starter analytics. Optional: delete this file if you don't need analytics.

The portal replays every finished game of yours move by move and calls these
two functions; their output appears in «Мои игры» → your game → event explorer
(count / sum / average / distribution, grouped and split by any field, CSV).
A change to this file is recomputed over ALL past games, of every engine
version, without releasing a new engine version.

  on_step(prev, player, action_type, data, next, ctx) -> [event, ...]
      Called once per move. `prev` / `next` are the full state (hidden fields
      included) before and after the move; `player` is the seat who moved.
      event = {"name": "went", "props": {"order": 0}}

  on_finish(final, ctx) -> [summary, ...]
      Called once at the end. One summary per seat at most.
      summary = {"seat": 0, "props": {"went_first": True}}

ctx: {"engine_version": "my-game@3", "version": 3, "n_players": 2,
      "memo": {}}                                  # + in on_finish only:
     {"outcome": "normal" | "resign" | "draw", "resigned_seat": int | None}

- Names (event names and prop keys): [a-z0-9_]{1,40}.
- Prop values: str (≤ 100 chars), int, float, bool or None; ≤ 20 props.
- ≤ 50 events per move, ≤ 20 000 per game.
- The portal adds these itself, so don't use them as prop names:
  game, game_id, engine_version, n_players, move_number, seat, seat_won, won.
  Every event gets `seat` (who moved) and `seat_won` (did that player win);
  every summary gets `won`. "Winners vs the rest" needs no code from you.
- ctx["version"] tells engine versions apart when the state shape changed.
- On "resign" / "draw" the final state is NOT finished (nobody moved last):
  read the outcome from ctx, not from final["phase"].
- ctx["memo"] is a dict shared by all calls of ONE game (empty at the start):
  count something in on_step, report it in on_finish. It is the only argument
  you may change; never keep game data in module globals.
- No I/O, no randomness. Don't import engine.py — copy the helper you need.

Check it locally: python -m harness --analytics --game games/<slug>
"""


def on_step(prev, player, action_type, data, next, ctx):
    if action_type != "go":
        return []
    order = sum(1 for went in prev["went"] if went)    # players who went before
    ctx["memo"].setdefault("order", []).append(player)
    return [{"name": "went", "props": {"order": order}}]


def on_finish(final, ctx):
    order = ctx["memo"].get("order", [])
    return [{"seat": seat, "props": {"went_first": bool(order) and order[0] == seat}}
            for seat in range(ctx["n_players"])]
