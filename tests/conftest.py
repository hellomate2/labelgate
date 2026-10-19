import csv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

from labelgate.adapters import medcalc


@pytest.fixture(scope="session")
def tasks():
    return medcalc.load_splits(ROOT / "data")


@pytest.fixture(scope="session")
def flags():
    with open(ROOT / "results/flags.csv", newline="", encoding="utf-8") as f:
        return {(r["dataset"], r["row"]): r for r in csv.DictReader(f)}
