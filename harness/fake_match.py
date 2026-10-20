"""In-memory match that drives a reducer like the platform server does."""
from __future__ import annotations

from harness.sandbox_runner import ReducerMissing, run


class FakeMatch:
    def __init__(self, source: str, n_players: int = 2, config: dict | None = None):
        self.source = source
        self.n_players = n_players
        self.state = run(source, "new_game", [config or {}])
        # initialize_for_players is optional; apply if present.
        try:
            self.state = run(source, "initialize_for_players", [self.state, n_players])
        except ReducerMissing:
            pass

    def players_to_move(self) -> list:
        """Seats allowed to move now, derived from the state (server convention)."""
        if "players_to_move" in self.state:
            return list(self.state["players_to_move"])
        cp = self.state.get("current_player", 0)
        return [] if cp == -1 else [cp]

    def legal_actions(self, seat: int) -> dict:
        return run(self.source, "legal_actions", [self.state, seat])

    def snapshot(self) -> dict:
        return run(self.source, "snapshot", [self.state])

    def apply(self, seat: int, action_type: str, data: dict) -> dict:
        """Apply one action; advance state; return the new public snapshot."""
        self.state = run(
            self.source, "apply_action", [self.state, seat, action_type, data]
        )
        return self.snapshot()
