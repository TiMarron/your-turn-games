"""Last Coin Loses (reference game with a Vite + Vue client).

Two players alternate taking 1 or 2 coins from a pile of 3; whoever takes the
last coin loses. Pure reducer over a JSON dict — the client framework (Vue here)
is irrelevant to this file.
"""


def new_game(config):
    return {"phase": "playing", "winner": None, "move_number": 0,
            "current_player": 0, "coins": 3}


def legal_actions(state, player):
    if state["phase"] == "finished" or player != state["current_player"]:
        return {}
    return {"take": [{"n": n} for n in (1, 2) if n <= state["coins"]]}


def apply_action(state, player, action_type, data):
    if player != state["current_player"]:
        raise ValueError("not your turn")
    if action_type != "take":
        raise ValueError(f"unknown action: {action_type}")
    n = data.get("n")
    if n not in (1, 2) or n > state["coins"]:
        raise ValueError("illegal take")
    s = dict(state)
    s["coins"] = state["coins"] - n
    s["move_number"] = state["move_number"] + 1
    if s["coins"] <= 0:
        # took the last coin -> this player loses, the other wins
        s["phase"] = "finished"
        s["winner"] = 1 - player
        s["current_player"] = -1
    else:
        s["current_player"] = 1 - player
    return s


def snapshot(state):
    return {"phase": state["phase"], "winner": state["winner"],
            "move_number": state["move_number"], "current_player": state["current_player"],
            "coins": state["coins"]}
