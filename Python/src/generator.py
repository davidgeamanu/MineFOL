from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple
from collections import deque

from grid import Grid
from logic_engine import LogicEngine
from message_generator import MessageGenerator

Coord = Tuple[int, int]


@dataclass(frozen=True)
class Difficulty:
    name: str
    n: int
    mines: int
    message_cells: int


# Adjust for reliability/speed:
# Easy: 4x4
EASY = Difficulty("Easy", n=4, mines=3, message_cells=8)
# Medium: 5x5
MEDIUM = Difficulty("Medium", n=5, mines=4, message_cells=14)
# Hard: 6x6
HARD = Difficulty("Hard", n=6, mines=5, message_cells=17)


def random_mines(grid: Grid, mine_count: int, start: Coord = (1, 1)) -> Set[Coord]:
    #Generate random mine positions
    cells = [(r, c) for r in range(1, grid.n + 1) for c in range(1, grid.n + 1) if (r, c) != start]
    return set(random.sample(cells, mine_count))


def bfs_reachable(grid: Grid, safe: Set[Coord], start: Coord) -> Set[Coord]:
    # Return all safe cells reachable from start via BFS
    q = deque([start])
    seen = {start}
    while q:
        u = q.popleft()
        for v in grid.neighbors4(*u):
            if v in safe and v not in seen:
                seen.add(v)
                q.append(v)
    return seen


def build_spanning_tree(grid: Grid, safe: Set[Coord], start: Coord) -> Dict[Coord, List[Coord]]:
    #Build BFS spanning tree over safe cells from start
    parent: Dict[Coord, Coord | None] = {start: None}
    children: Dict[Coord, List[Coord]] = {start: []}
    q = deque([start])
    seen = {start}

    while q:
        u = q.popleft()
        for v in grid.neighbors4(*u):
            if v in safe and v not in seen:
                seen.add(v)
                parent[v] = u
                children.setdefault(u, []).append(v)
                children.setdefault(v, [])
                q.append(v)

    return children


def validate_solvable_flag_all_mines(grid: Grid, engine: LogicEngine, mines: Set[Coord], messages_by_cell: Dict[Coord, str], max_steps: int = 500) -> bool:

    n = grid.n
    total_mines = len(mines)
    start = (1, 1)
    visited = {start}
    flagged = set()

    kb = ["-mine(1,1)"]
    if start in messages_by_cell:
        kb.append(messages_by_cell[start])

    # Frontier: Unvisited neighbors of visited cells
    frontier = set()
    for nbr in grid.neighbors4(*start):
        frontier.add(nbr)

    for _ in range(max_steps):
        if len(flagged) == total_mines:
            return True

        frontier_list = sorted(list(frontier))

        # 1) Try PROVABLY SAFE (Mace4: no model puts a mine there)
        # Prover9 can't answer "not provable" before its timeout, so it was slow here
        found_safe = None
        for (r, c) in frontier_list:
            if engine.is_provably_safe(n, total_mines, kb, r, c):
                found_safe = (r, c)
                break

        if found_safe:
            visited.add(found_safe)
            frontier.remove(found_safe)
            for nbr in grid.neighbors4(*found_safe):
                if nbr not in visited and nbr not in flagged:
                    frontier.add(nbr)

            kb.append(f"-mine({found_safe[0]},{found_safe[1]})")
            if found_safe in messages_by_cell:
                kb.append(messages_by_cell[found_safe])

            continue

        # 2) Try FORCED MINE (Mace4)
        found_mine = None
        for (r, c) in frontier_list:
            if engine.is_forced_mine(n, total_mines, kb, r, c):
                found_mine = (r, c)
                break

        if found_mine:
            flagged.add(found_mine)
            frontier.remove(found_mine)
            kb.append(f"mine({found_mine[0]},{found_mine[1]})")
            continue

        # 3) Stuck
        return False

    return False


def _pick_unlock_target(grid: Grid, cell: Coord, children: Dict[Coord, List[Coord]], safe: Set[Coord]) -> Coord | None:
    if cell in children and children[cell]:
        return random.choice(children[cell])
    nbrs = [n for n in grid.neighbors4(*cell) if n in safe]
    if nbrs:
        return random.choice(nbrs)
    if safe:
        return random.choice(list(safe))
    return None


def inject_global_clue(grid: Grid, mines: Set[Coord], messages: Dict[Coord, str]) -> None:
    #Finds a powerful global truth about the board (e.g. "Row 3 is safe") and adds it to the start message.
    #This increases chances of solvability.

    start = (1, 1)

    # Look for a safe row
    safe_row = None
    for r in range(1, grid.n + 1):
        if all((r, c) not in mines for c in range(1, grid.n + 1)):
            safe_row = r
            break

    # Look for a safe column
    safe_col = None
    if not safe_row:
        for c in range(1, grid.n + 1):
            if all((r, c) not in mines for r in range(1, grid.n + 1)):
                safe_col = c
                break

    # Create the clue
    clue = ""
    if safe_row:
        # "all x (-mine(row, x))"
        clue = f"(all x (-mine({safe_row},x)))"
    elif safe_col:
        # "all x (-mine(x, col))"
        clue = f"(all x (-mine(x,{safe_col})))"
    else:
        pass

    if clue:
        # Append this powerful clue to the start cell message
        if start in messages:
            existing = messages[start]
            messages[start] = f"({existing} & {clue})"
        else:
            messages[start] = clue


def generate_rich_messages(grid: Grid, mines: Set[Coord], safe: Set[Coord], children: Dict[Coord, List[Coord]], message_cells: Set[Coord], difficulty: str) -> Dict[Coord, str]:
    msg_gen = MessageGenerator(grid.n, mines, safe)
    messages: Dict[Coord, str] = {}
    start = (1, 1)

    if difficulty == "Easy":
        p_unlock = 0.85
    elif difficulty == "Medium":
        p_unlock = 0.75
    else:
        p_unlock = 0.65

    for cell in message_cells:
        if cell == start:
            messages[cell] = msg_gen.generate_helpful_start_message()
            continue

        complex_part = msg_gen.generate_message(difficulty)

        if random.random() < p_unlock:
            target = _pick_unlock_target(grid, cell, children, safe)
            if target is not None:
                tr, tc = target
                cr, cc = cell
                unlock_part = f"(-mine({cr},{cc}) -> -mine({tr},{tc}))"

                if difficulty in ("Medium", "Hard") and random.random() < 0.35:
                    u = _pick_unlock_target(grid, cell, children, safe)
                    if u is not None and u != target:
                        ur, uc = u
                        unlock_part = f"(-mine({cr},{cc}) -> (-mine({tr},{tc}) | mine({ur},{uc})))"

                messages[cell] = f"({complex_part} & {unlock_part})"
            else:
                messages[cell] = complex_part
        else:
            messages[cell] = complex_part

    return messages


def generate_game_rich(diff: Difficulty, seed: int | None = None, max_tries: int = 2000) -> dict:
    if seed is not None:
        random.seed(seed)

    grid = Grid(n=diff.n)
    start: Coord = (1, 1)

    print(f"Generating {diff.name} game...")

    for attempt in range(1, max_tries + 1):
        if attempt % 10 == 0:
            print(f" [Attempt {attempt}]", end="", flush=True)

        mines = random_mines(grid, diff.mines, start=start)
        safe = {(r, c) for r in range(1, grid.n + 1) for c in range(1, grid.n + 1)} - mines

        if start not in safe: continue
        if bfs_reachable(grid, safe, start) != safe: continue

        children = build_spanning_tree(grid, safe, start)
        for k in children: random.shuffle(children[k])

        msg_cells = {start}
        if start in children: msg_cells.update(children[start][:2])

        candidates = [c for c in safe if c not in msg_cells]
        random.shuffle(candidates)
        needed = max(0, diff.message_cells - len(msg_cells))
        msg_cells.update(candidates[:needed])

        messages = generate_rich_messages(
            grid=grid,
            mines=mines,
            safe=safe,
            children=children,
            message_cells=msg_cells,
            difficulty=diff.name
        )

        if start not in messages:
            msg_gen = MessageGenerator(grid.n, mines, safe)
            messages[start] = msg_gen.generate_helpful_start_message()

        inject_global_clue(grid, mines, messages)

        engine = LogicEngine()

        # Validation
        if not validate_solvable_flag_all_mines(
                grid=grid,
                engine=engine,
                mines=mines,
                messages_by_cell=messages
        ):
            continue

        print(f"\n[Success] Game generated on attempt {attempt}")
        return {
            "n": diff.n,
            "mines": diff.mines,
            "start": [1, 1],
            "mine_cells": sorted([[r, c] for (r, c) in mines]),
            "messages_by_cell": {f"{r},{c}": m for (r, c), m in messages.items()}
        }

    raise RuntimeError(f"Failed to generate game after {max_tries} attempts")


def generate_game(diff: Difficulty, seed: int | None = None, max_tries: int = 2000) -> dict:
    return generate_game_rich(diff, seed=seed, max_tries=max_tries)