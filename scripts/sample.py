"""Seeded draws for the model phases. Writes results/samples.json.

phase1: 100 unflagged Verified train rows that have at least one numeric input.
defects: every confirmed defect row in results/handcheck.csv, capped at 60.
control: 40 unflagged rows matched to the defect rows' calculator mix.
"""
import collections
import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from labelgate import handcheck
from labelgate.adapters import medcalc
from labelgate.checks import grounding

SEED = 20261017
DEFECT_CAP = 60
CONTROL_SIZE = 40
PHASE1_SIZE = 100


def allocate(counts, total):
    """Split total across keys in proportion to counts, largest remainder first."""
    whole = sum(counts.values())
    shares = {k: total * c / whole for k, c in counts.items()}
    out = {k: int(s) for k, s in shares.items()}
    for k in sorted(shares, key=lambda k: (out[k] - shares[k], k))[: total - sum(out.values())]:
        out[k] += 1
    return out


def main():
    tasks = medcalc.load(ROOT / "data/ver_train.csv", "ver_train")
    with open(ROOT / "results/flags.csv", newline="", encoding="utf-8") as f:
        flagged = {(r["dataset"], r["row"]) for r in csv.DictReader(f)}
    clean = [t for t in tasks if ("ver_train", t.id) not in flagged]
    rng = random.Random(SEED)

    with_numbers = [t for t in clean if any(True for _ in grounding.numeric_inputs(t))]
    phase1 = sorted(rng.sample(with_numbers, PHASE1_SIZE), key=lambda t: int(t.id))

    entries = [e for e in handcheck.load(ROOT / "results/handcheck.csv") if e["decision"] == "defect"]
    if len(entries) > DEFECT_CAP:
        by_type = collections.defaultdict(list)
        for e in entries:
            by_type[e["defect_type"]].append(e)
        quota = allocate({k: len(v) for k, v in by_type.items()}, DEFECT_CAP)
        entries = [e for k, v in sorted(by_type.items()) for e in rng.sample(v, quota[k])]
    defects = [{"dataset": e["dataset"], "row": e["row"]} for e in entries]

    mix = collections.Counter(e["calculator"] for e in entries)
    quota = allocate(mix, CONTROL_SIZE)
    by_calc = collections.defaultdict(list)
    for t in clean:
        by_calc[t.meta["calculator"]].append(t)
    control = []
    for calc in sorted(quota):
        control += rng.sample(by_calc[calc], quota[calc])
    control.sort(key=lambda t: int(t.id))

    out = {
        "seed": SEED,
        "phase1": [t.id for t in phase1],
        "defects": defects,
        "control": [t.id for t in control],
        "control_mix": quota,
    }
    (ROOT / "results/samples.json").write_text(json.dumps(out, indent=2) + "\n")
    print(f"phase1 {len(phase1)}, defects {len(defects)}, control {len(control)}")


if __name__ == "__main__":
    main()
