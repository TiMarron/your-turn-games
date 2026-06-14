"""CLI: python -m harness --game games/tic-tac-toe [--port 8080]

Loads engine.py + game.json from the game dir, builds the client (per the
game.json `build` manifest, or the static `client/` dir), and serves them.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from aiohttp import web

from harness.server import Harness, make_app


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="harness", description="Run a your-turn game locally.")
    parser.add_argument("--game", required=True,
                        help="path to a game dir (engine.py, game.json, and a client/ dir "
                             "or a game.json build manifest)")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--validate", action="store_true",
                        help="validate the reducer and exit (non-zero on problems)")
    parser.add_argument("--no-build", action="store_true",
                        help="serve the existing build output without rebuilding "
                             "(use after a build / alongside a framework watch server)")
    args = parser.parse_args(argv)

    game_dir = Path(args.game).resolve()
    engine_file = game_dir / "engine.py"
    meta_file = game_dir / "game.json"
    for p in (engine_file, meta_file):
        if not p.exists():
            print(f"error: missing {p}", file=sys.stderr)
            return 2

    source = engine_file.read_text(encoding="utf-8")
    metadata = json.loads(meta_file.read_text(encoding="utf-8"))

    if args.validate:
        from harness.validate import validate
        problems = validate(source)
        if problems:
            print("VALIDATION FAILED:", file=sys.stderr)
            for p in problems:
                print(f"  - {p}", file=sys.stderr)
            return 1
        print(f"OK: {metadata.get('title', game_dir.name)} reducer is contract-valid")
        return 0

    from harness.build import build_client
    try:
        client_dir = build_client(game_dir, metadata, rebuild=not args.no_build)
    except Exception as exc:
        print(f"error: client build failed: {exc}", file=sys.stderr)
        return 2
    harness = Harness(source=source, metadata=metadata, client_dir=client_dir)
    base = f"http://{args.host}:{args.port}"
    n = metadata.get("max_players", 2)
    print(f"Serving {metadata.get('title', game_dir.name)} at {base}")
    print("Open one tab per seat:")
    for i in range(n):
        print(f"  seat {i}: {base}/play?seat={i}")
    web.run_app(make_app(harness), host=args.host, port=args.port, print=None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
