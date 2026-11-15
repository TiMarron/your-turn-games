"""Game authorship checks (stdlib only).

Every game.json lists its authors as GitHub logins:

    "authors": ["octocat"]

On the portal, these authors manage the game (catalog visibility, testers,
analytics) after linking GitHub in their profile. CI checks that a pull request
touching a game comes from one of its authors on the base branch, so nobody can
take over someone else's game by editing its game.json; changes to the authors
list are printed so they stand out in review.

CLI:
    python -m harness.authors --all
    python -m harness.authors --base origin/main --pr-author <login> [--maintainer <owner>]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

LOGIN_RE = r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$"
_LOGIN = re.compile(LOGIN_RE)

Meta = dict
Changed = dict[str, tuple[Meta | None, Meta | None]]


def metadata_problems(meta: dict) -> list[str]:
    """Problems with the `authors` field of one game.json (empty = fine)."""
    authors = meta.get("authors")
    if authors is None:
        return ["game.json has no 'authors' (list of GitHub logins)"]
    if not isinstance(authors, list) or not authors:
        return ["'authors' must be a non-empty list of GitHub logins"]
    problems = []
    for a in authors:
        if not isinstance(a, str) or not _LOGIN.match(a):
            problems.append(f"'authors' entry {a!r} is not a valid GitHub login")
    return problems


def _logins(meta: dict | None) -> list[str]:
    authors = (meta or {}).get("authors")
    if not isinstance(authors, list):
        return []
    return [a for a in authors if isinstance(a, str)]


def _has(logins: list[str], login: str) -> bool:
    return login.lower() in {a.lower() for a in logins}


def check_pr(
    changed: Changed, pr_author: str, maintainers: list[str] | tuple[str, ...] = ()
) -> tuple[list[str], list[str]]:
    """(errors, notices) for the games a PR touches.

    `changed` maps a game dir to (game.json on the base branch | None,
    game.json in the PR head | None). `maintainers` (the repo owner) may change
    any game; format problems and authors changes are still reported for them."""
    errors: list[str] = []
    notices: list[str] = []
    is_maintainer = _has(list(maintainers), pr_author)
    for game, (base, head) in sorted(changed.items()):
        if base is None and head is None:
            continue
        if is_maintainer:
            pass
        elif base is None:  # new game
            if not _has(_logins(head), pr_author):
                errors.append(
                    f"{game}: new game: the PR author {pr_author!r} must be listed in its 'authors'"
                )
        elif not _has(_logins(base), pr_author):
            what = "removes" if head is None else "changes"
            errors.append(
                f"{game}: this PR {what} the game, but {pr_author!r} is not in the authors of "
                f"{game} on the base branch: a maintainer must approve this change"
            )
        if head is not None:
            errors.extend(f"{game}: {p}" for p in metadata_problems(head))
            if base is not None:
                before = {a.lower(): a for a in _logins(base)}
                after = {a.lower(): a for a in _logins(head)}
                added = [after[k] for k in after if k not in before]
                removed = [before[k] for k in before if k not in after]
                if added or removed:
                    diff = " ".join([*(f"+{a}" for a in added), *(f"-{a}" for a in removed)])
                    notices.append(f"{game}: authors changed: {diff}")
    return errors, notices


# ── git plumbing ──────────────────────────────────────────────────────────────

def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def _changed_games(base_ref: str) -> list[str]:
    out = _git("diff", "--name-only", f"{base_ref}...HEAD", "--", "games/")
    if out.returncode != 0:
        raise RuntimeError(f"git diff failed: {out.stderr.strip()}")
    games = set()
    for path in out.stdout.splitlines():
        parts = path.split("/")
        if len(parts) >= 3 and parts[0] == "games":
            games.add(f"games/{parts[1]}")
    return sorted(games)


def _base_meta(base_ref: str, game: str) -> dict | None:
    out = _git("show", f"{base_ref}:{game}/game.json")
    if out.returncode != 0:
        return None
    try:
        return json.loads(out.stdout)
    except ValueError:
        return {}


def _head_meta(game: str) -> dict | None:
    path = Path(game) / "game.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness.authors", description=__doc__.split("\n\n")[0])
    parser.add_argument("--all", action="store_true",
                        help="check that every games/*/game.json has valid 'authors'")
    parser.add_argument("--base", help="base ref of the PR, e.g. origin/main")
    parser.add_argument("--pr-author", help="GitHub login of the PR author")
    parser.add_argument("--maintainer", action="append", default=[],
                        help="login allowed to change any game (repeatable; CI passes the repo owner)")
    args = parser.parse_args(argv)

    errors: list[str] = []
    notices: list[str] = []
    if args.all:
        for meta_file in sorted(Path("games").glob("*/game.json")):
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            errors.extend(f"{meta_file.parent.as_posix()}: {p}" for p in metadata_problems(meta))
    if args.base or args.pr_author:
        if not (args.base and args.pr_author):
            parser.error("--base and --pr-author go together")
        changed = {g: (_base_meta(args.base, g), _head_meta(g)) for g in _changed_games(args.base)}
        e, n = check_pr(changed, args.pr_author, args.maintainer)
        errors += e
        notices += n
    if not (args.all or args.base):
        parser.error("nothing to check: pass --all and/or --base/--pr-author")

    for n in notices:
        print(f"NOTICE: {n}")
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)
    if not errors:
        print("OK: game authors check passed")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
