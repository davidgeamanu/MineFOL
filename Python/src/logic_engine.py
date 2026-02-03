from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple

from runner import PROJECT_ROOT, run_mace4, run_prover9
from minefol_writer import GameParams, write_mace_instance, write_prover_query
from parse_outputs import read_text, mace_found_model, prover9_proved
from grid import Grid

Coord = Tuple[int, int]

@dataclass
class LogicEngine:
    def is_configuration_consistent(self, n: int, mines: int, messages: List[str]) -> bool:

        #Mace4 consistency check. Messages are passed verbatim.

        params = GameParams(n=n, mines=mines)
        write_mace_instance(
            project_root=PROJECT_ROOT,
            params=params,
            messages=messages,
            out_path_rel="Prover/instances/tmp_config_check_mace.in"
        )
        run_mace4(
            "Prover/instances/tmp_config_check_mace.in",
            "Prover/out/tmp_config_check_mace_out.txt",
            timeout=2.0
        )
        out = read_text(PROJECT_ROOT / "Prover/out/tmp_config_check_mace_out.txt")
        return mace_found_model(out)

    def can_prove_safe(self, n: int, mines: int, messages_so_far: List[str], target_r: int, target_c: int, timeout: float = 1.0) -> bool:

        #Prover9 proof attempt.

        params = GameParams(n=n, mines=mines)
        write_prover_query(
            project_root=PROJECT_ROOT,
            params=params,
            messages_so_far=messages_so_far,
            target_r=target_r,
            target_c=target_c,
            out_path_rel="Prover/queries/tmp_prove_safe.in"
        )
        run_prover9(
            "Prover/queries/tmp_prove_safe.in",
            "Prover/out/tmp_prove_safe_out.txt",
            timeout=timeout
        )
        out = read_text(PROJECT_ROOT / "Prover/out/tmp_prove_safe_out.txt")
        return prover9_proved(out)

    def is_forced_mine(self, n: int, mines: int, messages_so_far: List[str], target_r: int, target_c: int) -> bool:

        #Model-based entailment using Mace4.
        params = GameParams(n=n, mines=mines)

        # 1) Check KB satisfiable
        write_mace_instance(
            project_root=PROJECT_ROOT,
            params=params,
            messages=messages_so_far,
            out_path_rel="Prover/instances/tmp_kb_sat.in"
        )
        run_mace4("Prover/instances/tmp_kb_sat.in", "Prover/out/tmp_kb_sat_out.txt", timeout=1.0)
        kb_out = read_text(PROJECT_ROOT / "Prover/out/tmp_kb_sat_out.txt")
        if not mace_found_model(kb_out):
            return False

        # 2) Check KB + -mine(rT,cT) satisfiable?
        msg2 = messages_so_far + [f"-mine({target_r},{target_c})"]
        write_mace_instance(
            project_root=PROJECT_ROOT,
            params=params,
            messages=msg2,
            out_path_rel="Prover/instances/tmp_kb_plus_not_target.in"
        )
        run_mace4(
            "Prover/instances/tmp_kb_plus_not_target.in",
            "Prover/out/tmp_kb_plus_not_target_out.txt",
            timeout=1.0
        )
        out2 = read_text(PROJECT_ROOT / "Prover/out/tmp_kb_plus_not_target_out.txt")

        if not out2.strip():
            return False

        return not mace_found_model(out2)

    def legal_moves(self, grid: Grid, mines: int, messages_so_far: List[str], r: int, c: int) -> list[Coord]:
        moves: list[Coord] = []
        for rr, cc in grid.neighbors4(r, c):
            if self.can_prove_safe(grid.n, mines, messages_so_far, rr, cc, timeout=1.0):
                moves.append((rr, cc))
        return moves