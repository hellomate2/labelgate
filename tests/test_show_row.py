import importlib.util
from pathlib import Path

from labelgate import handcheck

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("show_row", ROOT / "scripts/show_row.py")
show_row = importlib.util.module_from_spec(spec)
spec.loader.exec_module(show_row)
ENTRIES = {(e["dataset"], e["row"]): e for e in handcheck.load(ROOT / "results/handcheck.csv")}


def printout(tasks, flags, key):
    return show_row.show(tasks[key], flags[key], ENTRIES.get(key))


def test_headline_show_note(tasks, flags):
    for row, text in (("1337", "150-160/80-90"), ("2807", "pulse 40-50 bpm")):
        lines = printout(tasks, flags, ("ver_train", row))
        assert any(line.strip().startswith("...") and text in line for line in lines), row


def test_flagged_show_note(tasks, flags):
    for key in flags:
        if key[0] not in ("ver_train", "ver_test"):
            continue
        lines = printout(tasks, flags, key)
        assert any(line.strip().startswith("...") for line in lines), key
