from __future__ import annotations

import os
import re
import sys
import json
import time
import secrets
from pathlib import Path
from typing import Any, Dict, Tuple, List

from flask import Flask, abort, jsonify, render_template, request, session

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
app.secret_key = os.environ.get("MINEFOL_SECRET_KEY") or secrets.token_hex(32)
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
ENGINE = LogicEngine()

# In-memory sessions, one game per browser
SESSIONS: Dict[str, Dict[str, Any]] = {}
LAST_SEEN: Dict[str, float] = {}
SESSION_IDLE_HOURS = 12
MAX_SESSIONS = 10_000
NO_GAME = "Your game has expired. Reload the page to start again."


def _parse_cell_key(k: str) -> Coord:
    r, c = k.split(",")
    return int(r), int(c)


GAMES_DIR = PROJECT_ROOT / "build" / "games"


def _load_puzzle(category: str, number: int) -> dict:
    p = GAMES_DIR / category / f"{number:03d}.json"
    if not p.exists():
        raise FileNotFoundError(f"Missing puzzle file: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _list_puzzles() -> list[dict]:

    #Every folder in build/games holding numbered puzzles (001.json, 002.json, ...) is a category,
    #so adding a category means adding a folder. Categories are ordered by the board size of their
    #first puzzle (Easy < Medium < Hard); at the same size the generated ones come before e.g. Custom.

    categories = []
    for folder in sorted(GAMES_DIR.iterdir()):
        numbers = sorted(int(p.stem) for p in folder.glob("*.json") if p.stem.isdigit()) if folder.is_dir() else []
        if not numbers:
            continue
        first = _load_puzzle(folder.name, numbers[0])
        categories.append(((first["n"], folder.name not in ("easy", "medium", "hard")), {
            "name": folder.name,
            "label": folder.name.capitalize(),
            "numbers": numbers,
        }))
    return [cat for _, cat in sorted(categories, key=lambda item: item[0])]


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

    # Knowledge base: every clue found so far, in the order found, with the cell it came from
    cell_of = {msg.strip(): cell for cell, msg in state.messages_by_cell.items() if cell in state.visited}
    clues = [{"cell": list(cell_of[msg]), "text": parse_formula_for_display(msg, grid)}
             for msg in state.player_messages if msg in cell_of]

    return {
        "n": grid.n,
        "mines": state.mines,
        "pos": list(state.pos),
        "dead": state.dead,
        "success": success,
        "clues": clues,
        "cells": cells,
        "flaggedCount": len(state.flagged),
    }


def _fact_for_player(fact: str, state: GameState, grid: Grid) -> dict:

    #Describe a knowledge-base entry used in a proof: a clue (with the cell it came from),
    #a visited cell ("-mine(r,c)"), or a flagged mine ("mine(r,c)").

    for (r, c), msg in state.messages_by_cell.items():
        if msg.strip() == fact and (r, c) in state.visited:
            return {"kind": "clue", "cell": [r, c], "text": parse_formula_for_display(fact, grid)}

    m = re.fullmatch(r"(-?)mine\((\d+),(\d+)\)", fact)
    if m:
        return {"kind": "visited" if m.group(1) else "flag", "cell": [int(m.group(2)), int(m.group(3))]}
    return {"kind": "other", "text": parse_formula_for_display(fact, grid)}


def _get_session_id() -> str:
    if "sid" not in session:
        session["sid"] = secrets.token_hex(16)
        _drop_idle_sessions()
    LAST_SEEN[session["sid"]] = time.time()
    return session["sid"]


def _drop_idle_sessions() -> None:
    cutoff = time.time() - SESSION_IDLE_HOURS * 3600
    for sid, seen in list(LAST_SEEN.items()):
        if seen < cutoff:
            LAST_SEEN.pop(sid, None)
            SESSIONS.pop(sid, None)
    if len(LAST_SEEN) > MAX_SESSIONS:
        oldest = sorted(list(LAST_SEEN.items()), key=lambda item: item[1])[:MAX_SESSIONS // 10]
        for sid, _ in oldest:
            LAST_SEEN.pop(sid, None)
            SESSIONS.pop(sid, None)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/<category>/<int:number>")
def puzzle_page(category: str, number: int):
    #A puzzle's own address, e.g. /hard/2; the page then opens that puzzle
    listed = {cat["name"]: cat["numbers"] for cat in _list_puzzles()}
    if number not in listed.get(category, []):
        abort(404)
    return render_template("index.html")


@app.get("/api/puzzles")
def api_puzzles():
    #Categories and puzzle numbers, for the puzzle picker.
    return jsonify({"categories": _list_puzzles()})


def _start_puzzle(category: str, number: int) -> dict:

    #Start a puzzle for this session and return its payload.

    grid, state = _new_state_from_game(_load_puzzle(category, number))
    sid = _get_session_id()
    SESSIONS[sid] = {"category": category, "number": number, "grid_n": grid.n, "state": state}
    return {"category": category, "number": number, **_state_to_payload(grid, state)}


@app.post("/api/new_game")
def api_new_game():
    """Start puzzle <number> of <category> - NO Prover9 calls."""
    data = request.get_json(force=True)
    category = str(data.get("category", ""))
    number = int(data.get("number", 1))

    # Only names and numbers we listed ourselves (they become a file path)
    listed = {cat["name"]: cat["numbers"] for cat in _list_puzzles()}
    if number not in listed.get(category, []):
        return jsonify({"error": f"No puzzle {category} #{number}."}), 404

    # Return state with NO safe move hints
    return jsonify(_start_puzzle(category, number))


@app.get("/api/show_solution")
def api_show_solution():
    sid = _get_session_id()
    if sid not in SESSIONS:
        return jsonify({"error": NO_GAME}), 400

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
        "info": "Solution revealed: red cells are mines, green cells are safe.",
        **_state_to_payload(grid, state, highlight_safe=all_safe, highlight_forced=all_mines)
    })

@app.get("/api/state")
def api_state():

    sid = _get_session_id()
    if sid not in SESSIONS:
        first = _list_puzzles()[0]
        return jsonify(_start_puzzle(first["name"], first["numbers"][0]))

    grid = Grid(n=SESSIONS[sid]["grid_n"])
    state: GameState = SESSIONS[sid]["state"]
    game = SESSIONS[sid]

    # Return state with NO safe move hints
    return jsonify({"category": game["category"], "number": game["number"], **_state_to_payload(grid, state)})


@app.post("/api/move")
def api_move():

    #Move to adjacent cell
    #Risky moves allowed - player can step anywhere adjacent.
    #If they step on a mine, game over.

    sid = _get_session_id()
    if sid not in SESSIONS:
        return jsonify({"error": NO_GAME}), 400

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
            "error": f"You stepped on a mine at ({rr},{cc}). Game over.",
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
        return jsonify({"error": NO_GAME}), 400

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
            "info": f"Flagged ({rr},{cc}): forced by logic.",
            **_state_to_payload(grid, state)
        }), 200

    # Risky guess
    if (rr, cc) in state.mine_cells:
        state.flagged.add((rr, cc))
        return jsonify({
            "info": f"Flagged ({rr},{cc}): it is a mine, but that was a guess.",
            **_state_to_payload(grid, state)
        }), 200
    else:
        state.dead = True
        return jsonify({
            "error": f"({rr},{cc}) is not a mine. Game over.",
            **_state_to_payload(grid, state)
        }), 200


@app.get("/api/hint_safe")
def api_hint_safe():

    #Compute and show provably safe moves using Mace4 (Prover9 explains them on demand).
    sid = _get_session_id()
    if sid not in SESSIONS:
        return jsonify({"error": NO_GAME}), 400

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
            "info": f"Provably safe moves: {moves_str}",
            **_state_to_payload(grid, state, highlight_safe=safe_moves)  # Highlight them!
        })
    else:
        return jsonify({
            "safeMoves": [],
            "info": "No provably safe moves from your position.",
            **_state_to_payload(grid, state)
        })


@app.get("/api/explain_safe")
def api_explain_safe():
    #Explain why a cell is safe: Prover9 proves it and we list the facts the proof used.
    return _explain(prove_mine=False)


@app.get("/api/explain_mine")
def api_explain_mine():
    #Explain why a cell must be a mine, the same way.
    return _explain(prove_mine=True)


def _explain(prove_mine: bool):
    sid = _get_session_id()
    if sid not in SESSIONS:
        return jsonify({"error": NO_GAME}), 400

    rr = int(request.args["r"])
    cc = int(request.args["c"])

    grid = Grid(n=SESSIONS[sid]["grid_n"])
    state: GameState = SESSIONS[sid]["state"]

    kb = state.collected_messages.copy()
    for (fr, fc) in state.flagged:
        kb.append(f"mine({fr},{fc})")

    # Only explain what Mace4 confirms (Mace4 decides, Prover9 explains)
    if prove_mine:
        if not ENGINE.is_forced_mine(state.n, state.mines, kb, rr, cc):
            return jsonify({"cell": [rr, cc], "status": "not_mine"})
    elif not ENGINE.is_provably_safe(state.n, state.mines, kb, rr, cc):
        return jsonify({"cell": [rr, cc], "status": "not_safe"})

    print(f"[EXPLAIN] Asking Prover9 why ({rr},{cc}) is {'a mine' if prove_mine else 'safe'}...")
    if prove_mine:
        result = ENGINE.explain_mine(state.n, state.mines, kb, rr, cc)
    else:
        result = ENGINE.explain_safe(state.n, state.mines, kb, rr, cc)

    # No proof within the time limit: usually it follows from counting the mines
    if result is None:
        return jsonify({"cell": [rr, cc], "status": "no_short_proof"})

    used, used_mine_count = result
    return jsonify({
        "cell": [rr, cc],
        "status": "proved",
        "facts": [_fact_for_player(fact, state, grid) for fact in used],
        "usesMineCount": used_mine_count,
        "mines": state.mines,
    })


@app.get("/api/hint_forced")
def api_hint_forced():
    #Find all forced mines using Mace4 (VERY slow - checks all unflagged cells).

    sid = _get_session_id()
    if sid not in SESSIONS:
        return jsonify({"error": NO_GAME}), 400

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
            "info": f"Forced mines: {forced_str}",
            **_state_to_payload(grid, state, highlight_forced=forced)
        })
    else:
        return jsonify({
            "forcedMines": [],
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