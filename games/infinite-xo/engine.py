"""Infinite tic-tac-toe (gomoku-style) reducer.

Pure functions over a JSON dict state. Seat 0 is X (moves first), seat 1 is O.
The board is an unbounded grid: `cells` maps "x,y" -> seat for occupied cells.
First to get `win_length` (config, default 5) or more of their marks in an
unbroken row/column/diagonal wins. There are no draws: the board never fills.
"""

DEFAULT_WIN_LENGTH = 5
MIN_WIN_LENGTH = 3
COORD_LIMIT = 10000  # sanity bound on |x|, |y|; the grid is "infinite" in practice

_DIRECTIONS = [(1, 0), (0, 1), (1, 1), (1, -1)]


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _key(x, y):
    return "%d,%d" % (x, y)


def new_game(config):
    win_length = (config or {}).get("win_length", DEFAULT_WIN_LENGTH)
    if not _is_int(win_length) or win_length < MIN_WIN_LENGTH:
        raise ValueError("win_length must be an integer >= %d" % MIN_WIN_LENGTH)
    return {
        "phase": "playing", "winner": None, "move_number": 0,
        "current_player": 0, "win_length": win_length,
        "cells": {}, "last_move": None, "win_line": None,
    }


def legal_actions(state, player):
    if state["phase"] == "finished" or player != state["current_player"]:
        return {}
    cells = state["cells"]
    if not cells:
        return {"place": [{"x": 0, "y": 0}]}
    # The board is unbounded, so only suggest free cells adjacent to a mark.
    # apply_action accepts any free cell within COORD_LIMIT.
    free = set()
    for k in cells:
        x, y = (int(p) for p in k.split(","))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nk = _key(x + dx, y + dy)
                if nk not in cells:
                    free.add((x + dx, y + dy))
    return {"place": [{"x": x, "y": y} for x, y in sorted(free)]}


def _winning_line(cells, x, y, player, win_length):
    """Return the unbroken run through (x, y) if it is long enough, else None."""
    for dx, dy in _DIRECTIONS:
        line = [[x, y]]
        for sign in (1, -1):
            cx, cy = x + sign * dx, y + sign * dy
            while cells.get(_key(cx, cy)) == player:
                line.append([cx, cy])
                cx, cy = cx + sign * dx, cy + sign * dy
        if len(line) >= win_length:
            return sorted(line)
    return None


def apply_action(state, player, action_type, data):
    if state["phase"] == "finished":
        raise ValueError("game already finished")
    if player != state["current_player"]:
        raise ValueError("not your turn")
    if action_type != "place":
        raise ValueError("unknown action: %s" % action_type)
    x, y = data.get("x"), data.get("y")
    if not (_is_int(x) and _is_int(y)):
        raise ValueError("x and y must be integers")
    if abs(x) > COORD_LIMIT or abs(y) > COORD_LIMIT:
        raise ValueError("cell out of range")
    if _key(x, y) in state["cells"]:
        raise ValueError("cell already taken")

    cells = dict(state["cells"])
    cells[_key(x, y)] = player
    s = dict(state)
    s["cells"] = cells
    s["last_move"] = [x, y]
    s["move_number"] = state["move_number"] + 1

    line = _winning_line(cells, x, y, player, state["win_length"])
    if line is not None:
        s["phase"] = "finished"
        s["winner"] = player
        s["current_player"] = -1
        s["win_line"] = line
    else:
        s["current_player"] = 1 - player
    return s


def snapshot(state):
    return {
        "phase": state["phase"], "winner": state["winner"],
        "move_number": state["move_number"], "current_player": state["current_player"],
        "win_length": state["win_length"], "cells": dict(state["cells"]),
        "last_move": state["last_move"], "win_line": state["win_line"],
    }
