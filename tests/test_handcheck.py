from pathlib import Path

from labelgate import handcheck

ROOT = Path(__file__).resolve().parent.parent
ENTRIES = handcheck.load(ROOT / "results/handcheck.csv")
DECISIONS = {"defect", "not a defect", "unclear"}
TYPES = {"range merged", "readings mixed", "unit tag does not match note", "multiplier dropped", "source typo copied", "other"}


def test_quotes_in_note(tasks):
    for e in ENTRIES:
        note = tasks[(e["dataset"], e["row"])].source_text
        for q in handcheck.quotes(e):
            assert q in note, (e["row"], q)


def test_flagged_rows_covered(flags):
    flagged = {k for k in flags if k[0] in ("ver_train", "ver_test")}
    keys = [(e["dataset"], e["row"]) for e in ENTRIES]
    assert len(keys) == len(set(keys))
    assert set(keys) == flagged


def test_vocabulary():
    for e in ENTRIES:
        assert e["decision"] in DECISIONS
        assert handcheck.quotes(e), e["row"]
        if e["decision"] == "defect":
            assert e["defect_type"] in TYPES
            assert e["defect_kind"] in ("extraction", "copied typo")
            assert (e["defect_kind"] == "copied typo") == (e["defect_type"] == "source typo copied")


def test_intervals_exclude_label(tasks):
    for e in ENTRIES:
        if e["note_inputs"]:
            task = tasks[(e["dataset"], e["row"])]
            low, high = handcheck.interval(task, e["note_inputs"])
            assert not low <= task.label <= high, e["row"]
