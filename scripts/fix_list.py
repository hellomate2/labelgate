"""Write results/fix_list.csv: every row to relabel, drop, or fix through the calculator.

One rule, applied to rows already decided in results/handcheck.csv and results/homa_ir.csv:
  relabel                       a defect whose note gives the inputs (note_inputs is filled)
  drop                          a defect with no note-supported answer
  fix calculator and regenerate a HOMA-IR row with pmol/L insulin (PR #5's patch), including 5880
This adds no new judgment. It is a filtered view of those two files.
"""
import csv
from pathlib import Path

from labelgate import handcheck
from labelgate.adapters import medcalc

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
PATCH = "PR #5 on nikhilk7153/MedCalc-Bench-Verified changes `* 6` to `/ 6` in calculator_implementations/homa_ir.py"
COLUMNS = ["dataset", "row", "calculator", "note_quote", "stored_label", "action", "note_supported", "reason"]
ORDER = {"relabel": 0, "drop": 1, "fix calculator and regenerate": 2}
# Rows where only one criterion is settled by the note. The full score is left to whoever relabels.
CRITERION_ONLY = {("ver_train", "2807"): "heart-rate criterion 0, not 1.5"}


def fmt(x):
    return f"{x:,.6g}" if abs(x) >= 1e-3 or x == 0 else f"{x:.6g}"


def supported(task, entry):
    values = handcheck.note_values(task, entry["note_inputs"])
    low, high = min(values), max(values)
    text = fmt(low) if low == high else f"{fmt(low)} to {fmt(high)}"
    bounds = handcheck.interval(task, entry["note_inputs"])
    if bounds != (low, high):
        text += f" ({fmt(bounds[0])} to {fmt(bounds[1])} with the 5% tolerance)"
    if entry["interval_assumes"]:
        text += f", if {entry['interval_assumes']}"
    return text


def main():
    entries = [e for e in handcheck.load(RESULTS / "handcheck.csv") if e["decision"] == "defect"]
    with open(RESULTS / "homa_ir.csv", newline="", encoding="utf-8") as f:
        homa = list(csv.DictReader(f))
    homa_keys = {(r["dataset"], r["row"]) for r in homa}
    tasks = medcalc.load_splits(ROOT / "data")

    out = []
    for e in entries:
        key = (e["dataset"], e["row"])
        if key in homa_keys:
            continue
        task = tasks[key]
        action = "relabel" if e["note_inputs"] else "drop"
        out.append({"dataset": e["dataset"], "row": e["row"], "calculator": e["calculator"],
                    "note_quote": e["quote"], "stored_label": task.meta["label_text"], "action": action,
                    "note_supported": CRITERION_ONLY.get(key) or (supported(task, e) if e["note_inputs"] else "none"),
                    "reason": e["reason"]})
    by_key = {(e["dataset"], e["row"]): e for e in entries}
    for r in homa:
        task = tasks[(r["dataset"], r["row"])]
        entry = by_key.get((r["dataset"], r["row"]))
        reason = f"insulin {r['insulin_pmol_l']} pmol/L is multiplied by 6 where it should be divided, so the label is {r['ratio']}x too large; {PATCH}"
        if entry:
            reason = f"{entry['reason']}; after the calculator fix, the input also needs the note's value"
        out.append({"dataset": r["dataset"], "row": r["row"], "calculator": task.meta["calculator"],
                    "note_quote": entry["quote"] if entry else "", "stored_label": task.meta["label_text"],
                    "action": "fix calculator and regenerate",
                    "note_supported": "regenerate from the note's insulin" if entry else f"{float(r['corrected_label']):.4g} after the patch",
                    "reason": reason})

    out.sort(key=lambda r: (r["dataset"] != "ver_train", ORDER[r["action"]], int(r["row"])))
    with open(RESULTS / "fix_list.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(out)
    counts = {a: sum(r["action"] == a for r in out) for a in ORDER}
    print(f"wrote results/fix_list.csv with {len(out)} rows:", ", ".join(f"{a} {n}" for a, n in counts.items()))


if __name__ == "__main__":
    main()
