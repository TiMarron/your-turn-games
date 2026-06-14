# your-turn-games

Author games for the **«Твой ход!»** platform: a Python **reducer** + a static
**client**, developed and tested fully offline with a local dev harness.
No build step; one dependency (aiohttp) to run the harness — the game client
itself stays dependency-free.

## Layout

```
CONTRACT.md          the game contract (read this)
SKILL.md             authoring guide + worked example
harness/             the local dev harness (stdlib only)
template/            copy this to start a new game
games/tic-tac-toe/   reference game (engine.py + client/ + game.json)
tests/               the harness's own tests (require pytest)
```

## Quickstart

```bash
git clone <this repo> && cd your-turn-games
pip install -r requirements.txt        # aiohttp (the dev harness server)
python -m harness --game games/tic-tac-toe
# open the two printed URLs (seat 0 and seat 1) in separate browser tabs and play
```

## Start your own game

```bash
cp -r template games/my-game
# edit games/my-game/engine.py, client/index.html, game.json
python -m harness --game games/my-game
```

On Windows use `xcopy /E /I template games\my-game` (or `Copy-Item -Recurse template games/my-game` in PowerShell).

## Run the harness tests (contributors)

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

See [CONTRACT.md](CONTRACT.md) and [SKILL.md](SKILL.md).
