"""Repository paths, resolved from this file so scripts work from any working directory."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
EXPERIMENTS = ROOT / "experiments"
RUBRICS = Path(__file__).resolve().parent / "rubric" / "tasks"
