from __future__ import annotations
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from grid import Grid
from logic_engine import LogicEngine
from generator import validate_solvable_flag_all_mines

# YOUR CUSTOM BOARD CONFIGURATION
CUSTOM_GAME = {
    "n": 6, #nxn

    # Mines
    "mines": [
        (1, 4), (2, 6), (3, 1), (3, 4), (4, 3), (6, 5)
    ],

    # Messages
    "messages": {
        (1, 1): "((-mine(1,2) & -mine(2,1)) & (all x (-mine(5,x))))",
        (1, 2): "(all x (-mine(x,x)))",
        (1, 5): "((exists x mine(1,x)) & -mine(6,4))",
        (1, 6): "mine(3,1)",
        (2, 2): "(all x (-mine(x,2)))",
        (2, 3): "((-(exists x mine(x,6)) | -mine(4,1)) & -mine(6,3))",
        (3, 5): "(exists x mine(2,x))",
        (4, 1): "((-mine(1,4) | -mine(4,5)) & (-mine(6,1) -> -mine(1,5)))",
        (4, 4): "(mine(3,4) -> -mine(2,3))",
        (4, 5): "(-mine(3,6) & -mine(4,6))",
        (5, 2): "(all x (mine(4,x) -> mine(x,4)))",
        (5, 5): "mine(4,3)",
        (6, 3): "((-mine(6,1) & -mine(3,5)) & (-mine(6,6) -> -mine(5,6)))",
        (6, 4): "(-mine(1,3) & -mine(1,6))",
        (6, 6): "(-mine(2,4) & -mine(2,5))"
    }
}


def verify_board():
    n = CUSTOM_GAME["n"]
    mine_list = CUSTOM_GAME["mines"]
    mines = set(mine_list)
    messages = CUSTOM_GAME["messages"]

    print(f"Loading Custom {n}x{n} Board...")
    print(f"Mines: {len(mines)} at {mine_list}")
    print(f"Messages: {len(messages)} defined")

    grid = Grid(n=n)
    engine = LogicEngine()

    print("\n[1/2] Checking Logical Consistency (Mace4)...")
    if (1, 1) in mines:
        print("  CRITICAL ERROR: Start cell (1,1) contains a mine!")
        return

    #Check if messages contradict the actual board state + start safety
    all_msgs = ["-mine(1,1)"] + list(messages.values())

    #pass the real mine count to set up the domain correctly
    is_consistent = engine.is_configuration_consistent(n, len(mines), all_msgs)

    if is_consistent:
        print("   Configuration is logically consistent.")
    else:
        print("   WARNING: Configuration is INCONSISTENT.")
        print("   This means one of your messages contradicts the mine placement.")
        print("   (e.g., saying 'Row 1 safe' when (1,4) is a mine).")

    print("\n[2/2] Verifying Solvability (Virtual Agent Playthrough)...")

    is_solvable = validate_solvable_flag_all_mines(
        grid=grid,
        engine=engine,
        mines=mines,
        messages_by_cell=messages,
        max_steps=1000
    )

    if is_solvable:
        print("\n  SUCCESS! The board is fully solvable using Logic.")
    else:
        print("\n  FAILURE. The logical agent got stuck.")
        print("   It could not prove a safe move or force a mine.")


if __name__ == "__main__":
    verify_board()