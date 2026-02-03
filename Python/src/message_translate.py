from __future__ import annotations
import re
from grid import Grid

_MINE_RC = re.compile(r"\bmine\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)")

def consts_to_coords(msg: str, grid: Grid) -> str:
    #Convert mine(cK) back into mine(r,c) for display.
    pat = re.compile(r"\bmine\s*\(\s*c(\d+)\s*\)")

    def repl(m: re.Match) -> str:
        idx = int(m.group(1))
        r, c = grid.index_to_rc(idx)
        return f"mine({r},{c})"

    return pat.sub(repl, msg)

def parse_formula_for_display(msg: str, grid: Grid) -> str:
    """
    Converts:
    - mine(cK) -> mine(r,c)
    - all x (...) -> ∀x.(...)
    - exists x (...) -> ∃x.(...)
    - & -> ∧
    - | -> ∨
    - -> -> ⇒
    - <-> -> ⇔
    """
    # First convert constants to coordinates
    display = consts_to_coords(msg, grid)

    display = re.sub(r'\ball\s+(\w+)\s+', r'∀\1.', display)
    display = re.sub(r'\bexists\s+(\w+)\s+', r'∃\1.', display)

    display = display.replace('<->', '⇔')
    display = display.replace('->', '⇒')
    display = display.replace(' & ', ' ∧ ')
    display = display.replace(' | ', ' ∨ ')

    display = re.sub(r'-mine', '¬mine', display)

    return display
