"""Draft hand-check entries for flagged grounding hits that are only number formatting.

For each G2 not_found flag, look for the value in the note written as "9 500" (space thousands),
"3,79" (decimal comma), "64. 4", "16.4 x 10^4" or "2.5 lakh". If every flag on a row is explained
this way, the row gets a drafted "not a defect" entry with the matched note text as its quote.
Rows with any other flag are listed for manual review. The draft is a reviewer aid: the reviewer
still reads each row and copies the entries into results/handcheck.csv.

usage: python scripts/handcheck_assist.py ver_train > draft.csv
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from labelgate.adapters import medcalc

SPACE = "[    ]"
TIMES = r"\s*[×xX*]\s*10\s*\^?\s*"


def _plain(x):
    text = f"{x:.6f}".rstrip("0").rstrip(".")
    return text


def candidates(value):
    """Yield (reason, regex) pairs for ways the value can be written."""
    text = _plain(value)
    whole, _, frac = text.partition(".")
    if len(whole) > 3:
        groups = []
        while len(whole) > 3:
            groups.insert(0, whole[-3:])
            whole = whole[:-3]
        groups.insert(0, whole)
        yield "space as thousands separator", SPACE.join(groups) + (r"\." + frac if frac else "")
    if frac:
        yield "decimal comma", re.escape(whole) + "," + re.escape(frac) + r"0*(?!\d)"
        yield "space after decimal point", re.escape(whole) + r"[.,] " + re.escape(frac) + r"0*(?!\d)"
    for exp in range(3, 13):
        mantissa = value / 10 ** exp
        if 1 <= mantissa < 1000 and abs(round(mantissa, 2) - mantissa) < 1e-9:
            m = _plain(round(mantissa, 2))
            yield "scientific notation", r"(?<![\d.])" + re.escape(m) + r"0*" + TIMES + str(exp) + r"(?!\d)"
    if value >= 1e4:
        yield "lakh", re.escape(_plain(value / 1e5)) + r"0*\s*lakh"


def explain(value, note):
    for reason, pattern in candidates(value):
        m = re.search(pattern, note)
        if m:
            return reason, m.group(0)
    return None, None


def main():
    dataset = sys.argv[1]
    tasks = {t.id: t for t in medcalc.load(ROOT / f"data/{dataset}.csv", dataset)}
    with open(ROOT / "results/flags.csv", newline="", encoding="utf-8") as f:
        flags = [r for r in csv.DictReader(f) if r["dataset"] == dataset]
    writer = csv.writer(sys.stdout)
    writer.writerow(["dataset", "row", "calculator", "checks", "field", "reason", "quote"])
    manual = []
    for flag in flags:
        details = json.loads(flag["details"])
        others = details["G3"] or details["G4"] or flag["g1_status"] == "mismatch"
        found = []
        for g2 in details["G2"]:
            if g2["kind"] != "not_found":
                others = True
                continue
            reason, quote = explain(g2["value"], tasks[flag["row"]].source_text)
            if reason is None:
                others = True
            found.append((g2["field"], reason, quote))
        if others:
            manual.append(flag["row"])
            continue
        for field, reason, quote in found:
            writer.writerow([dataset, flag["row"], flag["calculator"], flag["checks"], field, reason, quote])
    print("manual:", " ".join(manual), file=sys.stderr)


if __name__ == "__main__":
    main()
