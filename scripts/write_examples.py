"""Write examples/*.md, one worked example per file, from the data, handcheck.csv and raw/."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from labelgate import answers, handcheck
from labelgate.adapters import medcalc
from labelgate.checks import recompute

EXAMPLES = [
    ("01-row-1337-range-merged", "Row 1337: a blood pressure range read as one number", ["1337"]),
    ("02-row-1545-readings-mixed", "Row 1545: systolic and diastolic taken from different readings", ["1545"]),
    ("03-row-2685-calcium-range", "Row 2685: a calcium range read as one value", ["2685"]),
    ("04-rows-6171-8473-8678-one-typo-three-labels", "Rows 6171, 8473 and 8678: one note typo, three wrong labels", ["6171", "8473", "8678"]),
    ("05-row-267-copied-typo", "Row 267: an impossible unit copied from the note", ["267"]),
]
MODELS = ("haiku", "sonnet", "opus")


def fmt(x):
    return f"{x:,.6g}" if abs(x) >= 1e-3 or x == 0 else f"{x:.6g}"


def model_lines(task):
    lines = []
    for model in MODELS:
        path = medcalc.raw_path(ROOT, model, "calc", "ver_train", task.id)
        if not path.exists():
            continue
        record = json.loads(path.read_text())
        text = str(record["cli"].get("result", ""))
        parsed = answers.parse(text, task.meta["calculator_id"])
        raw = answers.answer_text(text)
        verdict = "rewarded" if task.accepts(parsed) else "not rewarded"
        lines.append(f"- {model}: answer field `{raw}`, parsed as {parsed}, {verdict} by the stored label.")
    return lines


def section(task, entry):
    lines = [f"## Row {task.id}, {task.meta['calculator']}", ""]
    lines.append("| | |")
    lines.append("|---|---|")
    for q in handcheck.quotes(entry):
        lines.append(f"| Note says | `{q}` |")
    for name in entry["field"].split(";"):
        if name in task.fields:
            value, unit = task.fields[name]
            lines.append(f"| Extracted input | {name} = `{value}` {unit or ''} |")
    lines.append(f"| Stored answer, as stored | `{task.meta['label_text']}` (accepted range {fmt(task.lower)} to {fmt(task.upper)}) |")
    if task.formula:
        lines.append(f"| Recomputed from the extracted inputs | `{fmt(recompute.recompute(task))}` |")
    bounds = handcheck.interval(task, entry["note_inputs"])
    if bounds:
        head = "What the note supports" + (f", if {entry['interval_assumes']}" if entry.get("interval_assumes") else "")
        values = handcheck.note_values(task, entry["note_inputs"])
        text = f"`{fmt(min(values))}` to `{fmt(max(values))}`"
        if (min(values), max(values)) != bounds:
            text += f" (`{fmt(bounds[0])}` to `{fmt(bounds[1])}` with the 5% tolerance)"
        lines.append(f"| {head} | {text} |")
    elif entry["defect_kind"] == "copied typo":
        lines.append("| What the note supports | no interval: the note itself prints the impossible value |")
    else:
        lines.append("| What the note supports | nothing: the note gives no value this input could be replaced with |")
    lines += ["", f"Defect: {entry['defect_type']} ({entry['defect_kind']}). {entry['reason'][:1].upper() + entry['reason'][1:]}.", ""]
    if task.formula == "mean_arterial_pressure" and bounds:
        lines.append("Arithmetic: MAP = SBP / 3 + 2 x DBP / 3. With the stored inputs that is "
                     f"{task.fields['sbp'][0]:g} / 3 + 2 x {task.fields['dbp'][0]:g} / 3 = {fmt(recompute.recompute(task))}.")
        lines.append("")
    models = model_lines(task)
    if models:
        lines += ["Model answers on the original MedCalc-Bench zero-shot prompt:", ""] + models + [""]
    return lines


def main():
    tasks = {t.id: t for t in medcalc.load(ROOT / "data/ver_train.csv", "ver_train")}
    entries = {e["row"]: e for e in handcheck.load(ROOT / "results/handcheck.csv") if e["dataset"] == "ver_train"}
    out = ROOT / "examples"
    out.mkdir(exist_ok=True)
    for slug, title, rows in EXAMPLES:
        lines = [f"# {title}", "", "MedCalc-Bench Verified train split, release v1.0.8 (commit 58fc3de). "
                 "Quotes are copied from the row's Patient Note and checked by tests/test_handcheck.py.", ""]
        for row in rows:
            lines += section(tasks[row], entries[row])
        (out / f"{slug}.md").write_text("\n".join(lines).rstrip() + "\n")
        print("wrote", slug)


if __name__ == "__main__":
    main()
