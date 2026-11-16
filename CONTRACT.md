# Game contract

A your-turn game is two parts:

1. **`engine.py`** — a Python *reducer*: pure functions over a JSON-serializable
   `dict` state. Runs server-side in a sandbox; never does I/O.
2. **`client/`** — a static web client (any stack that builds to plain files; the
   examples here are dependency-free HTML+JS). Runs in a **sandboxed iframe**
   (opaque origin) and talks to the platform over HTTP with a room-scoped token.

Plus **`game.json`** — metadata, and optionally **`analytics.py`** — see
[Analytics](#analytics-analyticspy-optional).

## Reducer functions (`engine.py`)

```python
def new_game(config: dict) -> dict: ...                                   # required
def legal_actions(state: dict, player: int) -> dict: ...                  # required
def apply_action(state: dict, player: int, action_type: str, data: dict) -> dict: ...  # required
def snapshot(state: dict) -> dict: ...                                    # required
def initialize_for_players(state: dict, n_players: int) -> dict: ...      # optional
```

- **Players are 0-indexed** (seat 0, 1, …).
- `legal_actions` returns `{action_type: [data, ...]}` — the actions `player` may
  take now; return `{}` if they cannot act (not their turn / game over).
- `apply_action` returns the **new** state, or **raises** on an illegal move
  (wrong turn, occupied cell, …). The platform maps the exception to HTTP 400.
- `apply_action` must be **deterministic**: the same `state`, `player`, `action_type` and `data` always give the same result. The platform replays stored games move by move (history, analytics). Need randomness mid-game? Derive it from a seed kept in the state, e.g. `random.Random(f"{state['seed']}:{state['move_number']}")`, and set the seed in `new_game`/`initialize_for_players` (those may use any randomness — their result is stored). Don't expose the seed in `snapshot()`.
- `snapshot` returns the **public** view sent to clients — never include hidden
  information (other players' secret state).
- State must be **JSON-serializable** (dicts/lists/str/int/float/bool/None).

### Required state & snapshot fields

Both the state dict and the `snapshot()` result MUST contain:

| Field | Meaning |
|---|---|
| `phase` | `"playing"` or `"finished"` |
| `winner` | winning seat (int) or `null` (no winner yet / draw) |
| `move_number` | integer, increments per applied action |
| `current_player` | seat whose turn it is; **`-1` = nobody** (e.g. finished) |

For simultaneous-move phases use `players_to_move` (a list of seats; `[]` = all)
instead of `current_player`. The platform derives the turn queue from these
fields; **enforcing** "not your turn" is the reducer's job (raise in
`apply_action`).

## `game.json`

```json
{
  "game_type": "infinite-xo",
  "title": "Infinite Tic-Tac-Toe",
  "description": "One-line description.",
  "author": "your-name",
  "authors": ["your-github-login"],
  "min_players": 2,
  "max_players": 2
}
```

`authors` — GitHub logins of the game's authors (required). They manage the game on the portal (visibility, testers, analytics) after linking GitHub in their profile. CI checks that a PR changing a game comes from one of its authors. A new game starts hidden from the catalog; its authors publish it in «Мои игры». `author` stays the display name.

If your client needs a build step (a bundler, etc.), add an optional `"build"`
object naming the command and its output directory:

```json
{
  "game_type": "chess",
  "title": "Chess",
  "description": "...",
  "author": "you",
  "min_players": 2,
  "max_players": 2,
  "build": { "command": "npm ci && npm run build", "output": "dist" }
}
```

- **No `build` key** ⇒ the client is static; the `client/` directory is shipped
  as-is (the infinite-xo reference works this way).
- **With `build`** ⇒ the dev harness, CI, and the platform run `command` in your
  game directory and serve the `output` directory as the client bundle. Set your
  bundler's base path to relative (e.g. Vite `base: "./"`) so assets resolve when
  the bundle is served from a sub-path and inside the sandboxed iframe.

## Analytics (`analytics.py`, optional)

Put `analytics.py` next to `engine.py` to see how your game is played: the portal
replays every finished game (at least one move; resigned and drawn games too)
move by move and turns it into named events you explore in «Мои игры» → your
game (count / sum / average / distribution, grouped and split by any field,
filters, CSV export). Start from [`template/analytics.py`](template/analytics.py);
[`games/infinite-xo/analytics.py`](games/infinite-xo/analytics.py) is a real example.

```python
def on_step(prev, player, action_type, data, next, ctx) -> list[dict]:
    """Events of one move: [{"name": "plant_sold", "props": {...}}, ...]; [] for none."""

def on_finish(final, ctx) -> list[dict]:
    """Per-seat summaries: [{"seat": 0, "props": {...}}, ...] (at most one per seat)."""
```

Both are optional. `ctx` is `{"engine_version": "my-game@3", "version": 3,
"n_players": 2, "memo": {}}`; `on_finish` also gets `"outcome"`
(`"normal"`, `"resign"` or `"draw"`) and `"resigned_seat"` (seat or `None`).

- **State**: `prev` / `next` / `final` are the full stored state, hidden fields
  included (only you see aggregates of your own game). On `resign` / `draw` the
  final state is not finished — read the outcome from `ctx`.
- **Names**: event names and prop keys match `[a-z0-9_]{1,40}`. **Values**: str
  (≤ 100 chars), int, float, bool or `None`; ≤ 20 props per event or summary;
  ≤ 50 events per move and ≤ 20 000 per game.
- **Added by the portal**: every event gets `seat` (who moved), `seat_won`,
  `move_number`, `engine_version`, `n_players`; every summary gets `won`,
  `engine_version`, `n_players`. These names (and `game`, `game_id`) are reserved
  for props.
- **`ctx["memo"]`**: a dict shared by every call of one game, empty at its start —
  count in `on_step`, report in `on_finish`. It is the only argument you may change;
  don't keep game data in module globals.
- **Self-contained**: no I/O, no randomness, and don't import `engine.py` (each
  game is replayed with its own engine version) — copy the helpers you need.
- **Versions**: one analytics file serves games of every engine version; branch on
  `ctx["version"]` when the state shape changed.
- **Recompute**: a merged change to `analytics.py` alone (no new engine version)
  is recomputed over all past games. Games whose replay does not reproduce the
  stored state are `diverged`; games where your code raises or breaks the format
  are `failed` — both are listed with the reason in «Мои игры».
- **Check before you push**: `python -m harness --analytics --game games/<slug>`
  plays a random game and runs your analytics over it (CI runs it too).

## Client protocol

The client runs in an iframe and communicates two ways.

### postMessage (with the host page)

- On load, the client posts (as a JSON **string**): `{"type":"ready"}`, or
  `{"type":"ready","features":["replay"]}` if it supports replay (the SDK does).
- The host replies: `{"type":"init","token":"<match token>","room_code":"<code>","api_base":"<origin>"}`.
- The client may post `{"type":"game_ended","winner_seat":N}` (`-1` = draw) and
  `{"type":"navigate","path":"/somewhere"}`.
- Because the iframe is sandboxed (opaque origin), post to the parent with
  `targetOrigin "*"`.
- **Replay** (only if the client declared `"replay"`): the host lets the player
  step through the game's past positions. It posts
  `{"type":"replay_state","state":<snapshot>}` — show that position read-only:
  no moves, no `game_ended` — and later `{"type":"replay_exit"}` — go back to
  the newest live state. Live WebSocket updates keep arriving in between.
  The `state` is the same platform snapshot as the HTTP state response, built
  from your `snapshot()` after that move. **Your snapshot is shown to every
  viewer after every single move**, so it must not hold private data, not even
  indirectly (a count that drops by exactly what a face-down choice cost gives
  that choice away).

### HTTP (with the platform API), using the token from `init`

All requests send header `Authorization: Bearer <token>`.

| Method | Path | Returns |
|---|---|---|
| GET  | `{api_base}/api/games/{room}/state`   | the latest `snapshot()` + `your_seat`, `players`, `room_code` |
| GET  | `{api_base}/api/games/{room}/actions` | `legal_actions(state, your_seat)` |
| POST | `{api_base}/api/games/{room}/action`  | body `{"type": <action_type>, "data": {...}}` → new snapshot (HTTP 400 if the reducer rejects) |

> The platform injects a few fields into the state response on top of your
> `snapshot()`: `your_seat`, `players`, `room_code`, `engine_version`, and (for
> external-authored games) an `external_client` block. Your client may read them
> but your reducer never produces them.

### Live updates (WebSocket) — handled by the SDK

You do not poll. Copy `sdk/client.js` into your client bundle and use it:

```html
<script type="module">
  import { connect } from "./sdk.js";
  function render(snap) { /* draw snap; snap.your_seat / snap.current_player */ }
  let game = null;
  connect({ onState: render }).then((g) => { game = g; });
  // send a move:  game.sendAction("place", { cell: 4 })
</script>
```

- `connect({ onState })` does the `ready`→`init` handshake, opens a WebSocket to
  `{api_base}/api/ws/{room}?token=…`, and calls `onState(snapshot)` on the initial
  state **and every opponent move** — no page refresh.
- `game.sendAction(type, data)` sends your move over `POST /action`; the resulting
  state comes back through `onState` (via the WebSocket broadcast), so render only
  in `onState`.
- The SDK notifies the host with `game_ended` when `phase` becomes `"finished"`.
- The SDK supports replay: it declares `"replay"`, calls
  `onState(snapshot, { replay: true })` for a past position, holds live updates
  meanwhile and calls `onState(latest, { replay: false })` on exit. While
  replaying `game.replay` is `true` and `game.sendAction` rejects — hide or
  disable your move controls. `connect({ onState, replay: false })` opts out.
  The same `sdk.js` runs unchanged in the dev harness and on the platform (both
  serve the WebSocket at the same origin as `api_base`).

## Develop locally

```bash
python -m harness --game games/infinite-xo
```

Open the printed per-seat URLs in separate tabs. The harness runs your reducer in
the same kind of sandbox the platform uses and serves your client in a sandboxed
iframe — so a game that works here works on the platform.
