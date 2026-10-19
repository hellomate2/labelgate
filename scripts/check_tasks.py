"""Run the gate on a JSONL file of your own tasks and print one line per flagged task.

Rows the reader rejects and tasks whose formula could not be recomputed are printed too, with the
reason, so a task is never counted as clean because a check skipped it.

usage: python scripts/check_tasks.py tasks.jsonl
"""
import json
import sys

from labelgate.adapters import jsonl
from labelgate.checks import consistency, grounding, outliers, recompute


def main():
    tasks, rejected = jsonl.read(sys.argv[1])
    for number, id_, reason in rejected:
        print(f"rejected line {number} (id {id_ or '?'}): {reason}")
    far = outliers.check(tasks)
    flagged = skipped = 0
    for t in tasks:
        g1 = recompute.check(t)
        if g1["status"] == "skipped":
            skipped += 1
            print(t.id, "G1 skipped:", g1["reason"])
        found = {"G1": g1["status"] == "mismatch", "G2": grounding.check(t),
                 "G3": consistency.check(t), "G4": far.get(t.id, [])}
        found = {k: v for k, v in found.items() if v}
        if found:
            flagged += 1
            print(t.id, json.dumps(found, ensure_ascii=False, default=str))
    print(f"{flagged} of {len(tasks)} tasks flagged; {skipped} could not be recomputed; "
          f"{len(rejected)} rows rejected", file=sys.stderr)


if __name__ == "__main__":
    main()
