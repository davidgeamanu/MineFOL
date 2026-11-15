from __future__ import annotations

import re
import sys
import json
from pathlib import Path
from typing import Any, Dict, Tuple, List

from flask import Flask, jsonify, render_template, request

THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]
SRC_DIR = PROJECT_ROOT / "Python" / "src"
sys.path.insert(0, str(SRC_DIR))

# Python/src is on sys.path (above), so these work from any working directory
from grid import Grid
from game_state import GameState
from logic_engine import LogicEngine
from message_translate import parse_formula_for_display

Coord = Tuple[int, int]

app = Flask(__name__, static_folder="static", template_folder="templates")
ENGINE = LogicEngine()

# In-memory sessions
SESSIONS: Dict[str, Dict[str, Any]] = {}


def _parse_cell_key(k: str) -> Coord:
    r, c = k.split(",")
    return int(r), int(c)


def _load_game(diff: str) -> dict:
    p = PROJECT_ROOT / "build" / "games" / f"game_{diff.lower()}.json"
    if not p.exists():
        raise FileNotFoundError(f"Missing game file: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _new_state_from_game(game: dict) -> tuple[Grid, GameState]:
    n = game["n"]
    mines = game["mines"]
    grid = Grid(n=n)

    state = GameState(n=n, mines=mines)
    state.mine_cells = set(tuple(x) for x in game["mine_cells"])
    state.messages_by_cell = {_parse_cell_key(k): v for k, v in game["messages_by_cell"].items()}

    sr, sc = game["start"]
    state.step_into((sr, sc))
    return grid, state


def _state_to_payload(grid: Grid, state: GameState, highlight_safe: List[Coord] = None, highlight_forced: List[Coord] = None) -> dict:

    #Convert game state to JSON payload.

    if highlight_safe is None: highlight_safe = []
    if highlight_forced is None: highlight_forced = []

    cells = []
    for rr in range(1, grid.n + 1):
        row = []
        for cc in range(1, grid.n + 1):
            has_msg = (rr, cc) in state.messages_by_cell
            visited = (rr, cc) in state.visited

            cell_msg = ""
            if visited and has_msg:
                raw_msg = state.messages_by_cell[(rr, cc)]
                cell_msg = parse_formula_for_display(raw_msg, grid)

            row.append({
                "r": rr,
                "c": cc,
                "isCurrent": (rr, cc) == state.pos,
                "visited": visited,
                "flagged": (rr, cc) in state.flagged,
                "provablySafe": (rr, cc) in highlight_safe,
                "forcedHint": (rr, cc) in highlight_forced,
                "hasMessage": has_msg,
                "showMessageIcon": (visited and has_msg),
                "message": cell_msg,
            })
        cells.append(row)

    success = (len(state.flagged) == state.mines and state.flagged == state.mine_cells)

    current_msg_display = ""
    if state.last_cell_message:
        current_msg_display = parse_formula_for_display(state.last_cell_message, grid)

    display_messages = []
    for msg in state.player_messages[-10:]:
        display_messages.append(parse_formula_for_display(msg, grid))

    return {
        "n": grid.n,
        "mines": state.mines,
        "pos": list(state.pos),
        "dead": state.dead,
        "success": success,
        "currentMessage": current_msg_display,
        "messages": display_messages,
        "cells": cells,
        "flaggedCount": len(state.flagged),
    }


def _describe_fact(fact: str, state: GameState, grid: Grid) -> str:

    #Turn a knowledge-base entry into a sentence for the player.

    for (r, c), msg in state.messages_by_cell.items():
        if msg.strip() == fact:
            return f"clue at ({r},{c}): {parse_formula_for_display(fact, grid)}"

    m = re.fullmatch(r"(-?)mine\((\d+),(\d+)\)", fact)
    if m and m.group(1):
        return f"({m.group(2)},{m.group(3)}) is safe (you visited it)"
    if m:
        return f"({m.group(2)},{m.group(3)}) is a flagged mine"
    return parse_formula_for_display(fact, grid)


def _get_session_id() -> str:
    return "default"


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/new_game")
def api_new_game():
    """Generate new game - NO Prover9 calls."""
    data = request.get_json(force=True)
    diff = data.get("difficulty", "Easy")

    game = _load_game(diff)
    grid, state = _new_state_from_game(game)

    sid = _get_session_id()
    SESSIONS[sid] = {"diff": diff, "grid_n": grid.n, "state": state}

    # Return state with NO safe move hints
    return jsonify(_state_to_payload(grid, state))


@app.post("/api/load_custom")
def api_load_custom():
    custom_path = PROJECT_ROOT / "build" / "games" / "hard_6x6_example_handmade.json"

    if not custom_path.exists():
        return jsonify({"error": f"Custom file not found at: {custom_path}"}), 404

    try:
        game = json.loads(custom_path.read_text(encoding="utf-8"))
        grid, state = _new_state_from_game(game)

        sid = _get_session_id()
        SESSIONS[sid] = {"diff": "Custom", "grid_n": grid.n, "state": state}

        return jsonify({
            "info": "Loaded custom 6x6 handmade puzzle.",
            **_state_to_payload(grid, state)
        })
    except Exception as e:
        return jsonify({"error": f"Failed to load custom game: {e}"}), 500


@app.get("/api/show_solution")
def api_show_solution():
    sid = _get_session_id()
    if sid not in SESSIONS:
        return jsonify({"error": "No game"}), 400

    grid = Grid(n=SESSIONS[sid]["grid_n"])
    state: GameState = SESSIONS[sid]["state"]

    # Gather all mines for "Forced Hint" (Red Flash)
    all_mines = list(state.mine_cells)

    # Gather all non-mines for "Safe Hint" (Green Flash)
    all_safe = []
    for r in range(1, grid.n + 1):
        for c in range(1, grid.n + 1):
            if (r, c) not in state.mine_cells and (r, c) not in state.visited:
                all_safe.append((r, c))

    return jsonify({
        "info": "👀 Solution revealed!",
        **_state_to_payload(grid, state, highlight_safe=all_safe, highlight_forced=all_mines)
    })

@app.get("/api/state")
def api_state():

    sid = _get_session_id()
    if sid not in SESSIONS:
        game = _load_game("Easy")
        grid, state = _new_state_from_game(game)
        SESSIONS[sid] = {"diff": "Easy", "grid_n": grid.n, "state": state}

    grid = Grid(n=SESSIONS[sid]["grid_n"])
    state: GameState = SESSIONS[sid]["state"]

    # Return state with NO safe move hints
    return jsonify(_state_to_payload(grid, state))


@app.post("/api/move")
def api_move():

    #Move to adjacent cell
    #Risky moves allowed - player can step anywhere adjacent.
    #If they step on a mine, game over.

    sid = _get_session_id()
    if sid not in SESSIONS:
        return jsonify({"error": "No game"}), 400

    data = request.get_json(force=True)
    rr = int(data["r"])
    cc = int(data["c"])

    grid = Grid(n=SESSIONS[sid]["grid_n"])
    state: GameState = SESSIONS[sid]["state"]

    # Check if game is over
    success = (len(state.flagged) == state.mines and state.flagged == state.mine_cells)
    if state.dead or success:
        return jsonify(_state_to_payload(grid, state))

    # Must be adjacent (4-neighborhood)
    r, c = state.pos
    if (rr, cc) not in grid.neighbors4(r, c):
        return jsonify({
            "error": "Invalid move (must move to an adjacent cell).",
            **_state_to_payload(grid, state)
        }), 200

    # Check if stepping on a mine
    if (rr, cc) in state.mine_cells:
        state.dead = True
        state.pos = (rr, cc)
        state.visited.add((rr, cc))
        return jsonify({
            "error": "💥 Stepped on a mine. GAME OVER!",
            **_state_to_payload(grid, state)
        }), 200

    state.step_into((rr, cc))

    # Return updated state with NO safe hints
    return jsonify(_state_to_payload(grid, state))


@app.post("/api/flag")
def api_flag():
    #Flag a cell as mine. Uses Mace4 to check if forced.
    sid = _get_session_id()
    if sid not in SESSIONS:
        return jsonify({"error": "No game"}), 400

    data = request.get_json(force=True)
    rr = int(data["r"])
    cc = int(data["c"])

    grid = Grid(n=SESSIONS[sid]["grid_n"])
    state: GameState = SESSIONS[sid]["state"]

    if state.dead:
        return jsonify(_state_to_payload(grid, state))

    if not grid.in_bounds(rr, cc):
        return jsonify({
            "error": "Out of bounds.",
            **_state_to_payload(grid, state)
        }), 200

    if (rr, cc) in state.flagged:
        return jsonify(_state_to_payload(grid, state))

    kb = state.collected_messages.copy()
    for (fr, fc) in state.flagged:
        kb.append(f"mine({fr},{fc})")

    # Check if forced mine using Mace4 (this IS slow, but only when flagging)
    print(f"[FLAG] Checking if ({rr},{cc}) is forced mine using Mace4...")
    #forced = ENGINE.is_forced_mine(state.n, state.mines, state.collected_messages, rr, cc)
    forced = ENGINE.is_forced_mine(state.n, state.mines, kb, rr, cc)

    if forced:
        state.flagged.add((rr, cc))
        return jsonify({
            "info": f"🚩 Flagged mine at ({rr},{cc}) [forced by logic].",
            **_state_to_payload(grid, state)
        }), 200

    # Risky guess
    if (rr, cc) in state.mine_cells:
        state.flagged.add((rr, cc))
        return jsonify({
            "info": f"🚩 Flagged mine at ({rr},{cc}) [correct guess].",
            **_state_to_payload(grid, state)
        }), 200
    else:
        state.dead = True
        return jsonify({
            "error": "❌ Wrong flag. GAME OVER.",
            **_state_to_payload(grid, state)
        }), 200


@app.get("/api/hint_safe")
def api_hint_safe():

    #Compute and show provably safe moves using Mace4 (Prover9 explains them on demand).
    sid = _get_session_id()
    if sid not in SESSIONS:
        return jsonify({"error": "No game"}), 400

    grid = Grid(n=SESSIONS[sid]["grid_n"])
    state: GameState = SESSIONS[sid]["state"]

    if state.dead:
        return jsonify({
            "info": "Game over - no hints available.",
            **_state_to_payload(grid, state)
        })

    print(f"[HINT SAFE] Computing safe moves from ({state.pos[0]},{state.pos[1]}) using Mace4...")

    kb = state.collected_messages.copy()
    for (fr, fc) in state.flagged:
        kb.append(f"mine({fr},{fc})")

    # This calls Mace4 once per neighbor
    r, c = state.pos
    #safe_moves = ENGINE.legal_moves(grid, state.mines, state.collected_messages, r, c)
    all_safe_moves = ENGINE.legal_moves(grid, state.mines, kb, state.pos[0], state.pos[1])

    # Filter out visited cells
    safe_moves = [m for m in all_safe_moves if m not in state.visited]

    print(f"[HINT SAFE] Found {len(safe_moves)} safe moves: {safe_moves}")

    if safe_moves:
        moves_str = ", ".join([f"({rr},{cc})" for rr, cc in safe_moves])
        return jsonify({
            "safeMoves": safe_moves,
            "info": f"✅ Provably safe moves: {moves_str}",
            **_state_to_payload(grid, state, highlight_safe=safe_moves)  # Highlight them!
        })
    else:
        return jsonify({
            "info": "⚠️ No provably safe moves from current position.",
            **_state_to_payload(grid, state)
        })


@app.get("/api/explain_safe")
def api_explain_safe():

    #Explain why a cell is safe: Prover9 proves it and we list the facts the proof used.
    sid = _get_session_id()
    if sid not in SESSIONS:
        return jsonify({"error": "No game"}), 400

    rr = int(request.args["r"])
    cc = int(request.args["c"])

    grid = Grid(n=SESSIONS[sid]["grid_n"])
    state: GameState = SESSIONS[sid]["state"]

    kb = state.collected_messages.copy()
    for (fr, fc) in state.flagged:
        kb.append(f"mine({fr},{fc})")

    # Only explain cells that really are safe (Mace4 decides, Prover9 explains)
    if not ENGINE.is_provably_safe(state.n, state.mines, kb, rr, cc):
        return jsonify({"explanation": f"({rr},{cc}) is not provably safe with what you know so far."})

    print(f"[EXPLAIN] Asking Prover9 why ({rr},{cc}) is safe...")
    result = ENGINE.explain_safe(state.n, state.mines, kb, rr, cc)

    if result is None:
        return jsonify({
            "explanation": f"({rr},{cc}) is safe, but Prover9 found no short explanation "
                           f"(usually this means it follows from counting the mines)."
        })

    used, used_mine_count = result
    lines = [f"({rr},{cc}) is safe because:"]
    for fact in used:
        lines.append(f"• {_describe_fact(fact, state, grid)}")
    if used_mine_count:
        lines.append(f"• there are exactly {state.mines} mines")

    return jsonify({"explanation": "\n".join(lines)})


@app.get("/api/hint_forced")
def api_hint_forced():
    #Find all forced mines using Mace4 (VERY slow - checks all unflagged cells).

    sid = _get_session_id()
    if sid not in SESSIONS:
        return jsonify({"error": "No game"}), 400

    grid = Grid(n=SESSIONS[sid]["grid_n"])
    state: GameState = SESSIONS[sid]["state"]

    print(f"[HINT FORCED] Scanning all cells for forced mines using Mace4 (this is slow)...")


    kb = state.collected_messages.copy()
    for (fr, fc) in state.flagged:
        kb.append(f"mine({fr},{fc})")

    forced = []
    for rr in range(1, grid.n + 1):
        for cc in range(1, grid.n + 1):
            if (rr, cc) in state.flagged or (rr, cc) in state.visited:
                continue
            #if ENGINE.is_forced_mine(state.n, state.mines, state.collected_messages, rr, cc):
            if ENGINE.is_forced_mine(state.n, state.mines, kb, rr, cc):
                forced.append((rr, cc))
                print(f"[HINT FORCED] Found forced mine at ({rr},{cc})")

    if forced:
        forced_str = ", ".join([f"({r},{c})" for r, c in forced])
        return jsonify({
            "forcedMines": forced,
            "info": f"🚩 Forced mines: {forced_str}",
            **_state_to_payload(grid, state, highlight_forced=forced)
        })
    else:
        return jsonify({
            "info": "No forced mines detected with current knowledge.",
            **_state_to_payload(grid, state)
        })


if __name__ == "__main__":
    print("=" * 70)
    print("MineFOL Web Server")
    print("=" * 70)
    print()
    print("Starting server at http://127.0.0.1:5000")
    print("Press Ctrl+C to stop")
    print("=" * 70)
    app.run(host="127.0.0.1", port=5000, debug=True)