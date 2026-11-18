from __future__ import annotations
import argparse
import json
import os
import tempfile
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


def write_next_puzzle(game: dict, category: str) -> Path:
    #Write to a temp file, then link it to the next free number (os.link fails if taken).
    folder = GAMES_DIR / category.lower()
    folder.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=folder, suffix=".tmp", delete=False, encoding="utf-8") as tmp:
        tmp.write(json.dumps(game, indent=2))
    try:
        while True:
            out_path = next_puzzle_path(category)
            try:
                os.link(tmp.name, out_path)
                return out_path
            except FileExistsError:
                pass
    finally:
        os.unlink(tmp.name)


def is_duplicate(game: dict, category: str) -> bool:
    #Same mines and clues as a puzzle we already saved
    for p in (GAMES_DIR / category.lower()).glob("*.json"):
        old = json.loads(p.read_text(encoding="utf-8"))
        if old["mine_cells"] == game["mine_cells"] and old["messages_by_cell"] == game["messages_by_cell"]:
            return True
    return False


def save(diff_name: str, seed: int | None = None, mines: int | None = None, clues: int | None = None) -> Path | None:
    """
    Generate a MineFOL game and save it as the next puzzle of its difficulty.
    Args:
        diff_name: "Easy", "Medium", or "Hard"
        seed: Random seed
        mines, clues: fixed mine count and number of clue cells (default: random in the difficulty's range)
    Returns the new file, or None if the puzzle was a duplicate.
    """
    diff = {"Easy": EASY, "Medium": MEDIUM, "Hard": HARD}[diff_name]

    print(f"Generating {diff_name} game...")
    print(f"  Grid: {diff.n}x{diff.n}")

    game = generate_game(diff, seed=seed, mines=mines, message_cells=clues)
    print(f"  Mines: {game['mines']}")

    grid = Grid(n=game['n'])
    print(f"\n  Generated {len(game['messages_by_cell'])} messages")
    print(f"  Sample messages:")

    for i, (cell_key, msg) in enumerate(list(game['messages_by_cell'].items())[:3]):
        display = parse_formula_for_display(msg, grid)
        print(f"    [{cell_key}] {display}")

    if is_duplicate(game, diff_name):
        print("\n    Skipped: same puzzle as one already saved")
        return None

    out_path = write_next_puzzle(game, diff_name)

    print(f"\n    Saved to: {out_path.relative_to(PROJECT_ROOT)}")
    return out_path


if __name__ == "__main__":
    # Usage: python save_game.py [Easy|Medium|Hard] [count] [--mines N] [--clues N]
    #   no arguments: one new puzzle per difficulty
    #   seed=None triggers random generation in generator.py
    parser = argparse.ArgumentParser(description="Generate MineFOL puzzles.")
    parser.add_argument("difficulty", nargs="?", help="Easy, Medium or Hard (default: one of each)")
    parser.add_argument("count", nargs="?", type=int, default=1, help="how many puzzles (default: 1)")
    parser.add_argument("--mines", type=int, help="fixed mine count (default: random in the difficulty's range)")
    parser.add_argument("--clues", type=int, help="fixed number of clue cells (default: random in the range)")
    args = parser.parse_args()
    names = [args.difficulty.capitalize()] if args.difficulty else ["Easy", "Medium", "Hard"]
    count = args.count

    print("=" * 70)
    print("MineFOL Game Generator")
    print("=" * 70)
    print()

    for name in names:
        for _ in range(count):
            try:
                save(name, seed=None, mines=args.mines, clues=args.clues)
                print()
            except Exception as e:
                print(f"  ✗ Failed to generate {name}: {e}")
                import traceback

                traceback.print_exc()
                print()

    print("=" * 70)
    print(f"Generation complete! Puzzles saved to {GAMES_DIR.relative_to(PROJECT_ROOT)}/<difficulty>/")
    print("=" * 70)