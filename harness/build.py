"""Resolve (and, if needed, build) a game's client bundle for the harness.

Mirrors how the platform delivers external games: a game.json `build` manifest
names a command + output dir; with no manifest, the static `client/` dir is the
bundle. Build commands run UNSANDBOXED on the dev host — fine for a local tool
you point at your own game; the platform's trust boundary is its CI + merge
review.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def _contained(game_dir: Path, rel: str) -> Path:
    """Resolve game_dir/rel and ensure it stays inside game_dir (no escape)."""
    base = game_dir.resolve()
    target = (base / rel).resolve()
    if target != base and not target.is_relative_to(base):
        raise ValueError(f"bundle dir {rel!r} escapes the game directory")
    return target


def build_client(game_dir: Path, metadata: dict, rebuild: bool = True) -> Path:
    """Return the static dir to serve as the client.

    - No `build` manifest -> the static `client/` dir.
    - With `build` -> run `command` in the game dir (unless rebuild=False) and
      return its `output` dir.
    Raises ValueError on a bad/escaping manifest, FileNotFoundError if the
    resolved dir has no index.html.
    """
    game_dir = Path(game_dir)
    build = metadata.get("build")
    if not build:
        out = _contained(game_dir, "client")
    else:
        command = build.get("command")
        output = build.get("output")
        if not command or not output:
            raise ValueError("invalid build manifest: 'build' requires 'command' and 'output'")
        if rebuild:
            subprocess.run(command, cwd=game_dir, shell=True, check=True)
        out = _contained(game_dir, output)
    if not (out / "index.html").is_file():
        raise FileNotFoundError(f"client bundle has no index.html at {out}")
    return out
