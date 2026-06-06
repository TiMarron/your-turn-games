"""Run one reducer function call in a throwaway subprocess.

The author's reducer source is untrusted: it is sent in the stdin job and
executed only inside the child process, never in the harness process. This
mirrors the platform's execution contract (it is NOT the platform's code).
"""
from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

REQUIRED_FUNCTIONS = ("new_game", "legal_actions", "apply_action", "snapshot")
OPTIONAL_FUNCTIONS = ("initialize_for_players",)
ALL_FUNCTIONS = REQUIRED_FUNCTIONS + OPTIONAL_FUNCTIONS


class RunnerError(Exception):
    """Infrastructure failure (bad source/payload, no output, timeout)."""


class ReducerError(Exception):
    """The author's reducer function raised (incl. rule/turn violations)."""


class ReducerMissing(Exception):
    """The reducer source does not define the requested function."""


# Fixed child program. Reads {"source","fn","args"} from stdin, execs the source
# in a fresh namespace, calls fn, writes exactly one JSON line to real stdout.
_CHILD = r"""
import io, json, sys
real = sys.stdout
try:
    job = json.loads(sys.stdin.read())
    source, fn, args = job["source"], job["fn"], job.get("args", [])
except Exception as exc:
    sys.stdout.write(json.dumps({"ok": False, "error_type": "runner",
                                 "message": "bad job: %s" % exc})); sys.exit(0)
sys.stdout = io.StringIO()  # swallow author prints so they can't corrupt output
try:
    ns = {}
    try:
        exec(source, ns)
    except Exception as exc:
        real.write(json.dumps({"ok": False, "error_type": "runner",
                               "message": "source failed to load: %s" % exc})); sys.exit(0)
    func = ns.get(fn)
    if not callable(func):
        real.write(json.dumps({"ok": False, "error_type": "missing",
                               "message": "reducer does not define %r" % fn})); sys.exit(0)
    try:
        result = func(*args)
        json.dumps(result)
    except Exception as exc:
        real.write(json.dumps({"ok": False, "error_type": "reducer",
                               "message": "%s: %s" % (type(exc).__name__, exc)})); sys.exit(0)
    real.write(json.dumps({"ok": True, "result": result}))
finally:
    sys.stdout = real
"""


def run(source: str, fn: str, args: list, timeout: float = 5.0) -> Any:
    """Execute reducer `fn(*args)` defined in `source`; return its JSON result."""
    job = json.dumps({"source": source, "fn": fn, "args": args})
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _CHILD],
            input=job, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RunnerError(f"reducer call {fn!r} timed out after {timeout}s") from exc

    out = proc.stdout.strip()
    if not out:
        raise RunnerError(
            f"sandbox produced no output (exit {proc.returncode}): "
            f"{proc.stderr.strip()[:300]}"
        )
    try:
        resp = json.loads(out.splitlines()[-1])
    except json.JSONDecodeError as exc:
        raise RunnerError(f"sandbox output not JSON: {out[:300]}") from exc

    if resp.get("ok"):
        return resp["result"]
    etype, msg = resp.get("error_type"), resp.get("message", "unknown error")
    if etype == "reducer":
        raise ReducerError(msg)
    if etype == "missing":
        raise ReducerMissing(msg)
    raise RunnerError(msg)
