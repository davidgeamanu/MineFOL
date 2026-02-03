from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List
import re

_MINE_TERM = re.compile(r"\bmine\s*\(\s*([^,]+?)\s*,\s*([^)]+?)\s*\)")

@dataclass(frozen=True)
class GameParams:
    n: int
    mines: int

def _row_consts(n: int) -> list[str]:
    return [f"r{i}" for i in range(1, n + 1)]

def _mine_pair_consts(m: int) -> tuple[list[str], list[str]]:
    mrs = [f"mr{i}" for i in range(1, m + 1)]
    mcs = [f"mc{i}" for i in range(1, m + 1)]
    return mrs, mcs

def _distinct_constants_axioms(consts: list[str]) -> list[str]:
    ax = ["% --- Distinct row/col constants ---"]
    for i in range(len(consts)):
        for j in range(i + 1, len(consts)):
            ax.append(f"{consts[i]} != {consts[j]}.")
    return ax

def _domain_closure_axiom(consts: list[str]) -> str:
    # all x (x=r1 | x=r2 | ... | x=rN)
    disj = " | ".join([f"x = {c}" for c in consts])
    return f"all x ({disj})."

def _one_of_axiom(var: str, consts: list[str]) -> str:
    # (var=r1 | ... | var=rN)
    disj = " | ".join([f"{var} = {c}" for c in consts])
    return f"({disj})."

def _to_rconst(term: str) -> str:
    t = term.strip()
    if t.isdigit():
        return f"r{t}"
    return t

def rewrite_mine_terms_to_rconsts(formula: str) -> str:
    def repl(m: re.Match) -> str:
        a = _to_rconst(m.group(1))
        b = _to_rconst(m.group(2))
        return f"mine({a},{b})"
    return _MINE_TERM.sub(repl, formula)


def exactly_m_mines_axioms(n: int, m: int) -> list[str]:

    #Encode exactly m mines using mine-pair constants:
    #  mine(x,y) <-> OR_k (x=mrk & y=mck)
    #plus distinctness of pairs and range restriction to r1..rN.

    rows = _row_consts(n)
    mrs, mcs = _mine_pair_consts(m)

    ax: list[str] = ["% --- Exactly M mines (mine/2) ---"]

    # Range restriction: each mrk, mck is one of r1..rN
    for i in range(m):
        ax.append(_one_of_axiom(mrs[i], rows))
        ax.append(_one_of_axiom(mcs[i], rows))

    # Distinct mine positions: for i<j, (mr_i != mr_j) | (mc_i != mc_j)
    for i in range(m):
        for j in range(i + 1, m):
            ax.append(f"({mrs[i]} != {mrs[j]} | {mcs[i]} != {mcs[j]}).")

    # Define mine(x,y) iff it equals one of the mine pairs
    # all x all y (mine(x,y) <-> ((x=mr1 & y=mc1) | ...))
    pairs = " | ".join([f"(x = {mrs[i]} & y = {mcs[i]})" for i in range(m)])
    ax.append(f"all x all y (mine(x,y) <-> ({pairs})).")

    return ax

def write_mace_instance(project_root: Path, params: GameParams, messages: List[str], out_path_rel: str) -> Path:

    #Mace4 instance:
    #  domain_size = N  (rows/cols are elements r1..rN)
    #  closure axiom so quantifiers range over exactly those N elements
    #  exactly M mines via pair constants
    #  messages added verbatim

    out_path = (project_root / out_path_rel).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = _row_consts(params.n)
    mrs, mcs = _mine_pair_consts(params.mines)

    lines: list[str] = []
    lines.append(f"assign(domain_size,{params.n}).")
    lines.append("")
    lines.append("formulas(assumptions).")
    lines.append("")

    # Name row/col elements + make them distinct + close the domain
    for r in rows:
        lines.append(f"Row({r}).")
        lines.append(f"Col({r}).")
    lines.append("")
    lines.extend(_distinct_constants_axioms(rows))
    lines.append("")
    lines.append("% --- Domain closure for quantifiers ---")
    lines.append(_domain_closure_axiom(rows))
    lines.append("")

    lines.extend(exactly_m_mines_axioms(params.n, params.mines))
    lines.append("")

    lines.append("% --- Messages ---")
    for m in messages:
        m2 = rewrite_mine_terms_to_rconsts(m.strip())
        lines.append(m2 if m2.endswith(".") else (m2 + "."))
    lines.append("")
    lines.append("end_of_list.")
    lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path

def write_prover_query(project_root: Path, params: GameParams, messages_so_far: List[str],
                       target_r: int, target_c: int, out_path_rel: str) -> Path:
    #Prover9 query to prove -mine(rX,rY) (note: rows/cols are r1..rN constants).
    #We represent coordinate (i,j) as mine(ri,rj).
    out_path = (project_root / out_path_rel).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = _row_consts(params.n)
    tr = f"r{target_r}"
    tc = f"r{target_c}"

    lines: list[str] = []
    lines.append("set(auto).")
    lines.append("")
    lines.append("formulas(assumptions).")
    lines.append("")

    for r in rows:
        lines.append(f"Row({r}).")
        lines.append(f"Col({r}).")
    lines.append("")
    lines.extend(_distinct_constants_axioms(rows))
    lines.append("")
    lines.append(_domain_closure_axiom(rows))
    lines.append("")
    lines.extend(exactly_m_mines_axioms(params.n, params.mines))
    lines.append("")
    lines.append("% --- Messages collected so far ---")
    for m in messages_so_far:
        m2 = rewrite_mine_terms_to_rconsts(m.strip())
        lines.append(m2 if m2.endswith(".") else (m2 + "."))
    lines.append("")
    lines.append("end_of_list.")
    lines.append("")
    lines.append("formulas(goals).")
    lines.append(f"-mine({tr},{tc}).")
    lines.append("end_of_list.")
    lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
