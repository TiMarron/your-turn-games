"""Infinite tic-tac-toe analytics (see template/analytics.py for the contract).

Questions it answers in the event explorer:
- Do winners play closer to the centre?   mark_placed: avg `ring`, group by seat_won
- Do players build on their own marks or block?   mark_placed: avg `touching_own`
  vs `touching_other`, split by seat_won
- How long are winning lines?   player summaries: dist `win_length`, filter won = true
"""

_NEIGHBOURS = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0)]


def on_step(prev, player, action_type, data, next, ctx):
    if action_type != "place":
        return []
    x, y = data["x"], data["y"]
    cells = prev["cells"]
    around = [cells.get("%d,%d" % (x + dx, y + dy)) for dx, dy in _NEIGHBOURS]
    return [{"name": "mark_placed", "props": {
        "x": x, "y": y,
        "ring": max(abs(x), abs(y)),
        "touching_own": sum(1 for c in around if c == player),
        "touching_other": sum(1 for c in around if c is not None and c != player),
    }}]


def on_finish(final, ctx):
    line = final.get("win_line") or []
    return [{"seat": seat, "props": {
        "marks": sum(1 for c in final["cells"].values() if c == seat),
        "win_length": len(line) if final.get("winner") == seat else 0,
    }} for seat in range(ctx["n_players"])]
