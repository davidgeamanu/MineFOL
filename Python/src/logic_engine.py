from __future__ import annotations
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from runner import run_mace4, run_prover9
from minefol_writer import GameParams, write_mace_instance, write_prover_query
from parse_outputs import read_text, mace_found_model, mace_exhausted, prover9_proved, prover9_proof_labels
from grid import Grid

Coord = Tuple[int, int]

#Each prover call gets its own temp folder, so calls running at the same time can't clash.

def _run_mace4(params: GameParams, messages: List[str], timeout: float) -> str:
    with tempfile.TemporaryDirectory(prefix="minefol_") as tmp:
        write_mace_instance(project_root=Path(tmp), params=params, messages=messages, out_path_rel="instance.in")
        run_mace4(f"{tmp}/instance.in", f"{tmp}/output.txt", timeout=timeout)
        return read_text(Path(tmp) / "output.txt")


def _run_prover9(params: GameParams, messages: List[str], target_r: int, target_c: int, timeout: float,
                 prove_mine: bool = False) -> str:
    with tempfile.TemporaryDirectory(prefix="minefol_") as tmp:
        write_prover_query(project_root=Path(tmp), params=params, messages_so_far=messages,
                           target_r=target_r, target_c=target_c, out_path_rel="query.in", prove_mine=prove_mine)
        run_prover9(f"{tmp}/query.in", f"{tmp}/output.txt", timeout=timeout)
        return read_text(Path(tmp) / "output.txt")


@dataclass
class LogicEngine:
    def is_configuration_consistent(self, n: int, mines: int, messages: List[str]) -> bool:

        #Mace4 consistency check. Messages are passed verbatim.

        out = _run_mace4(GameParams(n=n, mines=mines), messages, timeout=2.0)
        return mace_found_model(out)

    def explain_safe(self, n: int, mines: int, messages_so_far: List[str], target_r: int, target_c: int, timeout: float = 1.0) -> tuple[List[str], bool] | None:

        #Prover9 proof that the cell is safe, used to explain a hint.
        #Returns (facts from messages_so_far the proof used, whether it used the mine count),
        #or None if no proof was found in time. Proofs either come in < 0.1s or not at all
        #(counting steps), so a short timeout is enough.
        return self._explain(n, mines, messages_so_far, target_r, target_c, timeout, prove_mine=False)

    def explain_mine(self, n: int, mines: int, messages_so_far: List[str], target_r: int, target_c: int, timeout: float = 1.0) -> tuple[List[str], bool] | None:

        #Same as explain_safe, for a proof that the cell is a mine.
        return self._explain(n, mines, messages_so_far, target_r, target_c, timeout, prove_mine=True)

    def _explain(self, n: int, mines: int, messages_so_far: List[str], target_r: int, target_c: int,
                 timeout: float, prove_mine: bool) -> tuple[List[str], bool] | None:
        out = _run_prover9(GameParams(n=n, mines=mines), messages_so_far, target_r, target_c,
                           timeout=timeout, prove_mine=prove_mine)
        if not prover9_proved(out):
            return None

        labels = prover9_proof_labels(out)
        used = sorted(int(label[2:]) for label in labels if label.startswith("kb"))
        return [messages_so_far[i] for i in used], "mine_count" in labels

    def is_provably_safe(self, n: int, mines: int, messages_so_far: List[str], target_r: int, target_c: int, timeout: float = 2.0) -> bool:

        #Model-based safety check using Mace4: safe iff KB + mine(rT,cT) has no model.
        #Every model has exactly n elements (distinct r1..rN + domain closure),
        #so an exhausted search of domain size n is a proof. Timeout -> not proved.
        out = _run_mace4(GameParams(n=n, mines=mines), messages_so_far + [f"mine({target_r},{target_c})"], timeout=timeout)

        if not mace_exhausted(out) and not mace_found_model(out):
            print(f"[Mace4] No answer for ({target_r},{target_c}) within {timeout}s, treating as not safe.")
        return mace_exhausted(out)

    def is_forced_mine(self, n: int, mines: int, messages_so_far: List[str], target_r: int, target_c: int) -> bool:

        #Model-based entailment using Mace4.
        params = GameParams(n=n, mines=mines)

        # 1) Check KB satisfiable
        kb_out = _run_mace4(params, messages_so_far, timeout=1.0)
        if not mace_found_model(kb_out):
            return False

        # 2) Check KB + -mine(rT,cT) satisfiable?
        out2 = _run_mace4(params, messages_so_far + [f"-mine({target_r},{target_c})"], timeout=1.0)

        # Forced only if Mace4 exhausted the search (a timeout proves nothing)
        if not mace_exhausted(out2) and not mace_found_model(out2):
            print(f"[Mace4] No answer for ({target_r},{target_c}), treating as not forced.")
        return mace_exhausted(out2)

    def legal_moves(self, grid: Grid, mines: int, messages_so_far: List[str], r: int, c: int) -> list[Coord]:
        moves: list[Coord] = []
        for rr, cc in grid.neighbors4(r, c):
            if self.is_provably_safe(grid.n, mines, messages_so_far, rr, cc):
                moves.append((rr, cc))
        return moves