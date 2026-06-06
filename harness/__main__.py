"""CLI: python -m harness --game games/tic-tac-toe [--port 8080]

Loads engine.py + game.json + client/ from the game dir and serves them.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from harness.server import Harness, serve


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="harness", description="Run a your-turn game locally.")
    parser.add_argument("--game", required=True, help="path to a game dir (engine.py, game.json, client/)")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args(argv)

    game_dir = Path(args.game).resolve()
    engine_file = game_dir / "engine.py"
    meta_file = game_dir / "game.json"
    client_dir = game_dir / "client"
    for p in (engine_file, meta_file, client_dir):
        if not p.exists():
            print(f"error: missing {p}", file=sys.stderr)
            return 2

    source = engine_file.read_text(encoding="utf-8")
    metadata = json.loads(meta_file.read_text(encoding="utf-8"))
    harness = Harness(source=source, metadata=metadata, client_dir=client_dir)
    httpd = serve(harness, host=args.host, port=args.port)
    base = f"http://{args.host}:{args.port}"
    n = metadata.get("max_players", 2)
    print(f"Serving {metadata.get('title', game_dir.name)} at {base}")
    print("Open one tab per seat:")
    for i in range(n):
        print(f"  seat {i}: {base}/play?seat={i}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
        httpd.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
