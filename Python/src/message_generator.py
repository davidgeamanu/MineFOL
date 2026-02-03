"""
Rich message generator for MineFOL with complex formulas.

Message categories:
1. Direct facts: mine(r,c) or -mine(r,c)
2. Conjunctions: mine(r1,c1) & mine(r2,c2)
3. Disjunctions: mine(r1,c1) | mine(r2,c2)
4. Implications: mine(r1,c1) -> mine(r2,c2)
5. Biconditionals: mine(r1,c1) <-> mine(r2,c2)
6. Universal quantifiers: all x.(mine(x,c) -> ...) or all x.(mine(r,x) -> ...)
7. Existential quantifiers: exists x.mine(x,c) or -exists x.mine(x,c)
8. Mixed: exists x.mine(x,3) -> exists x.mine(x,8)
"""
from __future__ import annotations
import random
from typing import Set, List, Tuple, Dict

Coord = Tuple[int, int]


class MessageGenerator:

    def __init__(self, n: int, mines: Set[Coord], safe: Set[Coord]):
        self.n = n
        self.mines = mines
        self.safe = safe
        self.all_coords = [(r, c) for r in range(1, n+1) for c in range(1, n+1)]

    def random_mine(self) -> Coord:
        #Get a random mine coordinate.
        return random.choice(list(self.mines))

    def random_safe(self) -> Coord:
        #Get a random safe coordinate.
        return random.choice(list(self.safe))

    def random_coord(self) -> Coord:
        #Get any random coordinate.
        return random.choice(self.all_coords)

    # CATEGORY 1: Direct Facts

    def msg_direct_mine(self) -> str:
        #mine(r,c) - directly states a mine location.
        r, c = self.random_mine()
        return f"mine({r},{c})"

    def msg_direct_safe(self) -> str:
        #-mine(r,c) - directly states a safe cell.
        r, c = self.random_safe()
        return f"-mine({r},{c})"

    # CATEGORY 2: Conjunctions

    def msg_conjunction_mines(self) -> str:
        #mine(r1,c1) & mine(r2,c2) - two mines.
        if len(self.mines) < 2:
            return self.msg_direct_mine()
        m1, m2 = random.sample(list(self.mines), 2)
        return f"(mine({m1[0]},{m1[1]}) & mine({m2[0]},{m2[1]}))"

    def msg_conjunction_safe(self) -> str:
        #-mine(r1,c1) & -mine(r2,c2) - two safe cells.
        if len(self.safe) < 2:
            return self.msg_direct_safe()
        s1, s2 = random.sample(list(self.safe), 2)
        return f"(-mine({s1[0]},{s1[1]}) & -mine({s2[0]},{s2[1]}))"

    #CATEGORY 3: Disjunctions

    def msg_disjunction_mines(self) -> str:
        #mine(r1,c1) | mine(r2,c2) - at least one is a mine.
        if len(self.mines) < 1:
            return self.msg_direct_safe()

        # Pick one mine and one random cell
        m = self.random_mine()
        other = self.random_coord()

        # Ensure they're different
        while other == m:
            other = self.random_coord()

        return f"(mine({m[0]},{m[1]}) | mine({other[0]},{other[1]}))"

    def msg_disjunction_safe(self) -> str:
        #-mine(r1,c1) | -mine(r2,c2) - at least one is safe.
        if len(self.safe) < 1:
            return self.msg_direct_safe()

        s = self.random_safe()
        other = self.random_coord()

        while other == s:
            other = self.random_coord()

        return f"(-mine({s[0]},{s[1]}) | -mine({other[0]},{other[1]}))"

    # CATEGORY 4: Implications

    def msg_implication_mine_to_mine(self) -> str:
        #mine(r1,c1) -> mine(r2,c2) - if first is mine, second is too.
        if len(self.mines) < 2:
            return self.msg_direct_mine()
        m1, m2 = random.sample(list(self.mines), 2)
        return f"(mine({m1[0]},{m1[1]}) -> mine({m2[0]},{m2[1]}))"

    def msg_implication_safe_to_safe(self) -> str:
        #-mine(r1,c1) -> -mine(r2,c2) - if first is safe, second is too.
        if len(self.safe) < 2:
            return self.msg_direct_safe()
        s1, s2 = random.sample(list(self.safe), 2)
        return f"(-mine({s1[0]},{s1[1]}) -> -mine({s2[0]},{s2[1]}))"

    def msg_implication_mine_to_safe(self) -> str:
        #mine(r1,c1) -> -mine(r2,c2) - if first is mine, second is safe.
        if not self.mines or not self.safe:
            return self.msg_direct_safe()
        m = self.random_mine()
        s = self.random_safe()
        return f"(mine({m[0]},{m[1]}) -> -mine({s[0]},{s[1]}))"

    # CATEGORY 5: Biconditionals

    def msg_biconditional_symmetric(self) -> str:
        #mine(r,c) <-> mine(c,r) - symmetric mines.
        r, c = self.random_mine()
        # Check if (c,r) is also a mine
        if (c, r) in self.mines:
            return f"(mine({r},{c}) <-> mine({c},{r}))"
        else:
            # Fall back to different message
            return self.msg_implication_mine_to_mine()

    def msg_biconditional_row_col(self) -> str:
        #all x.(mine(x,c1) <-> mine(x,c2)) - two columns have identical mine patterns.
        c1 = random.randint(1, self.n)
        c2 = random.randint(1, self.n)
        while c2 == c1:
            c2 = random.randint(1, self.n)

        col1_mines = {r for r in range(1, self.n+1) if (r, c1) in self.mines}
        col2_mines = {r for r in range(1, self.n+1) if (r, c2) in self.mines}

        if col1_mines == col2_mines:
            return f"(all x (mine(x,{c1}) <-> mine(x,{c2})))"
        else:
            return self.msg_direct_mine()

    # CATEGORY 6: Universal Quantifiers

    def msg_universal_row_implies(self) -> str:
        #all x.(mine(r,x) -> P) - if any cell in row r is mine, then P.
        r = random.randint(1, self.n)

        # Find if row has any mines
        row_has_mines = any((r, c) in self.mines for c in range(1, self.n+1))

        if row_has_mines:
            # Pick a true consequence (another mine)
            m = self.random_mine()
            return f"(all x (mine({r},x) -> mine({m[0]},{m[1]})))"
        else:
            # Row is all safe - any implication from False is true
            other = self.random_coord()
            return f"(all x (mine({r},x) -> mine({other[0]},{other[1]})))"

    def msg_universal_col_implies(self) -> str:
        #all x.(mine(x,c) -> P) - if any cell in column c is mine, then P.
        c = random.randint(1, self.n)

        col_has_mines = any((r, c) in self.mines for r in range(1, self.n+1))

        if col_has_mines:
            m = self.random_mine()
            return f"(all x (mine(x,{c}) -> mine({m[0]},{m[1]})))"
        else:
            other = self.random_coord()
            return f"(all x (mine(x,{c}) -> mine({other[0]},{other[1]})))"

    def msg_universal_no_mines_on_diagonal(self) -> str:
        #all x.(-mine(x,x)) - no mines on main diagonal.
        diagonal_clear = all((i, i) not in self.mines for i in range(1, self.n+1))

        if diagonal_clear:
            return "(all x (-mine(x,x)))"
        else:
            return self.msg_direct_safe()

    def msg_universal_row_all_safe(self) -> str:
        #all x.(-mine(r,x)) - entire row r is safe.
        # Find a row with no mines
        safe_rows = [r for r in range(1, self.n+1)
                     if all((r, c) not in self.mines for c in range(1, self.n+1))]

        if safe_rows:
            r = random.choice(safe_rows)
            return f"(all x (-mine({r},x)))"
        else:
            return self.msg_direct_safe()

    # CATEGORY 7: Existential Quantifiers

    def msg_existential_mine_in_row(self) -> str:
        #exists x.mine(r,x) - there is a mine in row r.
        # Pick a row that has at least one mine
        rows_with_mines = [r for r in range(1, self.n+1)
                          if any((r, c) in self.mines for c in range(1, self.n+1))]

        if rows_with_mines:
            r = random.choice(rows_with_mines)
            return f"(exists x mine({r},x))"
        else:
            return self.msg_direct_mine()

    def msg_existential_mine_in_col(self) -> str:
        #exists x.mine(x,c) - there is a mine in column c.
        cols_with_mines = [c for c in range(1, self.n+1)
                          if any((r, c) in self.mines for r in range(1, self.n+1))]

        if cols_with_mines:
            c = random.choice(cols_with_mines)
            return f"(exists x mine(x,{c}))"
        else:
            return self.msg_direct_mine()

    def msg_no_mines_in_row(self) -> str:
        #-(exists x.mine(r,x)) - no mines in row r.
        safe_rows = [r for r in range(1, self.n+1)
                    if all((r, c) not in self.mines for c in range(1, self.n+1))]

        if safe_rows:
            r = random.choice(safe_rows)
            return f"(-(exists x mine({r},x)))"
        else:
            return self.msg_direct_safe()

    def msg_no_mines_in_col(self) -> str:
        #-(exists x.mine(x,c)) - no mines in column c.
        safe_cols = [c for c in range(1, self.n+1)
                    if all((r, c) not in self.mines for r in range(1, self.n+1))]

        if safe_cols:
            c = random.choice(safe_cols)
            return f"(-(exists x mine(x,{c})))"
        else:
            return self.msg_direct_safe()

    # CATEGORY 8: Mixed Complex

    def msg_existential_implication(self) -> str:
        #exists x.mine(x,c1) -> exists x.mine(x,c2) - if col1 has mine, col2 has mine.
        cols_with_mines = [c for c in range(1, self.n+1)
                          if any((r, c) in self.mines for r in range(1, self.n+1))]

        if len(cols_with_mines) >= 2:
            c1, c2 = random.sample(cols_with_mines, 2)
            return f"((exists x mine(x,{c1})) -> (exists x mine(x,{c2})))"
        else:
            return self.msg_direct_mine()

    def msg_universal_all_or_none(self) -> str:
        #(all x.mine(r,x)) | (all x.-mine(r,x)) - row is all mines or all safe.
        r = random.randint(1, self.n)

        # Check if row is all mines or all safe
        row_cells = [(r, c) for c in range(1, self.n+1)]
        all_mines = all(cell in self.mines for cell in row_cells)
        all_safe = all(cell in self.safe for cell in row_cells)

        if all_mines or all_safe:
            return f"((all x mine({r},x)) | (all x (-mine({r},x))))"
        else:
            return self.msg_direct_safe()

    # Message Selection

    def generate_message(self, difficulty: str = "Medium") -> str:
        """
        Generate a random message appropriate for the difficulty level.
        Args: difficulty: "Easy", "Medium", or "Hard"
        Returns: a logical formula as a string
        """
        if difficulty == "Easy":
            options = [
                (self.msg_direct_safe, 40),
                (self.msg_direct_mine, 20),
                (self.msg_conjunction_safe, 20),
                (self.msg_implication_safe_to_safe, 10),
                (self.msg_disjunction_safe, 10),
            ]

        elif difficulty == "Medium":
            options = [
                (self.msg_direct_safe, 10),
                (self.msg_direct_mine, 5),
                (self.msg_conjunction_safe, 10),
                (self.msg_conjunction_mines, 10),
                (self.msg_disjunction_mines, 15),
                (self.msg_implication_mine_to_safe, 10),
                (self.msg_implication_safe_to_safe, 5),
                (self.msg_existential_mine_in_row, 15),
                (self.msg_existential_mine_in_col, 10),
                (self.msg_no_mines_in_row, 10),
                (self.msg_universal_row_all_safe, 10),
            ]

        else:  # Hard
            options = [
                (self.msg_direct_safe, 12),
                (self.msg_direct_mine, 6),
                (self.msg_disjunction_mines, 12),
                (self.msg_implication_mine_to_mine, 10),
                (self.msg_biconditional_symmetric, 8),
                (self.msg_universal_row_implies, 12),
                (self.msg_universal_col_implies, 12),
                (self.msg_universal_no_mines_on_diagonal, 10),
                (self.msg_existential_mine_in_row, 11),
                (self.msg_existential_mine_in_col, 12),
                (self.msg_no_mines_in_row, 10),
                (self.msg_no_mines_in_col, 8),
                (self.msg_existential_implication, 12),
            ]

        functions, weights = zip(*options)
        chosen_func = random.choices(functions, weights=weights)[0]

        try:
            message = chosen_func()
            return message
        except (IndexError, ValueError):
            return self.msg_direct_safe()

    def generate_helpful_start_message(self) -> str:
        #Generate a message for the start cell that helps the player progress.
        # Find safe neighbors of (1,1)
        start = (1, 1)
        neighbors = []
        for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
            nr, nc = start[0] + dr, start[1] + dc
            if 1 <= nr <= self.n and 1 <= nc <= self.n and (nr, nc) in self.safe:
                neighbors.append((nr, nc))

        if neighbors:
            # Reveal one or more safe neighbors
            if len(neighbors) == 1:
                r, c = neighbors[0]
                return f"-mine({r},{c})"
            else:
                # Reveal multiple with conjunction or disjunction
                r1, c1 = neighbors[0]
                r2, c2 = neighbors[1]
                return f"(-mine({r1},{c1}) & -mine({r2},{c2}))"
        else:
            # No safe neighbors? Reveal a safe cell elsewhere
            s = self.random_safe()
            return f"-mine({s[0]},{s[1]})"


def test_message_generator():
    n = 8
    mines = {(2,3), (4,4), (5,1), (7,7)}
    all_coords = {(r,c) for r in range(1, n+1) for c in range(1, n+1)}
    safe = all_coords - mines

    gen = MessageGenerator(n, mines, safe)

    print("=" * 60)
    print("MineFOL Message Generator Test")
    print("=" * 60)
    print(f"Board: {n}x{n}, Mines: {len(mines)}, Safe: {len(safe)}")
    print()

    for difficulty in ["Easy", "Medium", "Hard"]:
        print(f"\n{difficulty} Messages:")
        print("-" * 60)
        for i in range(5):
            msg = gen.generate_message(difficulty)
            print(f"  {i+1}. {msg}")

    print("\n" + "=" * 60)
    print("Start Message:")
    print("-" * 60)
    print(f"  {gen.generate_helpful_start_message()}")


if __name__ == "__main__":
    test_message_generator()