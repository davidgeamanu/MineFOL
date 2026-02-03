from __future__ import annotations
import json
from pathlib import Path

from generator import EASY, MEDIUM, HARD, generate_game
from runner import PROJECT_ROOT
from message_translate import parse_formula_for_display
from grid import Grid


def save(diff_name: str, seed: int | None = None) -> Path:
    """
    Generate and save a MineFOL game.
    Args:
        diff_name: "Easy", "Medium", or "Hard"
        seed: Random seed
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

    out_dir = PROJECT_ROOT / "build" / "games"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"game_{diff_name.lower()}.json"
    out_path.write_text(json.dumps(game, indent=2), encoding="utf-8")

    print(f"\n    Saved to: {out_path.relative_to(PROJECT_ROOT)}")
    return out_path


if __name__ == "__main__":
    print("=" * 70)
    print("MineFOL Game Generator")
    print("=" * 70)
    print()

    #Generate all three difficulties
    #seed=None triggers random generation in generator.py
    #for name, seed in [("Easy", 101), ("Medium", 202), ("Hard", 303)]:
    #for name, seed in [("Easy", None), ("Medium", None), ("Hard", None)]:
    #for name, seed in [("Easy", None)]:
    for name, seed in [("Easy", None), ("Medium", None), ("Hard", None)]:
        try:
            p = save(name, seed=seed)
            print()
        except Exception as e:
            print(f"  ✗ Failed to generate {name}: {e}")
            import traceback

            traceback.print_exc()
            print()

    print("=" * 70)
    print("Generation complete! Games saved to build/games/")
    print("=" * 70)