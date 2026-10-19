"""Turn the gate, the hand-check and any cached model calls into result tables.

Writes:
  results/results_table.csv           the headline numbers, each with k, n and a Wilson 95% interval
  results/defects_by_calculator.csv   confirmed defects by calculator and type
  results/model_scores.csv            one line per cached calculation call
  results/phase1_disagreements.csv    Sonnet re-extraction values that differ from the stored input
  results/checks.csv                  per check and split: rows flagged, decided, defects, false flags
  results/detection.csv               per confirmed defect: which checks fired on it
  results/verified_relabeled.csv      per confirmed defect: the v1.2 label next to the Verified label
  results/g2_formats.csv              per G2-flagged row: whether the format-aware reader still flags it
  results/range_screen.csv            every row a heart-rate or weight range check flags
  results/homa_ir.csv                 every HOMA-IR training row with insulin in pmol/L, stored and corrected label
Nothing here is typed by hand: every number comes from results/, data/ or raw/.
"""
import collections
import csv
import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from labelgate import answers, handcheck, stats, units
from labelgate.adapters import medcalc
from labelgate.checks import grounding, outliers

RESULTS = ROOT / "results"
TABLE_FIELDS = ["id", "metric", "split", "k", "n", "value", "ci_low", "ci_high", "note"]
MODELS = ("haiku", "sonnet", "opus")
G2_SPLIT_SEED = 20261018
# Plain physiological range checks, used only to describe how cheap the defects are to find.
# Both bounds were picked after the defects were known, so they are not a held-out test.
HEART_RATE_BPM = (15, 300)
WEIGHT_MAX_KG = 400
G4_LOWER_FACTOR = 30
HOMA_IR_ID = 31
HOMA_FACTOR = 6.0


def proportion(id_, metric, split, k, n, note=""):
    low, high = stats.wilson(k, n)
    return {"id": id_, "metric": metric, "split": split, "k": k, "n": n,
            "value": "" if n == 0 else round(k / n, 6),
            "ci_low": "" if low is None else round(low, 6), "ci_high": "" if high is None else round(high, 6),
            "note": note}


def missing(id_, metric, split, note):
    return {"id": id_, "metric": metric, "split": split, "k": "", "n": "", "value": "", "ci_low": "", "ci_high": "", "note": note}


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def model_scores(tasks, entries, samples):
    by_row = {(e["dataset"], e["row"]): e for e in entries}
    sets = [("defects", d["dataset"], d["row"]) for d in samples["defects"]]
    sets += [("control", "ver_train", r) for r in samples["control"]]
    rows = []
    for model in MODELS:
        for set_name, dataset, row in sets:
            path = medcalc.raw_path(ROOT, model, "calc", dataset, row)
            if not path.exists():
                continue
            record = json.loads(path.read_text())
            task = tasks[(dataset, row)]
            answer = answers.parse(str(record["cli"].get("result", "")), task.meta["calculator_id"])
            entry = by_row.get((dataset, row), {})
            bounds = handcheck.interval(task, entry.get("note_inputs", "")) if entry else None
            rewarded = task.accepts(answer)
            in_note = bounds is not None and answer is not None and bounds[0] - 1e-9 <= answer <= bounds[1] + 1e-9
            literal = answer is not None and task.label is not None and abs(answer - task.label) <= 1e-6 * max(1, abs(task.label))
            rows.append({
                "model": model, "set": set_name, "dataset": dataset, "row": row,
                "calculator": task.meta["calculator"], "defect_kind": entry.get("defect_kind", ""),
                "defect_type": entry.get("defect_type", ""), "answer": "" if answer is None else answer,
                "stored_label": task.meta["label_text"], "rewarded": int(rewarded),
                "note_low": "" if bounds is None else round(bounds[0], 6),
                "note_high": "" if bounds is None else round(bounds[1], 6),
                "in_note_interval": int(in_note), "matches_stored_label": int(literal),
                "outcome": "rewarded" if rewarded else ("note-supported" if in_note else "neither"),
            })
    return rows


def phase1_disagreements(tasks, samples):
    rows = []
    for row in samples["phase1"]:
        path = medcalc.raw_path(ROOT, "sonnet", "extract", "ver_train", row)
        if not path.exists():
            continue
        task = tasks[("ver_train", row)]
        text = str(json.loads(path.read_text())["cli"].get("result", ""))
        start, end = text.find("{"), text.rfind("}")
        try:
            got = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            rows.append({"row": row, "field": "", "stored": "", "stored_unit": "", "model_value": "",
                         "model_unit": "", "model_span": "", "status": "unparsed"})
            continue
        for name, (value, unit) in task.fields.items():
            if name not in got or isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            item = got[name] or {}
            mv = item.get("value")
            try:
                mv = None if mv is None else float(mv)
            except (TypeError, ValueError):
                mv = None
            agree = mv is not None and abs(mv - value) <= 0.05 * max(abs(value), 1e-9)
            if not agree:
                rows.append({"row": row, "field": name, "stored": value, "stored_unit": unit or "",
                             "model_value": "" if mv is None else mv, "model_unit": item.get("unit") or "",
                             "model_span": item.get("span") or "", "status": "disagree"})
    return rows


def fired(entry, check):
    return any(c.startswith(check + ":") for c in entry["checks"].split(";"))


def check_rows(entries):
    """One line per check and split: flagged, decided, defects, false flags, false flags that are number formats."""
    rows = []
    for dataset, split in (("ver_train", "train"), ("ver_test", "test")):
        mine = [e for e in entries if e["dataset"] == dataset]
        defects = [e for e in mine if e["decision"] == "defect"]
        for check in ("G1", "G2", "G3", "G4"):
            hit = [e for e in mine if fired(e, check)]
            decided = [e for e in hit if e["decision"] != "unclear"]
            k = sum(e["decision"] == "defect" for e in decided)
            false = [e for e in decided if e["decision"] == "not a defect"]
            others = [c for c in ("G1", "G2", "G3", "G4") if c != check]
            only = [e for e in defects if fired(e, check) and not any(fired(e, c) for c in others)]
            low, high = stats.wilson(k, len(decided))
            rows.append({"check": check, "split": split, "flagged": len(hit), "decided": len(decided), "defects": k,
                         "precision": "" if not decided else round(k / len(decided), 6),
                         "ci_low": "" if low is None else round(low, 6), "ci_high": "" if high is None else round(high, 6),
                         "false_flags": len(false),
                         "format_false_flags": sum(e["reason"].startswith("number format") for e in false),
                         "defects_only_this_check": len(only)})
    return rows


def range_flags(task):
    """Fields outside a plain physiological range: heart rate 15 to 300 bpm, weight at most 400 kg."""
    out = []
    value, unit = task.fields.get("heart_rate", (None, None))
    if isinstance(value, (int, float)) and not isinstance(value, bool) and not HEART_RATE_BPM[0] <= value <= HEART_RATE_BPM[1]:
        out.append(("heart_rate", value, unit))
    value, unit = task.fields.get("weight", (None, None))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            if units.weight_kg(value, unit) > WEIGHT_MAX_KG:
                out.append(("weight", value, unit))
        except units.UnitError:
            pass
    return out


def range_screen_rows(tasks, entries):
    by_row = {(e["dataset"], e["row"]): e for e in entries}
    rows = []
    for (dataset, row), task in sorted(tasks.items(), key=lambda kv: (kv[0][0], int(kv[0][1]))):
        for name, value, unit in range_flags(task):
            e = by_row.get((dataset, row))
            rows.append({"dataset": dataset, "row": row, "calculator": task.meta["calculator"], "field": name,
                         "value": value, "unit": unit, "decision": e["decision"] if e else "not flagged by the gate"})
    return rows


def detection_rows(entries, tasks, lower_g4):
    """Which checks fired on each confirmed defect. g4_label means G4 fired on the stored label itself.

    range_check means a heart-rate or weight range check fires; g4_30x means G4 at the lower, post hoc factor fires.
    """
    rows = []
    for e in entries:
        if e["decision"] != "defect":
            continue
        checks = [c for c in ("G1", "G2", "G3", "G4") if fired(e, c)]
        in_range = bool(range_flags(tasks[(e["dataset"], e["row"])]))
        rows.append({"dataset": e["dataset"], "row": e["row"], "defect_kind": e["defect_kind"],
                     "defect_type": e["defect_type"], "checks": " ".join(checks),
                     "g4": int("G4" in checks), "g4_label": int("G4:label:label" in e["checks"].split(";")),
                     "missed_by_g4": int("G4" not in checks), "g3": int("G3" in checks),
                     "range_check": int(in_range),
                     "g4_g3_or_range": int("G4" in checks or "G3" in checks or in_range),
                     "g4_30x": int(e["row"] in lower_g4.get(e["dataset"], set()))})
    return rows


def homa_rows(tasks, entries):
    """HOMA-IR training rows with insulin in pmol/L.

    The dataset's explanation converts pmol/L to µIU/mL by multiplying by 6 ("756.0 * 6 µIU/mL/pmol/L").
    About 6 pmol/L make 1 µIU/mL, so the conversion should divide by 6, and the stored label is 36 times
    too large. corrected_label uses the same factor of 6, divided instead of multiplied.
    """
    defects = {(e["dataset"], e["row"]) for e in entries if e["decision"] == "defect"}
    rows = []
    for (dataset, row), t in sorted(tasks.items(), key=lambda kv: (kv[0][0], int(kv[0][1]))):
        if t.meta["calculator_id"] != HOMA_IR_ID:
            continue
        insulin, unit = t.fields["Insulin"]
        if unit != "pmol/L":
            continue
        glucose = units.concentration(*t.fields["glucose"], "glucose", "mg/dL")
        corrected = insulin / HOMA_FACTOR * glucose / 405
        rows.append({"dataset": dataset, "row": row, "insulin_pmol_l": insulin, "glucose_mg_dl": round(glucose, 4),
                     "stored_label": t.meta["label_text"], "corrected_label": round(corrected, 4),
                     "ratio": round(t.label / corrected, 3),
                     "explanation_multiplies_by_6": int(bool(re.search(r"\* 6(\.0)? µIU/mL/pmol/L", t.meta["explanation"]))),
                     "in_confirmed_defects": int((dataset, row) in defects)})
    return rows


def same_to_shorter_precision(a_text, b_text):
    """True when two label strings agree once the longer one is rounded to the shorter one's significant figures."""
    def sig(text):
        digits = text.lower().split("e")[0].replace("-", "").replace(".", "").lstrip("0")
        return max(1, len(digits))
    a, b = float(a_text), float(b_text)
    n = min(sig(a_text), sig(b_text))
    return float(f"{a:.{n}g}") == float(f"{b:.{n}g}")


def numbers_in_equation(explanation):
    """The numbers in the explanation's last 'Plugging' sentence, as strings."""
    lines = [line for line in explanation.splitlines() if "Plugging" in line]
    if not lines:
        return []
    equation = lines[-1].split("=")[0]
    return re.findall(r"\d+(?:\.\d+)?", equation)


def precision_change(old, new):
    """How a changed label differs: the label re-rounded, an intermediate value re-rounded, or neither."""
    if same_to_shorter_precision(old.meta["label_text"], new.meta["label_text"]):
        return "label re-rounded"
    a, b = numbers_in_equation(old.meta["explanation"]), numbers_in_equation(new.meta["explanation"])
    if a and len(a) == len(b) and all(same_to_shorter_precision(x, y) for x, y in zip(a, b)):
        changed = [f"{x} to {y}" for x, y in zip(a, b) if x != y]
        return "intermediate re-rounded: " + "; ".join(changed)
    return "other"


def relabeled_rows(entries):
    """The v1.2 label next to the Verified label for every confirmed defect, joined on Calculator ID plus Note ID."""
    old = {}
    for dataset, split in (("v12_train", "ver_train"), ("v12_test", "ver_test")):
        for t in medcalc.load(ROOT / f"data/{dataset}.csv", dataset):
            old[(split, t.meta["calculator_id"], t.meta["note_id"])] = t
    tasks = medcalc.load_splits(ROOT / "data")
    rows = []
    for e in entries:
        if e["decision"] != "defect":
            continue
        t = tasks[(e["dataset"], e["row"])]
        o = old.get((e["dataset"], t.meta["calculator_id"], t.meta["note_id"]))
        changed = o is not None and o.label is not None and t.label is not None and o.label != t.label
        rows.append({"dataset": e["dataset"], "row": e["row"], "calculator": t.meta["calculator"],
                     "defect_kind": e["defect_kind"], "v12_row": "" if o is None else o.id,
                     "v12_label": "" if o is None else o.meta["label_text"], "verified_label": t.meta["label_text"],
                     "label_changed": int(changed),
                     "rerounded_only": int(changed and same_to_shorter_precision(o.meta["label_text"], t.meta["label_text"])),
                     "precision_change": precision_change(o, t) if changed else "",
                     "same_inputs": "" if o is None else int(o.fields == t.fields)})
    return rows


def g2_format_rows(entries, tasks):
    """Rerun G2 with the format-aware reader on every G2-flagged Verified row.

    Train rows are split in half with a fixed seed. The four formats the reader handles were chosen
    by reading the dev half only; the held-out half and the test split were not read for that step.
    The reader only adds candidate numbers, so every row it still flags already has a hand-check decision.
    """
    g2 = [e for e in entries if fired(e, "G2")]
    train = sorted((e for e in g2 if e["dataset"] == "ver_train"), key=lambda e: int(e["row"]))
    random.Random(G2_SPLIT_SEED).shuffle(train)
    part = {("ver_train", e["row"]): ("dev" if i < len(train) // 2 else "held-out") for i, e in enumerate(train)}
    rows = []
    for e in g2:
        still = bool(grounding.check(tasks[(e["dataset"], e["row"])], formats=True))
        rows.append({"dataset": e["dataset"], "row": e["row"], "part": part.get((e["dataset"], e["row"]), "test"),
                     "decision": e["decision"], "still_flagged": int(still)})
    return rows


def g2_format_table(rows):
    out = []
    for part in ("dev", "held-out", "test"):
        mine = [r for r in rows if r["part"] == part and r["decision"] != "unclear"]
        for reader, keep in (("original reader", lambda r: True), ("format-aware reader", lambda r: r["still_flagged"])):
            kept = [r for r in mine if keep(r)]
            k = sum(r["decision"] == "defect" for r in kept)
            out.append(proportion("g2-formats", f"G2 precision, {reader}", part, k, len(kept),
                                  f"{len(mine) - len(kept)} flags removed"))
    return out


def main():
    tasks = medcalc.load_splits(ROOT / "data")
    summary = json.loads((RESULTS / "gate_summary.json").read_text())
    entries = handcheck.load(RESULTS / "handcheck.csv")
    samples = json.loads((RESULTS / "samples.json").read_text())
    with open(RESULTS / "flags.csv", newline="", encoding="utf-8") as f:
        flags = {(r["dataset"], r["row"]): r for r in csv.DictReader(f)}
    table = []

    for dataset, split in (("ver_train", "train"), ("ver_test", "test")):
        rows = summary[dataset]["counts"]["rows"]
        mine = [e for e in entries if e["dataset"] == dataset]
        defects = [e for e in mine if e["decision"] == "defect"]
        unclear = [e for e in mine if e["decision"] == "unclear"]
        covered = [e for e in defects if flags[(dataset, e["row"])]["g1_status"] == "match"]
        table.append(proportion("1", "confirmed wrong labels", split, len(defects), rows))
        table.append(proportion("1-g1", "confirmed wrong labels the formula recompute covers and passes", split,
                                len(covered), len(defects)))
        for kind in ("extraction", "copied typo"):
            k = sum(e["defect_kind"] == kind for e in defects)
            table.append(proportion(f"1-{kind}", f"confirmed wrong labels: {kind}", split, k, rows))
        listed = " ".join(e["row"] for e in unclear)
        table.append(proportion("4", "gate precision (confirmed / flagged, unclear excluded)", split,
                                len(defects), len(mine) - len(unclear),
                                f"{len(mine)} flagged; unclear rows left out: {listed or 'none'}"))

    for dataset, label in (("ver_train", "Verified v1.0.8"), ("v12_train", "v1.2")):
        counts = summary[dataset]["counts"]
        n = counts.get("g1_match", 0) + counts.get("g1_mismatch", 0)
        table.append(proportion("2", f"formula recompute mismatches, {label}", "train", counts.get("g1_mismatch", 0), n,
                                f"skipped {counts.get('g1_skipped', 0)}"))

    defects = [e for e in entries if e["decision"] == "defect"]
    by_calc = collections.Counter((e["calculator"], e["defect_kind"], e["defect_type"]) for e in defects)
    write_csv(RESULTS / "defects_by_calculator.csv",
              [{"calculator": c, "defect_kind": k, "defect_type": t, "rows": n} for (c, k, t), n in sorted(by_calc.items())],
              ["calculator", "defect_kind", "defect_type", "rows"])

    disagreements = phase1_disagreements(tasks, samples)
    write_csv(RESULTS / "phase1_disagreements.csv", disagreements,
              ["row", "field", "stored", "stored_unit", "model_value", "model_unit", "model_span", "status"])
    done = sum(medcalc.raw_path(ROOT, "sonnet", "extract", "ver_train", r).exists() for r in samples["phase1"])
    review = RESULTS / "phase1_handcheck.csv"
    if done == len(samples["phase1"]) and review.exists():
        confirmed = sum(r["decision"] == "defect" for r in handcheck.load(review))
        table.append(proportion("5", "confirmed defects among unflagged rows (Sonnet re-extraction)", "train", confirmed, done))
    else:
        table.append(missing("5", "confirmed defects among unflagged rows (Sonnet re-extraction)", "train",
                             f"not run: {done} of {len(samples['phase1'])} Sonnet calls cached"))

    scores = model_scores(tasks, entries, samples)
    write_csv(RESULTS / "model_scores.csv", scores,
              ["model", "set", "dataset", "row", "calculator", "defect_kind", "defect_type", "answer", "stored_label",
               "rewarded", "note_low", "note_high", "in_note_interval", "matches_stored_label", "outcome"])
    with_interval = {(e["dataset"], e["row"]) for e in defects if e["defect_kind"] == "extraction" and e["note_inputs"]}
    shares = {}
    for model in MODELS:
        mine = [s for s in scores if s["model"] == model and s["set"] == "defects" and (s["dataset"], s["row"]) in with_interval]
        if len(mine) < len(with_interval):
            table.append(missing("6", f"{model}: note-supported answers the stored label scores wrong", "train",
                                 f"not run: {len(mine)} of {len(with_interval)} calls cached"))
        else:
            k = sum(s["in_note_interval"] and not s["rewarded"] for s in mine)
            shares[model] = (k, len(mine))
            table.append(proportion("6", f"{model}: note-supported answers the stored label scores wrong", "train", k, len(mine)))
        control = [s for s in scores if s["model"] == model and s["set"] == "control"]
        if model != "opus":
            if len(control) < len(samples["control"]):
                table.append(missing("6-control", f"{model}: clean-row accuracy", "train",
                                     f"not run: {len(control)} of {len(samples['control'])} calls cached"))
            else:
                table.append(proportion("6-control", f"{model}: clean-row accuracy", "train",
                                        sum(s["rewarded"] for s in control), len(control)))
    if "sonnet" in shares and "haiku" in shares:
        a = {(s["dataset"], s["row"]): s for s in scores if s["model"] == "sonnet" and s["set"] == "defects"}
        b = {(s["dataset"], s["row"]): s for s in scores if s["model"] == "haiku" and s["set"] == "defects"}
        keys = sorted(with_interval)
        diff, low, high = stats.paired_bootstrap([a[k]["in_note_interval"] for k in keys], [b[k]["in_note_interval"] for k in keys])
        table.append({"id": "6-diff", "metric": "sonnet minus haiku, share inside note interval", "split": "train",
                      "k": "", "n": len(keys), "value": round(diff, 6), "ci_low": round(low, 6), "ci_high": round(high, 6),
                      "note": "paired bootstrap, 10,000 resamples over rows, seed 0"})

    train_rows = summary["ver_train"]["counts"]["rows"]
    extraction = sum(e["defect_kind"] == "extraction" and e["dataset"] == "ver_train" for e in defects)
    per_1000 = 1000 * extraction / train_rows
    if "sonnet" in shares:
        k, n = shares["sonnet"]
        table.append({"id": "7", "metric": "per 1,000 training rows: rows where the label scores a note-supported answer wrong",
                      "split": "train", "k": "", "n": "", "value": round(per_1000 * k / n, 6), "ci_low": "", "ci_high": "",
                      "note": f"1000 x ({extraction} / {train_rows}) x ({k} / {n})"})
    else:
        table.append({"id": "7", "metric": "per 1,000 training rows: extraction-defect rows (first factor only)",
                      "split": "train", "k": extraction, "n": train_rows, "value": round(per_1000, 6), "ci_low": "", "ci_high": "",
                      "note": f"1000 x ({extraction} / {train_rows}); the Sonnet share factor is not run"})

    typo_rows = {(e["dataset"], e["row"]) for e in defects if e["defect_kind"] == "copied typo"}
    for model in MODELS:
        mine = [s for s in scores if s["model"] == model and (s["dataset"], s["row"]) in typo_rows]
        if len(mine) < len(typo_rows):
            table.append(missing("8", f"{model}: copied-typo rows answered with the literal stored label", "train+test",
                                 f"not run: {len(mine)} of {len(typo_rows)} calls cached"))
        else:
            k = sum(s["matches_stored_label"] or s["rewarded"] for s in mine)
            table.append({"id": "8", "metric": f"{model}: copied-typo rows answered with the literal stored label",
                          "split": "train+test", "k": k, "n": len(mine), "value": "", "ci_low": "", "ci_high": "",
                          "note": f"{len(mine) - k} answered something else"})

    checks = check_rows(entries)
    write_csv(RESULTS / "checks.csv", checks, list(checks[0]))
    lower_g4 = {}
    for dataset in ("ver_train", "ver_test"):
        mine = [t for (d, _r), t in tasks.items() if d == dataset]
        lower_g4[dataset] = set(outliers.check(mine, factor=G4_LOWER_FACTOR))
    detection = detection_rows(entries, tasks, lower_g4)
    write_csv(RESULTS / "detection.csv", detection, list(detection[0]))
    train_found = [d for d in detection if d["dataset"] == "ver_train"]
    table.append(proportion("found-G4", "confirmed defects the G4 outlier screen flags", "train",
                            sum(d["g4"] for d in train_found), len(train_found)))
    table.append(proportion("found-G4-label", "confirmed defects whose stored label alone is a G4 outlier", "train",
                            sum(d["g4_label"] for d in train_found), len(train_found)))
    table.append(proportion("found-G2G3-only", "confirmed defects only G2 or G3 flags", "train",
                            sum(d["missed_by_g4"] for d in train_found), len(train_found)))
    table.append(proportion("found-G4-G3", "confirmed defects G4 or G3 flags", "train",
                            sum(d["g4"] or d["g3"] for d in train_found), len(train_found)))
    table.append(proportion("found-screens", "confirmed defects G4, G3 or a heart-rate or weight range check flags",
                            "train", sum(d["g4_g3_or_range"] for d in train_found), len(train_found),
                            f"heart rate {HEART_RATE_BPM[0]} to {HEART_RATE_BPM[1]} bpm, weight at most {WEIGHT_MAX_KG} kg; "
                            "bounds picked after the defects were known"))
    table.append(proportion("found-G4-30x", f"confirmed defects G4 flags at {G4_LOWER_FACTOR}x instead of 100x", "train",
                            sum(d["g4_30x"] for d in train_found), len(train_found),
                            f"post hoc; G4 at {G4_LOWER_FACTOR}x flags {len(lower_g4['ver_train'])} train rows"))
    screen = range_screen_rows(tasks, entries)
    write_csv(RESULTS / "range_screen.csv", screen, ["dataset", "row", "calculator", "field", "value", "unit", "decision"])
    train_screen = {r["row"] for r in screen if r["dataset"] == "ver_train"}
    table.append(proportion("range-screen", "train rows a heart-rate or weight range check flags that are confirmed defects",
                            "train", sum(r["dataset"] == "ver_train" and r["decision"] == "defect" for r in screen),
                            len(train_screen), " ".join(sorted(train_screen, key=int))))
    homa = homa_rows(tasks, entries)
    write_csv(RESULTS / "homa_ir.csv", homa, list(homa[0]))
    homa_train = [r for r in homa if r["dataset"] == "ver_train"]
    homa_all = sum(t.meta["calculator_id"] == HOMA_IR_ID for (d, _r), t in tasks.items() if d == "ver_train")
    ratios = [r["ratio"] for r in homa_train]
    table.append(proportion("homa-ir", "HOMA-IR training labels with insulin in pmol/L, inflated by the conversion bug",
                            "train", len(homa_train), homa_all,
                            f"stored / corrected label from {min(ratios)} to {max(ratios)}"))
    table.append(proportion("homa-ir-new", "of those, rows outside the confirmed defects", "train",
                            sum(not r["in_confirmed_defects"] for r in homa_train), len(homa_train)))
    relabeled = relabeled_rows(entries)
    write_csv(RESULTS / "verified_relabeled.csv", relabeled, list(relabeled[0]))
    table.append(proportion("relabeled", "confirmed defects whose label the Verified pass changed", "train+test",
                            sum(r["label_changed"] for r in relabeled), len(relabeled)))
    g2_rows = g2_format_rows(entries, tasks)
    write_csv(RESULTS / "g2_formats.csv", g2_rows, list(g2_rows[0]))
    table += g2_format_table(g2_rows)

    write_csv(RESULTS / "results_table.csv", table, TABLE_FIELDS)
    for row in table:
        print(row["id"], row["metric"], row["split"], row["k"], row["n"], row["value"], row["ci_low"], row["ci_high"], row["note"], sep=" | ")


if __name__ == "__main__":
    main()
