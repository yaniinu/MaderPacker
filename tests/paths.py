"""Shared test fixture paths."""
import os
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
IDX = REPO_ROOT / "fixtures" / "shubidx"
BLOB = pathlib.Path(os.environ.get("MADERPACKER_BLOB", REPO_ROOT / "fixtures" / "shubblob"))
GROUND = REPO_ROOT / "fixtures" / "ground_truth.csv"
