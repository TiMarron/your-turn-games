"""Tests for harness.build.build_client (runs game.json build manifests)."""
import sys

import pytest

from harness.build import build_client


def _write(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_static_game_returns_client_dir(tmp_path):
    game = tmp_path / "g"
    _write(game / "client" / "index.html", "<!doctype html>hi")
    out = build_client(game, {}, rebuild=True)
    assert out == (game / "client").resolve()
    assert (out / "index.html").is_file()


def test_static_game_without_index_raises(tmp_path):
    game = tmp_path / "g"
    (game / "client").mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        build_client(game, {}, rebuild=True)


def test_build_runs_command_and_returns_output(tmp_path):
    game = tmp_path / "g"
    game.mkdir()
    (game / "do_build.py").write_text(
        "import pathlib; d = pathlib.Path('out'); d.mkdir(exist_ok=True); "
        "(d / 'index.html').write_text('built')\n",
        encoding="utf-8",
    )
    meta = {"build": {"command": f'"{sys.executable}" do_build.py', "output": "out"}}
    out = build_client(game, meta, rebuild=True)
    assert out == (game / "out").resolve()
    assert (out / "index.html").read_text(encoding="utf-8") == "built"


def test_no_rebuild_skips_command(tmp_path):
    game = tmp_path / "g"
    _write(game / "dist" / "index.html", "prebuilt")
    meta = {"build": {"command": "exit 1", "output": "dist"}}
    out = build_client(game, meta, rebuild=False)
    assert out == (game / "dist").resolve()
    assert (out / "index.html").read_text(encoding="utf-8") == "prebuilt"


def test_build_manifest_missing_fields_raises(tmp_path):
    game = tmp_path / "g"
    game.mkdir()
    with pytest.raises(ValueError):
        build_client(game, {"build": {"command": "echo hi"}}, rebuild=True)


def test_output_escaping_game_dir_raises(tmp_path):
    game = tmp_path / "g"
    game.mkdir()
    meta = {"build": {"command": "echo noop", "output": "../../etc"}}
    with pytest.raises(ValueError):
        build_client(game, meta, rebuild=True)
