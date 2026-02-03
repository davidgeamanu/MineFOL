from pathlib import Path

def mace_found_model(output_text: str) -> bool:
    # Mace4 prints an interpretation(...) block when it finds a model
    return "interpretation(" in output_text

def prover9_proved(output_text: str) -> bool:
    # Prover9 prints "THEOREM PROVED" when the goal is proved
    return "THEOREM PROVED" in output_text

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")
