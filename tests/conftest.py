"""Shared test fixtures: make `harness` importable and expose sample reducers."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# A tiny 2-player turn reducer used across harness tests (not a shipped game).
TURN_REDUCER = (
    "def new_game(config):\n"
    "    return {'phase': 'playing', 'winner': None, 'move_number': 0,\n"
    "            'current_player': 0, 'count': [0, 0]}\n"
    "def legal_actions(state, player):\n"
    "    if state['phase'] == 'finished' or player != state['current_player']:\n"
    "        return {}\n"
    "    return {'inc': [{}]}\n"
    "def apply_action(state, player, action_type, data):\n"
    "    if player != state['current_player']:\n"
    "        raise ValueError('not your turn')\n"
    "    s = dict(state); s['count'] = list(state['count'])\n"
    "    s['count'][player] += 1\n"
    "    s['move_number'] = state['move_number'] + 1\n"
    "    if s['count'][player] >= 2:\n"
    "        s['phase'] = 'finished'; s['winner'] = player; s['current_player'] = -1\n"
    "    else:\n"
    "        s['current_player'] = 1 - player\n"
    "    return s\n"
    "def snapshot(state):\n"
    "    return {'phase': state['phase'], 'winner': state['winner'],\n"
    "            'move_number': state['move_number'],\n"
    "            'current_player': state['current_player'], 'count': state['count']}\n"
)
