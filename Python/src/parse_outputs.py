import re
from pathlib import Path

def mace_found_model(output_text: str) -> bool:
    # Mace4 prints an interpretation(...) block when it finds a model
    return "interpretation(" in output_text

def mace_exhausted(output_text: str) -> bool:
    # Mace4 prints "exit (exhausted)" when it searched everything and found no model
    return "exit (exhausted)" in output_text

def prover9_proved(output_text: str) -> bool:
    # Prover9 prints "THEOREM PROVED" when the goal is proved
    return "THEOREM PROVED" in output_text

def prover9_proof_labels(output_text: str) -> list[str]:
    # Labels of the input formulas the proof used, e.g. ["kb1", "kb3"]
    # (the proof lists them as lines ending in "[assumption].")
    proof = output_text.split("= PROOF =")[-1].split("end of proof")[0]
    labels: list[str] = []
    for line in proof.splitlines():
        if "[assumption]" in line:
            for label in re.findall(r"label\((\w+)\)", line):
                if label != "non_clause" and label not in labels:
                    labels.append(label)
    return labels

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")
