from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class Grid:
    n: int  # N x N

    def in_bounds(self, r: int, c: int) -> bool:
        return 1 <= r <= self.n and 1 <= c <= self.n

    def rc_to_index(self, r: int, c: int) -> int:
        # 1-based index: (1,1)->1, (1,2)->2, ..., (2,1)->N+1
        return (r - 1) * self.n + c

    def index_to_rc(self, idx: int) -> tuple[int, int]:
        # idx in 1..N^2
        r = (idx - 1) // self.n + 1
        c = (idx - 1) % self.n + 1
        return r, c

    def neighbors4(self, r: int, c: int) -> list[tuple[int, int]]:
        # 4-directional movement
        candidates = [(r-1, c), (r+1, c), (r, c-1), (r, c+1)]
        return [(rr, cc) for rr, cc in candidates if self.in_bounds(rr, cc)]
