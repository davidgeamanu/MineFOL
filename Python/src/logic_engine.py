from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple

from runner import PROJECT_ROOT, run_mace4, run_prover9
from minefol_writer import GameParams, write_mace_instance, write_prover_query
from parse_outputs import read_text, mace_found_model, mace_exhausted, prover9_proved, prover9_proof_labels
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

    def explain_safe(self, n: int, mines: int, messages_so_far: List[str], target_r: int, target_c: int, timeout: float = 1.0) -> tuple[List[str], bool] | None:

        #Prover9 proof that the cell is safe, used to explain a hint.
        #Returns (facts from messages_so_far the proof used, whether it used the mine count),
        #or None if no proof was found in time. Proofs either come in < 0.1s or not at all
        #(counting steps), so a short timeout is enough.
        params = GameParams(n=n, mines=mines)
        write_prover_query(
            project_root=PROJECT_ROOT,
            params=params,
            messages_so_far=messages_so_far,
            target_r=target_r,
            target_c=target_c,
            out_path_rel="Prover/queries/tmp_explain_safe.in"
        )
        run_prover9(
            "Prover/queries/tmp_explain_safe.in",
            "Prover/out/tmp_explain_safe_out.txt",
            timeout=timeout
        )
        out = read_text(PROJECT_ROOT / "Prover/out/tmp_explain_safe_out.txt")
        if not prover9_proved(out):
            return None

        labels = prover9_proof_labels(out)
        used = sorted(int(label[2:]) for label in labels if label.startswith("kb"))
        return [messages_so_far[i] for i in used], "mine_count" in labels

    def is_provably_safe(self, n: int, mines: int, messages_so_far: List[str], target_r: int, target_c: int, timeout: float = 2.0) -> bool:

        #Model-based safety check using Mace4: safe iff KB + mine(rT,cT) has no model.
        #Every model has exactly n elements (distinct r1..rN + domain closure),
        #so an exhausted search of domain size n is a proof. Timeout -> not proved.
        params = GameParams(n=n, mines=mines)
        write_mace_instance(
            project_root=PROJECT_ROOT,
            params=params,
            messages=messages_so_far + [f"mine({target_r},{target_c})"],
            out_path_rel="Prover/instances/tmp_safe_mace.in"
        )
        run_mace4(
            "Prover/instances/tmp_safe_mace.in",
            "Prover/out/tmp_safe_mace_out.txt",
            timeout=timeout
        )
        out = read_text(PROJECT_ROOT / "Prover/out/tmp_safe_mace_out.txt")

        if not mace_exhausted(out) and not mace_found_model(out):
            print(f"[Mace4] No answer for ({target_r},{target_c}) within {timeout}s, treating as not safe.")
        return mace_exhausted(out)

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