"""Run the four checks on every row of Verified and v1.2, train and test.

Writes results/flags.csv (one line per flagged row) and results/gate_summary.json.
"""
import collections
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from labelgate.adapters import medcalc
from labelgate.checks import consistency, grounding, outliers, recompute

DATASETS = {
    "ver_train": "data/ver_train.csv",
    "ver_test": "data/ver_test.csv",
    "v12_train": "data/v12_train.csv",
    "v12_test": "data/v12_test.csv",
}


def run_dataset(name, path):
    tasks = medcalc.load(ROOT / path, name)
    outlier_flags = outliers.check(tasks)
    rows, summary = [], collections.Counter()
    by_formula = collections.defaultdict(collections.Counter)
    for t in tasks:
        g1 = recompute.check(t)
        g2 = grounding.check(t)
        g3 = consistency.check(t)
        g4 = outlier_flags.get(t.id, [])
        if g1["status"] != "no_formula":
            summary[f"g1_{g1['status']}"] += 1
            by_formula[t.formula][g1["status"]] += 1
        fired = []
        if g1["status"] == "mismatch":
            fired.append("G1:mismatch")
        fired += [f"G2:{f['kind']}:{f['field']}" for f in g2]
        fired += [f"G3:{rule}" for rule in g3]
        fired += [f"G4:{f['kind']}:{f['field']}" for f in g4]
        for check, hit in (("G1", g1["status"] == "mismatch"), ("G2", g2), ("G3", g3), ("G4", g4)):
            if hit:
                summary[f"rows_{check}"] += 1
        if not fired:
            continue
        summary["rows_flagged"] += 1
        rows.append({
            "dataset": name,
            "row": t.id,
            "calculator_id": t.meta["calculator_id"],
            "calculator": t.meta["calculator"],
            "checks": ";".join(fired),
            "g1_status": g1["status"],
            "recomputed": "" if g1["recomputed"] is None else round(g1["recomputed"], 6),
            "label": t.meta["label_text"],
            "details": json.dumps({"G2": g2, "G3": g3, "G4": g4}, ensure_ascii=False),
        })
    summary["rows"] = len(tasks)
    return rows, dict(summary), {k: dict(v) for k, v in by_formula.items()}


def label_changes(old_path, new_path):
    """Count rows whose Ground Truth Answer differs, joined on Calculator ID plus Note ID.

    label_changed uses an absolute difference above 1e-6, so it includes pure re-rounding. The
    changed_rel_* counts use the relative difference, so they show how many changes are large.
    """
    def read(path):
        with open(ROOT / path, newline="", encoding="utf-8") as f:
            return {(r["Calculator ID"], r["Note ID"]): r["Ground Truth Answer"] for r in csv.DictReader(f)}

    old, new = read(old_path), read(new_path)
    shared = old.keys() & new.keys()
    counts = collections.Counter()
    for key in shared:
        a, b = old[key], new[key]
        try:
            fa, fb = float(a), float(b)
        except ValueError:
            counts["label_changed"] += a.strip() != b.strip()
            counts["non_numeric_changed"] += a.strip() != b.strip()
            continue
        if abs(fa - fb) <= 1e-6:
            continue
        rel = abs(fa - fb) / max(abs(fa), 1e-12)
        counts["label_changed"] += 1
        counts["changed_rel_1e-4"] += rel > 1e-4
        counts["changed_rel_0.1pct"] += rel > 1e-3
        counts["changed_rel_5pct"] += rel > 0.05
    return {"join": "Calculator ID + Note ID", "old_rows": len(old), "new_rows": len(new),
            "matched": len(shared), **{k: counts[k] for k in ("label_changed", "changed_rel_1e-4",
                                                             "changed_rel_0.1pct", "changed_rel_5pct",
                                                             "non_numeric_changed")}}


def main():
    all_rows, summary = [], {}
    for name, path in DATASETS.items():
        rows, counts, by_formula = run_dataset(name, path)
        all_rows += rows
        summary[name] = {"counts": counts, "g1_by_formula": by_formula}
        print(name, counts)
    summary["label_changes"] = {
        "train": label_changes(DATASETS["v12_train"], DATASETS["ver_train"]),
        "test": label_changes(DATASETS["v12_test"], DATASETS["ver_test"]),
    }
    print(summary["label_changes"])
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    with open(out / "flags.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_rows[0]))
        writer.writeheader()
        writer.writerows(all_rows)
    (out / "gate_summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
