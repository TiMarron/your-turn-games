"""Starter reducer. Replace the rules with your game.

Contract (all functions are pure over a JSON dict `state`):
  new_game(config) -> state
  legal_actions(state, player) -> {action_type: [data, ...]}   (empty if can't act)
  apply_action(state, player, action_type, data) -> new state  (raise on illegal)
  snapshot(state) -> public view (no hidden info)
State MUST contain: phase ('playing'|'finished'), winner (seat|None),
move_number (int), current_player (seat int; -1 = nobody). Players are 0-indexed.
This starter: players take turns pressing 'go'; after each has gone once, P0 wins.
"""


def new_game(config):
    return {"phase": "playing", "winner": None, "move_number": 0,
            "current_player": 0, "went": [False, False]}


def legal_actions(state, player):
    if state["phase"] == "finished" or player != state["current_player"]:
        return {}
    return {"go": [{}]}


def apply_action(state, player, action_type, data):
    if player != state["current_player"]:
        raise ValueError("not your turn")
    if action_type != "go":
        raise ValueError(f"unknown action: {action_type}")
    s = dict(state); s["went"] = list(state["went"])
    s["went"][player] = True
    s["move_number"] = state["move_number"] + 1
    if all(s["went"]):
        s["phase"] = "finished"; s["winner"] = 0; s["current_player"] = -1
    else:
        s["current_player"] = 1 - player
    return s


def snapshot(state):
    return {"phase": state["phase"], "winner": state["winner"],
            "move_number": state["move_number"], "current_player": state["current_player"],
            "went": state["went"]}
