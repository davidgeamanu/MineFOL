from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Set, Tuple, List

Coord = Tuple[int, int]

@dataclass
class GameState:
    n: int
    mines: int
    start: Coord = (1, 1)
    pos: Coord = (1, 1)

    # Hidden truth for evaluation
    mine_cells: Set[Coord] = field(default_factory=set)

    # Messages stored in cells
    messages_by_cell: Dict[Coord, str] = field(default_factory=dict)

    # Knowledge base for Prover9 / Mace4
    collected_messages: List[str] = field(default_factory=list)

    # Messages visible to the player
    player_messages: List[str] = field(default_factory=list)

    # Last message at current cell
    last_cell_message: str | None = None

    visited: Set[Coord] = field(default_factory=set)
    flagged: Set[Coord] = field(default_factory=set)

    dead: bool = False

    def _observe_safe(self, cell: Coord) -> None:
        #Internal KB fact: if alive here, cell is safe.
        r, c = cell
        obs = f"-mine({r},{c})"
        if obs not in self.collected_messages:
            self.collected_messages.append(obs)

    def add_message_if_present(self) -> None:
        #Reveal message if current cell is a message cell.
        self.last_cell_message = None
        if self.pos in self.messages_by_cell:
            msg = self.messages_by_cell[self.pos].strip()

            # Add to KB
            if msg not in self.collected_messages:
                self.collected_messages.append(msg)

            # Add to player-visible messages
            if msg not in self.player_messages:
                self.player_messages.append(msg)

            self.last_cell_message = msg

    def step_into(self, cell: Coord) -> None:
        self.pos = cell
        self.visited.add(cell)

        if cell in self.mine_cells:
            self.dead = True
            return

        # KB observation
        self._observe_safe(cell)

        # Player message (if any)
        self.add_message_if_present()
