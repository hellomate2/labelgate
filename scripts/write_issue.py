"""Write upstream/ISSUE.md, a draft issue for the MedCalc-Bench Verified maintainers, from handcheck.csv."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Unclear rows a second check read as the same patterns as the rows below. Named only while all are still unclear.
SECOND_CHECK_UNCLEAR = ["6414", "6639", "6653", "6769"]

from labelgate import handcheck

INTRO = """# Training rows whose label follows a misread or mistyped input (train_data.csv, v1.0.8)

Draft, not filed.

The recompute audit in PR #7 re-runs each row's calculator on its Relevant Entities and finds 0 mismatches
in train_data.csv. The rows below also pass that check, because the label follows from its Relevant Entities and
the entity is what is wrong: it does not match what the Patient Note says, or the note itself prints an impossible
unit and the entity copies it.

Each row lists the exact note text, the stored entity and the stored answer. Every quote is a literal substring
of that row's Patient Note at commit 58fc3de. {review} Please treat the list as a set of rows to look at,
not as final.{second_check}

{relabeled}
"""


def table(rows):
    lines = ["| Row | Calculator | Note text | Stored entity | Stored answer | Why |", "|---|---|---|---|---|---|"]
    for e in rows:
        quote = " / ".join(f"`{q}`" for q in handcheck.quotes(e))
        why = e["reason"].replace("|", "/")
        lines.append(f"| {e['row']} | {e['calculator']} | {quote} | {e['input_value']} | {e['stored_label']} | {why} |")
    return lines


def main():
    all_entries = handcheck.load(ROOT / "results/handcheck.csv")
    entries = [e for e in all_entries if e["decision"] == "defect"]
    unclear = {e["row"] for e in all_entries if e["dataset"] == "ver_train" and e["decision"] == "unclear"}
    unconfirmed = not all(handcheck.confirmed_by_dev(e) for e in entries)
    review = ("Each row has a first-pass call and reason, which I have not yet confirmed row by row, and no "
              "clinician has read them." if unconfirmed else
              "I read each row against its note and agree with each call. No clinician has read them.")
    second_check = (f" Four more rows ({', '.join(SECOND_CHECK_UNCLEAR)}) look like the same patterns on a second "
                    "check. They are marked unclear and left out of the tables."
                    if set(SECOND_CHECK_UNCLEAR) <= unclear else "")
    with open(ROOT / "results/verified_relabeled.csv", newline="", encoding="utf-8") as f:
        changed = [r for r in csv.DictReader(f) if r["label_changed"] == "1"]
    rerounded = [r for r in changed if r["rerounded_only"] == "1"]
    recomputed = [f'{r["row"]} moved from {r["v12_label"]} to {r["verified_label"]} because the v1.2 explanation rounded an '
                  f'intermediate value: v1.2 used {r["precision_change"].split(": ", 1)[1].replace(" to ", " where Verified kept ")}'
                  if r["precision_change"].startswith("intermediate") else
                  f'{r["row"]} changed from {r["v12_label"]} to {r["verified_label"]}'
                  for r in changed if r["rerounded_only"] != "1"]
    relabeled = (f'{len(changed)} of these rows have a different stored answer in Verified than in v1.2 '
                 f'({", ".join(r["row"] for r in changed)}). {len(rerounded)} were re-rounded'
                 + (f'; {"; ".join(recomputed)}' if recomputed else "")
                 + ". In each case the new answer still follows from the impossible entity.") if changed else ""
    lines = [INTRO.format(review=review, second_check=second_check, relabeled=relabeled)]
    for dataset, name in (("ver_train", "train_data.csv"), ("ver_test", "test_data.csv")):
        mine = [e for e in entries if e["dataset"] == dataset]
        if not mine:
            continue
        for kind, heading in (("extraction", "The entity does not match the note"),
                              ("copied typo", "The note prints an impossible unit and the entity copies it")):
            rows = sorted((e for e in mine if e["defect_kind"] == kind), key=lambda e: int(e["row"]))
            if rows:
                lines += [f"## {name}: {heading} ({len(rows)} rows)", ""] + table(rows) + [""]
    with open(ROOT / "results/homa_ir.csv", newline="", encoding="utf-8") as f:
        homa = [r for r in csv.DictReader(f) if r["dataset"] == "ver_train"]
    with open(ROOT / "results/results_table.csv", newline="", encoding="utf-8") as f:
        homa_n = next(r["n"] for r in csv.DictReader(f) if r["id"] == "homa-ir")
    example = next(r for r in homa if r["in_confirmed_defects"] == "0")
    lines += ["## HOMA-IR: pmol/L insulin is multiplied by 6 instead of divided", "",
              "arXiv 2603.02222 lists this bug, and PR #5 (artuskg) proposed the one-line fix in February 2026. It was "
              f"closed without merging, so {len(homa)} of {homa_n} training labels in v1.0.8 still carry it.", "",
              f"{len(homa)} of the {homa_n} HOMA-IR rows in train_data.csv give insulin in pmol/L. The explanation "
              "converts it with \"* 6 µIU/mL/pmol/L\" (calculator_implementations/homa_ir.py). About 6 pmol/L make "
              "1 µIU/mL, so the conversion should divide, and each of these labels is 36 times too large. For example, "
              f"row {example['row']} has insulin {example['insulin_pmol_l']} pmol/L and a stored answer of "
              f"{example['stored_label']}; dividing gives about {float(example['corrected_label']):.2f}. Only row "
              "5880 is also in the tables above. Rows: " + ", ".join(r["row"] for r in homa) + ".", ""]
    out = ROOT / "upstream"
    out.mkdir(exist_ok=True)
    (out / "ISSUE.md").write_text("\n".join(lines))
    print("wrote upstream/ISSUE.md with", len(entries), "rows")


if __name__ == "__main__":
    main()
