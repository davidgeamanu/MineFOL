import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROVER9 = PROJECT_ROOT / "bin" / "prover9"
MACE4   = PROJECT_ROOT / "bin" / "mace4"

def run_cmd(cmd: list[str], output_path: Path, timeout: float = 5.0) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as out:
        try:
            subprocess.run(
                cmd,
                stdout=out, stderr=subprocess.STDOUT,
                check=False, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            out.write("\n% TIMEOUT\n")

def run_prover9(input_rel_path: str, output_rel_path: str, timeout: float = 5.0) -> None:
    inp = (PROJECT_ROOT / input_rel_path).resolve()
    out = (PROJECT_ROOT / output_rel_path).resolve()
    run_cmd([str(PROVER9), "-f", str(inp)], out, timeout=timeout)

def run_mace4(input_rel_path: str, output_rel_path: str, timeout: float = 5.0) -> None:
    inp = PROJECT_ROOT / input_rel_path
    out = PROJECT_ROOT / output_rel_path
    run_cmd([str(MACE4), "-f", str(inp)], out, timeout=timeout)