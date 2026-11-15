from __future__ import annotations
import json
import sys
from pathlib import Path

from generator import EASY, MEDIUM, HARD, generate_game
from runner import PROJECT_ROOT
from message_translate import parse_formula_for_display
from grid import Grid

# Puzzles are numbered per category: build/games/<category>/001.json, 002.json, ...
# Numbers never change, so "Hard #2" always means the same puzzle.
GAMES_DIR = PROJECT_ROOT / "build" / "games"


def next_puzzle_path(category: str) -> Path:
    folder = GAMES_DIR / category.lower()
    folder.mkdir(parents=True, exist_ok=True)
    numbers = [int(p.stem) for p in folder.glob("*.json") if p.stem.isdigit()]
    return folder / f"{max(numbers, default=0) + 1:03d}.json"


def is_duplicate(game: dict, category: str) -> bool:
    #Same mines and clues as a puzzle we already saved
    for p in (GAMES_DIR / category.lower()).glob("*.json"):
        old = json.loads(p.read_text(encoding="utf-8"))
        if old["mine_cells"] == game["mine_cells"] and old["messages_by_cell"] == game["messages_by_cell"]:
            return True
    return False


def save(diff_name: str, seed: int | None = None) -> Path | None:
    """
    Generate a MineFOL game and save it as the next puzzle of its difficulty.
    Args:
        diff_name: "Easy", "Medium", or "Hard"
        seed: Random seed
    Returns the new file, or None if the puzzle was a duplicate.
    """
    diff = {"Easy": EASY, "Medium": MEDIUM, "Hard": HARD}[diff_name]

    print(f"Generating {diff_name} game...")
    print(f"  Grid: {diff.n}x{diff.n}")
    print(f"  Mines: {diff.mines}")

    game = generate_game(diff, seed=seed)

    grid = Grid(n=game['n'])
    print(f"\n  Generated {len(game['messages_by_cell'])} messages")
    print(f"  Sample messages:")

    for i, (cell_key, msg) in enumerate(list(game['messages_by_cell'].items())[:3]):
        display = parse_formula_for_display(msg, grid)
        print(f"    [{cell_key}] {display}")

    if is_duplicate(game, diff_name):
        print("\n    Skipped: same puzzle as one already saved")
        return None

    out_path = next_puzzle_path(diff_name)
    out_path.write_text(json.dumps(game, indent=2), encoding="utf-8")

    print(f"\n    Saved to: {out_path.relative_to(PROJECT_ROOT)}")
    return out_path


if __name__ == "__main__":
    # Usage: python save_game.py [Easy|Medium|Hard] [count]
    #   no arguments: one new puzzle per difficulty
    #   seed=None triggers random generation in generator.py
    names = [sys.argv[1].capitalize()] if len(sys.argv) > 1 else ["Easy", "Medium", "Hard"]
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    print("=" * 70)
    print("MineFOL Game Generator")
    print("=" * 70)
    print()

    for name in names:
        for _ in range(count):
            try:
                save(name, seed=None)
                print()
            except Exception as e:
                print(f"  ✗ Failed to generate {name}: {e}")
                import traceback

                traceback.print_exc()
                print()

    print("=" * 70)
    print(f"Generation complete! Puzzles saved to {GAMES_DIR.relative_to(PROJECT_ROOT)}/<difficulty>/")
    print("=" * 70)