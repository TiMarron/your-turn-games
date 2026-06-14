# Skill: author a your-turn game

You are creating a game for the **«Твой ход!»** platform. Deliver three things in
a new directory under `games/<slug>/`:

1. `engine.py` — a Python reducer (pure functions over a JSON dict).
2. `client/` — a static web client (dependency-free HTML+JS is fine).
3. `game.json` — metadata.

Follow [CONTRACT.md](CONTRACT.md) exactly. Then verify locally:
`python -m harness --game games/<slug>` and play it in two browser tabs.

## Rules of thumb

- Keep **all** game rules in `engine.py`. The client only renders `snapshot()`
  and sends actions; it must never decide legality.
- The reducer is **pure**: no file/network/time/random-without-seed. Derive
  everything from `state` and `config`.
- Put hidden info in `state` but **omit it from `snapshot()`**.
- `apply_action` must **raise** for any illegal action (wrong turn, taken cell,
  bad payload). Returning an unchanged state is a bug.
- Always set `phase`, `winner`, `move_number`, `current_player` in both `state`
  and `snapshot()`. Set `current_player = -1` when the game is finished.
- For the client, **copy `sdk/client.js`** into your bundle and use
  `connect({ onState })` + `game.sendAction(type, data)` instead of writing your
  own polling/WebSocket code. `onState(snapshot)` fires on every move (yours and
  the opponent's) — render there. See `games/tic-tac-toe/client/` for a complete
  example.

## Worked example (complete, runnable)

`games/coin/engine.py` — two players alternate; whoever takes the last of 3 coins
loses:

(The `games/coin/` directory is illustrative — it is not shipped in this repo. Create it yourself to try the example, or just read it.)

```python
def new_game(config):
    return {"phase": "playing", "winner": None, "move_number": 0,
            "current_player": 0, "coins": 3}

def legal_actions(state, player):
    if state["phase"] == "finished" or player != state["current_player"]:
        return {}
    return {"take": [{"n": n} for n in (1, 2) if n <= state["coins"]]}

def apply_action(state, player, action_type, data):
    if player != state["current_player"]:
        raise ValueError("not your turn")
    if action_type != "take":
        raise ValueError("unknown action")
    n = data.get("n")
    if n not in (1, 2) or n > state["coins"]:
        raise ValueError("illegal take")
    s = dict(state)
    s["coins"] = state["coins"] - n
    s["move_number"] = state["move_number"] + 1
    if s["coins"] <= 0:
        # the player who took the last coin loses -> the other wins
        s["phase"] = "finished"; s["winner"] = 1 - player; s["current_player"] = -1
    else:
        s["current_player"] = 1 - player
    return s

def snapshot(state):
    return {"phase": state["phase"], "winner": state["winner"],
            "move_number": state["move_number"], "current_player": state["current_player"],
            "coins": state["coins"]}
```

`games/coin/client/index.html` — minimal client (same protocol as the tic-tac-toe
example; copy `games/tic-tac-toe/client/index.html` and adapt the rendering and
the action you POST).

`games/coin/game.json`:

```json
{ "game_type": "coin", "title": "Last Coin Loses", "description": "Take 1-2 coins; taking the last loses.", "author": "you", "min_players": 2, "max_players": 2 }
```

Run it: `python -m harness --game games/coin`.

## Checklist before you submit

- [ ] `python -m harness --game games/<slug>` runs; you can play a full game in
      two tabs and it reaches a `finished` state with the right winner.
- [ ] `apply_action` raises on out-of-turn and on every illegal action.
- [ ] `snapshot()` exposes no hidden info and includes the four required fields.
- [ ] `game.json` is filled in (slug, title, players).
