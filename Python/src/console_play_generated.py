from __future__ import annotations
import json
import sys

from grid import Grid
from game_state import GameState
from logic_engine import LogicEngine
from runner import PROJECT_ROOT


def parse_cell_key(k: str):
    r, c = k.split(",")
    return int(r), int(c)


def main():
    # Usage: python console_play_generated.py [category] [number]   (default: easy 1)
    category = sys.argv[1].lower() if len(sys.argv) > 1 else "easy"
    number = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    game_path = PROJECT_ROOT / "build" / "games" / category / f"{number:03d}.json"
    game = json.loads(game_path.read_text(encoding="utf-8"))

    n = game["n"]
    mines = game["mines"]
    grid = Grid(n=n)
    engine = LogicEngine()

    state = GameState(n=n, mines=mines)

    # Load configuration
    state.mine_cells = set(tuple(x) for x in game["mine_cells"])
    state.messages_by_cell = {parse_cell_key(k): v for k, v in game["messages_by_cell"].items()}

    start = tuple(game["start"])
    state.step_into(start)

    print(f"MineFOL generated game: {n}x{n}, mines={mines}")
    print("Goal: identify all mines logically (forced) or by risky guess.")
    print("Controls: w/a/s/d move | 'f' r c flag | 'h' hint safe moves | 'm' hint forced mines | 'q' quit")
    print("Start messages:", state.collected_messages)

    while True:
        if state.dead:
            print("GAME OVER (stepped on a mine).")
            break

        # Completion = all mines flagged (and no wrong flags)
        if len(state.flagged) == mines and state.flagged == state.mine_cells:
            print("SUCCESS: all mines identified correctly.")
            break

        r, c = state.pos
        legal = engine.legal_moves(grid, mines, state.collected_messages, r, c)

        print("\nPosition:", state.pos)
        print("Recent messages:")
        for m in state.collected_messages[-3:]:
            print(" ", m)
        print("Legal moves:", legal)
        print("Flagged:", len(state.flagged), "/", mines)

        cmd = input("Command: ").strip().lower()
        if cmd == "q":
            break

        # show provably safe moves from current position (Mace4)
        if cmd == "h":
            print("Provably safe moves from here:", legal)
            continue

        # scan for forced mines (Mace4 showcase)
        if cmd == "m":
            forced = []
            for rr in range(1, n + 1):
                for cc in range(1, n + 1):
                    if (rr, cc) in state.flagged:
                        continue

                    if engine.is_forced_mine(n, mines, state.collected_messages, rr, cc):
                        forced.append((rr, cc))
            if forced:
                print("Forced mines:", forced)
            else:
                print("No forced mines detected with current knowledge.")
            continue

        if cmd.startswith("f "):
            parts = cmd.split()
            if len(parts) != 3:
                print("Use: f <row> <col>")
                continue

            try:
                fr, fc = int(parts[1]), int(parts[2])
            except ValueError:
                print("Use: f <row> <col> (integers).")
                continue

            if not grid.in_bounds(fr, fc):
                print("Out of bounds.")
                continue

            if (fr, fc) in state.flagged:
                print("Already flagged.")
                continue

            forced = engine.is_forced_mine(n, mines, state.collected_messages, fr, fc)
            if forced:
                state.flagged.add((fr, fc))
                print(f"Flagged mine at ({fr},{fc}) [forced by logic].")
            else:

                if (fr, fc) in state.mine_cells:
                    state.flagged.add((fr, fc))
                    print(f"Flagged mine at ({fr},{fc}) [correct guess].")
                else:
                    state.dead = True
                    print("Wrong flag. GAME OVER.")
            continue

        drdc = {"w": (-1, 0), "s": (1, 0), "a": (0, -1), "d": (0, 1)}
        if cmd not in drdc:
            print("Invalid command.")
            continue

        rr, cc = r + drdc[cmd][0], c + drdc[cmd][1]
        if not grid.in_bounds(rr, cc):
            print("Out of bounds.")
            continue

        if (rr, cc) not in legal:
            print("Move blocked: Mace4 cannot prove safeness.")
            continue

        state.step_into((rr, cc))
        print("Moved to", state.pos)

    print("Exiting.")


if __name__ == "__main__":
    main()
