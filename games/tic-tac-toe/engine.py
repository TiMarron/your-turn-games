"""Tic-tac-toe reducer (reference game).

Pure functions over a JSON dict state — the your-turn-games author contract.
Seat 0 is X, seat 1 is O. State (and snapshot) carry phase/winner/move_number/
current_player plus the board (9 cells, None | 0 | 1).
"""

_WIN_LINES = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),  # rows
    (0, 3, 6), (1, 4, 7), (2, 5, 8),  # cols
    (0, 4, 8), (2, 4, 6),             # diagonals
]


def new_game(config):
    return {
        "phase": "playing", "winner": None, "move_number": 0,
        "current_player": 0, "board": [None] * 9,
    }


def legal_actions(state, player):
    if state["phase"] == "finished" or player != state["current_player"]:
        return {}
    return {"place": [{"cell": i} for i, v in enumerate(state["board"]) if v is None]}


def _winner(board):
    for a, b, c in _WIN_LINES:
        if board[a] is not None and board[a] == board[b] == board[c]:
            return board[a]
    return None


def apply_action(state, player, action_type, data):
    if state["phase"] == "finished":
        raise ValueError("game already finished")
    if player != state["current_player"]:
        raise ValueError("not your turn")
    if action_type != "place":
        raise ValueError(f"unknown action: {action_type}")
    cell = data.get("cell")
    if not isinstance(cell, int) or isinstance(cell, bool) or not (0 <= cell < 9):
        raise ValueError("invalid cell")
    if state["board"][cell] is not None:
        raise ValueError("cell already taken")

    board = list(state["board"])
    board[cell] = player
    s = dict(state)
    s["board"] = board
    s["move_number"] = state["move_number"] + 1

    w = _winner(board)
    if w is not None:
        s["phase"] = "finished"
        s["winner"] = w
        s["current_player"] = -1
    elif all(v is not None for v in board):  # board full, no line -> draw
        s["phase"] = "finished"
        s["winner"] = None
        s["current_player"] = -1
    else:
        s["current_player"] = 1 - player
    return s


def snapshot(state):
    return {
        "phase": state["phase"], "winner": state["winner"],
        "move_number": state["move_number"], "current_player": state["current_player"],
        "board": list(state["board"]),
    }
