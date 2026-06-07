# Game contract

A your-turn game is two parts:

1. **`engine.py`** — a Python *reducer*: pure functions over a JSON-serializable
   `dict` state. Runs server-side in a sandbox; never does I/O.
2. **`client/`** — a static web client (any stack that builds to plain files; the
   examples here are dependency-free HTML+JS). Runs in a **sandboxed iframe**
   (opaque origin) and talks to the platform over HTTP with a room-scoped token.

Plus **`game.json`** — metadata.

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
  "game_type": "tic-tac-toe",
  "title": "Tic-Tac-Toe",
  "description": "One-line description.",
  "author": "your-name",
  "min_players": 2,
  "max_players": 2
}
```

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
  as-is (the tic-tac-toe reference works this way).
- **With `build`** ⇒ CI and the platform run `command` in your game directory and
  ship the `output` directory as the client bundle. The command must run in a
  clean checkout with no network access to your machine.

## Client protocol

The client runs in an iframe and communicates two ways.

### postMessage (with the host page)

- On load, the client posts (as a JSON **string**): `{"type":"ready"}`.
- The host replies: `{"type":"init","token":"<match token>","room_code":"<code>","api_base":"<origin>"}`.
- The client may post `{"type":"game_ended","winner_seat":N}` (`-1` = draw) and
  `{"type":"navigate","path":"/somewhere"}`.
- Because the iframe is sandboxed (opaque origin), post to the parent with
  `targetOrigin "*"`.

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

A production client should also subscribe to `GET {api_base}/api/ws/{room}?token=<token>`
for live opponent moves; the example clients in this repo poll only and are kept
minimal.

## Develop locally

```bash
python -m harness --game games/tic-tac-toe
```

Open the printed per-seat URLs in separate tabs. The harness runs your reducer in
the same kind of sandbox the platform uses and serves your client in a sandboxed
iframe — so a game that works here works on the platform.
