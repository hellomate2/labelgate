"""Render report.html from results/, data/ and raw/.

Every count and rate on the page is read from results/ (results_table.csv, checks.csv, detection.csv,
verified_relabeled.csv, g2_formats.csv, gate_summary.json, handcheck.csv, defects_by_calculator.csv,
samples.json, call_log.csv), the pinned data CSVs, or a cached model call in raw/. The prose around
them is fixed text and names a few note values in passing.

usage: python scripts/build_report.py
"""
import collections
import csv
import datetime
import html
import json
import re
from pathlib import Path

from labelgate import answers, handcheck
from labelgate.adapters import medcalc
from labelgate.checks import recompute

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
MODELS = ("haiku", "sonnet", "opus")
MODEL_NAMES = {"haiku": "Haiku", "sonnet": "Sonnet", "opus": "Opus"}
COMMIT = "58fc3de"
RELEASE = "v1.0.8"
FORMULA_NAMES = {"ckd_epi_2021": "CKD-EPI 2021"}
SHORT = {
    "Albumin Corrected Anion Gap": "Albumin-corrected anion gap",
    "Albumin Corrected Delta Gap": "Albumin-corrected delta gap",
    "Albumin Corrected Delta Ratio": "Albumin-corrected delta ratio",
    "Anion Gap": "Anion gap",
    "Body Mass Index (BMI)": "BMI",
    "CKD-EPI Equations for Glomerular Filtration Rate": "CKD-EPI",
    "Calcium Correction for Hypoalbuminemia": "Calcium correction",
    "Creatinine Clearance (Cockcroft-Gault Equation)": "Cockcroft-Gault",
    "Delta Gap": "Delta gap",
    "Delta Ratio": "Delta ratio",
    "Fibrosis-4 (FIB-4) Index for Liver Fibrosis": "FIB-4",
    "Free Water Deficit": "Free water deficit",
    "HOMA-IR (Homeostatic Model Assessment for Insulin Resistance)": "HOMA-IR",
    "Ideal Body Weight": "Ideal body weight",
    "MDRD GFR Equation": "MDRD",
    "Maintenance Fluids Calculations": "Maintenance fluids",
    "Mean Arterial Pressure (MAP)": "MAP",
    "PERC Rule for Pulmonary Embolism": "PERC",
    "SIRS Criteria": "SIRS",
    "Serum Osmolality": "Serum osmolality",
    "Sodium Correction for Hyperglycemia": "Sodium correction",
    "Wells' Criteria for Pulmonary Embolism": "Wells PE",
}
TYPES = [("range merged", "Range merged"), ("readings mixed", "Readings mixed"),
         ("unit tag does not match note", "Unit tag wrong"), ("multiplier dropped", "Power of ten lost"),
         ("other", "Other extraction"), ("source typo copied", "Copied typo")]
# Rows the gate flagged that are not label defects under this method, though a clinician would call the task invalid.
INVALID_TASK_ROWS = {"fluids": ["4656", "4850", "4860"], "child_sirs": ["6805"]}
# Counted defects that are also adult formulas applied to a child.
CHILD_DEFECT_ROWS = {"sirs": "6732", "ckd_epi": "458"}
# Checked against 2512.19691's released training labels (github.com/junzeye/validate-medcalc-labels) and the
# Verified HF HEAD on 2026-10-18, outside this repo. Printed only while the defect count still matches.
PRIOR_WORK = {"rows": 52, "sampled": 27, "differ": 18, "no_public": 34, "checked": "October 18, 2026"}
# Unclear rows that a second check on 2026-10-18 read as the same patterns as counted rows. They stay unclear, so the
# count stays at its floor. Printed only while every one of them is still marked unclear.
SECOND_CHECK_UNCLEAR = ["6414", "6639", "6653", "6769"]

E = html.escape


def short(calculator):
    return SHORT.get(calculator, calculator)


def num(x, small_sig=4):
    """Thousands commas, at most 2 decimals at 1 and above, 4 significant figures below 1."""
    if x is None:
        return ""
    x = float(x)
    if x == 0:
        return "0"
    if abs(x) >= 1:
        text = f"{x:,.2f}"
        return text.rstrip("0").rstrip(".") if "." in text else text
    return f"{x:.{small_sig}g}"


def span(low, high):
    """Both ends of a range with the same number of decimals."""
    top = max(abs(low), abs(high))
    if top == 0:
        return "0"
    if top >= 10000:
        places = 0
    elif top >= 1000:
        places = 1
    elif min(abs(low), abs(high)) >= 1 or top >= 1:
        places = 2
    else:
        smallest = min(x for x in (abs(low), abs(high)) if x > 0)
        places = max(2, 3 - int(f"{smallest:e}".split("e")[1]))
    return f"{low:,.{places}f} to {high:,.{places}f}"


def raw_value(v):
    """An extracted input as stored, without thousands commas, so 150160 reads as 150160."""
    if isinstance(v, float) and v.is_integer() and abs(v) < 1e15:
        return str(int(v))
    return f"{v:g}" if isinstance(v, float) else str(v)


def pct(x):
    x = float(x) * 100
    if x == 0:
        return "0%"
    return f"{x:.2f}%" if x < 10 else f"{x:.1f}%"


def count(k, n):
    return f"{int(k):,} of {int(n):,}"


def read_csv(name):
    with open(RESULTS / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def find(table, id_, split=None, contains=None):
    for r in table:
        if r["id"] == id_ and (split is None or r["split"] == split) and (contains is None or contains in r["metric"]):
            return r
    raise KeyError((id_, split, contains))


def sentence_bounds(text, i, j):
    start = max(text.rfind(". ", 0, i), text.rfind("\n", 0, i))
    start = 0 if start < 0 else start + 1
    ends = [p for p in (text.find(". ", j), text.find("\n", j)) if p >= 0]
    return start, (min(ends) + 1 if ends else len(text))


def note_excerpts(text, quotes, limit=300):
    """One excerpt per note sentence, with every quote in that sentence wrapped in <mark>.

    Long sentences are trimmed at a word boundary on each side of the marked text.
    """
    groups = {}
    for q in quotes:
        i = text.find(q)
        if i < 0:
            raise ValueError(f"quote not in note: {q!r}")
        groups.setdefault(sentence_bounds(text, i, i + len(q)), []).append((i, i + len(q)))
    out = []
    for (start, end), spans in sorted(groups.items()):
        spans.sort()
        first, last = spans[0][0], spans[-1][1]
        before, after = text[start:first].lstrip(), text[last:end].rstrip()
        budget = max(0, limit - (last - first)) // 2
        if len(before) > budget:
            cut = before[-budget:]
            before = "..." + (cut[cut.find(" ") + 1:] if " " in cut else cut)
        if len(after) > budget:
            cut = after[:budget]
            after = (cut[:cut.rfind(" ")] if " " in cut else cut) + "..."
        middle, pos = [], first
        for i, j in spans:
            middle.append(E(text[pos:i]) + f"<mark>{E(text[i:j])}</mark>")
            pos = j
        out.append(E(before) + "".join(middle) + E(after))
    return out


def no_interval_text(entry):
    if entry["defect_kind"] == "copied typo":
        return "None. The note itself prints the impossible unit, so this page states only what the label rewards."
    return "None. The note gives no value this input could be replaced with, so the task has no supported answer."


def trace_rows(task, entry, show_recompute=True):
    rows = [("Note says", f'<span class="quote">{x}</span>', "")
            for x in note_excerpts(task.source_text, handcheck.quotes(entry))]
    for name in entry["field"].split(";"):
        if name in task.fields:
            value, unit = task.fields[name]
            rows.append(("Extracted input", f'<span class="mono">{E(name)} = {E(raw_value(value))} {E(unit or "")}</span>', ""))
    return rows, stored_rows(task, entry, show_recompute)


def stored_rows(task, entry, show_recompute=True, label="Stored answer"):
    rows = []
    low, high = task.accepted_range()
    rows.append((label, f'<span class="mono stored">{E(task.meta["label_text"])}</span>'
                        f'<span class="sub">as stored in the CSV; rewarded from {span(low, high)}</span>', "stored-row"))
    formula = task.formula or task.meta.get("extra_formula")
    if show_recompute and formula:
        rows.append(("Recomputed from the extracted inputs",
                     f'<span class="mono">{num(recompute.recompute(task, formula=formula))}</span>', ""))
    bounds = handcheck.interval(task, entry["note_inputs"])
    if bounds:
        head = "What the note supports"
        if entry.get("interval_assumes"):
            head += f", if {entry['interval_assumes']}"
        values = handcheck.note_values(task, entry["note_inputs"])
        raw = (min(values), max(values))
        text = span(*raw) if raw == bounds else f"{span(*raw)} ({span(*bounds)} with the 5% tolerance)"
        rows.append((head, f'<span class="mono supported">{text}</span>', "supported-row"))
    else:
        rows.append(("What the note supports", f'<span class="sub flush">{no_interval_text(entry)}</span>', ""))
    return rows


def render_trace(rows, caption):
    body = "\n".join(f'<tr class="{cls}"><th scope="row">{E(k)}</th><td>{v}</td></tr>' for k, v, cls in rows)
    return f'<div class="scroll"><table class="trace"><caption>{caption}</caption>\n<tbody>\n{body}\n</tbody></table></div>'


def trace_table(task, entry, caption, show_recompute=True):
    head, tail = trace_rows(task, entry, show_recompute)
    return render_trace(head + tail, caption)


def model_block(task, dataset):
    """Model answers for one row from raw/, or nothing when no call is cached."""
    found = []
    for model in MODELS:
        path = medcalc.raw_path(ROOT, model, "calc", dataset, task.id)
        if path.exists():
            found.append((model, json.loads(path.read_text())))
    if not found:
        return ""
    out = ['<div class="scroll"><table class="data models-table"><caption>Model answers on the original '
           'MedCalc-Bench zero-shot prompt, one call per model</caption>',
           '<thead><tr><th scope="col">Model</th><th scope="col">Answer field, verbatim</th>'
           '<th scope="col" class="num">Parsed</th><th scope="col">Stored label</th></tr></thead><tbody>']
    excerpts = []
    for model, record in found:
        text = str(record["cli"].get("result", ""))
        raw = answers.answer_text(text)
        parsed = answers.parse(text, task.meta["calculator_id"])
        verdict = "rewards it" if task.accepts(parsed) else "scores it wrong"
        out.append(f'<tr><td>{MODEL_NAMES[model]}</td><td class="mono">{E(raw or "(no answer field)")}</td>'
                   f'<td class="num mono">{"" if parsed is None else num(parsed)}</td><td>{verdict}</td></tr>')
        m = re.search(r'step_by_step_thinking"\s*:\s*"(.*?)"\s*,\s*"answer', text, flags=re.S)
        if m:
            step = m.group(1).replace("\\n", " ").replace('\\"', '"')
            excerpts.append((model, step[:420] + ("..." if len(step) > 420 else "")))
    out.append("</tbody></table></div>")
    for model, step in excerpts:
        out.append(f'<blockquote class="model-quote"><p class="who">{MODEL_NAMES[model]}, start of its '
                   f'step_by_step_thinking</p><p class="mono">{E(step)}</p></blockquote>')
    return "\n".join(out)


def headline_rows(table):
    """(measure, split, count, share, ci) for every measured headline number."""
    out = []

    def add(measure, r, with_ci=True):
        if r["k"] == "" or r["n"] == "":
            return
        share = pct(r["value"]) if r["value"] != "" else ""
        ci = f'{pct(r["ci_low"])} to {pct(r["ci_high"])}' if with_ci and r["ci_low"] != "" else ""
        out.append((measure, r["split"], count(r["k"], r["n"]), share, ci))

    for split in ("train", "test"):
        add("Wrong labels given their notes (a floor: only flagged rows were read)", find(table, "1", split), False)
        add("Misread from the note", find(table, "1-extraction", split), False)
        add("Copying a typo the note itself prints", find(table, "1-copied typo", split), False)
    add("Formula recompute mismatches, Verified v1.0.8", find(table, "2", contains="Verified"))
    add("Formula recompute mismatches, v1.2, same rows", find(table, "2", contains="v1.2"))
    for split in ("train", "test"):
        add("Gate precision: confirmed among decided flagged rows", find(table, "4", split))
    add("Confirmed train defects the 100x median outlier screen flags", find(table, "found-G4"))
    add("Confirmed train defects the median screen or the diastolic rule flags", find(table, "found-G4-G3"))
    add("Confirmed train defects those two or a heart-rate or weight range check flags", find(table, "found-screens"))
    add("Confirmed defects whose label the Verified pass rewrote", find(table, "relabeled"))
    add("HOMA-IR training labels inflated 36x by the pmol/L conversion", find(table, "homa-ir"))
    for r in table:
        if r["id"] in ("5", "6", "6-control", "8") and r["k"] != "":
            add(r["metric"][:1].upper() + r["metric"][1:], r)
    return out


def calculator_table(rows):
    pivot = collections.defaultdict(collections.Counter)
    for r in rows:
        pivot[r["calculator"]][r["defect_type"]] += int(r["rows"])
    order = sorted(pivot, key=lambda c: (-sum(pivot[c].values()), short(c)))
    head = "".join(f'<th scope="col" class="num">{E(name)}</th>' for _, name in TYPES)
    body = []
    for c in order:
        cells = "".join(f'<td class="num">{pivot[c][t] or ""}</td>' for t, _ in TYPES)
        body.append(f'<tr><th scope="row">{E(short(c))}</th>{cells}<td class="num strong">{sum(pivot[c].values())}</td></tr>')
    totals = "".join(f'<td class="num">{sum(pivot[c][t] for c in pivot)}</td>' for t, _ in TYPES)
    grand = sum(sum(v.values()) for v in pivot.values())
    return (f'<div class="scroll"><table class="data"><caption>Confirmed defects by calculator and type, '
            f'train and test together, n = {grand}. The first {len(TYPES) - 1} columns are extraction defects.</caption>'
            f'<thead><tr><th scope="col">Calculator</th>{head}<th scope="col" class="num">Total</th></tr></thead>'
            f'<tbody>{"".join(body)}</tbody><tfoot><tr><th scope="row">All calculators</th>{totals}'
            f'<td class="num strong">{grand}</td></tr></tfoot></table></div>'), pivot, order


def checks_table(rows):
    what = {"G1": "Recompute the label from the extracted inputs",
            "G2": "Every numeric input appears in the note",
            "G3": "Diastolic at most systolic, MAP between them",
            "G4": "Label or input within 100x of the field's median"}
    body = []
    for r in (r for r in rows if r["split"] == "train"):
        prec = "" if int(r["decided"]) < 10 else f'{pct(r["precision"])} ({pct(r["ci_low"])} to {pct(r["ci_high"])})'
        body.append(f'<tr><th scope="row">{r["check"]}</th><td>{what[r["check"]]}</td><td class="num">{r["flagged"]}</td>'
                    f'<td class="num">{count(r["defects"], r["decided"]) if r["decided"] != "0" else ""}</td>'
                    f'<td class="num">{prec}</td><td class="num">{r["false_flags"]}</td>'
                    f'<td class="num">{r["defects_only_this_check"]}</td></tr>')
    return ('<div class="scroll"><table class="data"><caption>The four checks on Verified train. A row can be flagged by '
            'more than one check. Unclear rows are left out of the decided count.</caption><thead><tr>'
            '<th scope="col">Check</th><th scope="col">What it tests</th><th scope="col" class="num">Rows flagged</th>'
            '<th scope="col" class="num">Defects among decided</th><th scope="col" class="num">Precision, 95% CI</th>'
            '<th scope="col" class="num">False flags</th><th scope="col" class="num">Defects only it flags</th>'
            f'</tr></thead><tbody>{"".join(body)}</tbody></table></div>')


def all_defects_table(entries, tasks):
    defects = [e for e in entries if e["decision"] == "defect"]
    defects.sort(key=lambda e: (e["dataset"] != "ver_train", e["defect_kind"], e["defect_type"], int(e["row"])))
    body = []
    for e in defects:
        task = tasks[(e["dataset"], e["row"])]
        quote = " / ".join(E(q) for q in handcheck.quotes(e))
        split = "train" if e["dataset"] == "ver_train" else "test"
        body.append(f'<tr><td class="num mono">{E(e["row"])}</td><td>{split}</td><td>{E(short(e["calculator"]))}</td>'
                    f'<td>{E(e["defect_type"])}</td><td><span class="quote"><mark>{quote}</mark></span></td>'
                    f'<td class="mono">{E(e["input_value"])}</td>'
                    f'<td class="num mono stored">{E(task.meta["label_text"])}</td></tr>')
    return len(defects), (f'<div class="scroll"><table class="data long"><caption>Every confirmed row, n = {len(defects)}. '
                          f'Quotes are literal substrings of the row\'s Patient Note. Labels are as stored.</caption><thead><tr>'
                          f'<th scope="col" class="num">Row</th><th scope="col">Split</th><th scope="col">Calculator</th>'
                          f'<th scope="col">Type</th><th scope="col">Note says</th><th scope="col">Stored input</th>'
                          f'<th scope="col" class="num">Stored label</th></tr></thead><tbody>{"".join(body)}</tbody></table></div>')


def relabeled_table(rows, entries):
    by_row = {(e["dataset"], e["row"]): e for e in entries}
    body = []
    for r in rows:
        e = by_row[(r["dataset"], r["row"])]
        quote = " / ".join(E(q) for q in handcheck.quotes(e))
        body.append(f'<tr><td class="num mono">{E(r["row"])}</td><td>{E(short(r["calculator"]))}</td>'
                    f'<td><span class="quote"><mark>{quote}</mark></span></td>'
                    f'<td class="num mono stored">{E(r["v12_label"])}</td><td class="num mono stored">{E(r["verified_label"])}</td>'
                    f'<td>{E(r["precision_change"].replace("intermediate re-rounded: ", "intermediate value re-rounded, "))}</td></tr>')
    return ('<div class="scroll"><table class="data"><caption>Confirmed defects whose stored label differs between v1.2 and '
            'Verified, joined on Calculator ID plus Note ID. Labels are as stored in each CSV.</caption><thead><tr>'
            '<th scope="col" class="num">Row</th><th scope="col">Calculator</th><th scope="col">Note says</th>'
            '<th scope="col" class="num">v1.2 label</th><th scope="col" class="num">Verified label</th>'
            f'<th scope="col">Change</th></tr></thead><tbody>{"".join(body)}</tbody></table></div>')


def article(number_text):
    return "an" if number_text.startswith("8") or number_text in ("11", "18") else "a"


def join(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


CSS = """
/* Layout: one 70ch reading column for prose; tables run to 960px inside the same left edge. */
:root {
  --paper: #ffffff;
  --ink: #16181d;
  --ink-2: #4b515b;
  --rule: #d5d8dd;
  --rule-strong: #9aa1ab;
  --stored: #b3261e;
  --supported: #1f5fa8;
  --mark: #fff0a0;
  --sans: "IBM Plex Sans", "Helvetica Neue", Arial, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  --s1: 4px; --s2: 8px; --s3: 12px; --s4: 16px; --s6: 24px; --s8: 32px; --s12: 48px;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --paper: #1b1e24; --ink: #e3e6ea; --ink-2: #a8afb9; --rule: #3a404b; --rule-strong: #626b77;
    --stored: #f08a80; --supported: #8ab6ee; --mark: #4a4210; color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --paper: #1b1e24; --ink: #e3e6ea; --ink-2: #a8afb9; --rule: #3a404b; --rule-strong: #626b77;
  --stored: #f08a80; --supported: #8ab6ee; --mark: #4a4210; color-scheme: dark;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; overflow-x: clip; }
body {
  margin: 0; background: var(--paper); color: var(--ink); overflow-x: clip;
  font-family: var(--sans); font-size: 16px; line-height: 1.6;
  padding-inline: var(--s4); padding-block: var(--s8) var(--s12);
}
main { max-width: 960px; margin-inline: auto; }
p, ul, ol, h1, h2, h3, blockquote, pre { max-width: 70ch; }
h1, h2, h3 { line-height: 1.25; text-wrap: balance; font-weight: 600; }
h1 { font-size: 1.75rem; margin: 0 0 var(--s2); letter-spacing: -0.01em; overflow-wrap: anywhere; }
h2 { font-size: 1.25rem; margin: var(--s12) 0 var(--s3); padding-top: var(--s4); border-top: 1px solid var(--rule); }
h3 { font-size: 1.0625rem; margin: var(--s8) 0 var(--s2); }
p { margin: 0 0 var(--s4); }
ul, ol { margin: 0 0 var(--s4); padding-left: var(--s6); }
li { margin-bottom: var(--s1); }
a { color: inherit; text-decoration: underline; text-decoration-color: var(--rule-strong); text-underline-offset: 2px; }
a:hover { text-decoration-color: var(--ink); }
a:focus-visible { outline: 2px solid var(--supported); outline-offset: 2px; }
.byline { color: var(--ink-2); margin-bottom: var(--s4); }
.draft { border: 1px solid var(--rule-strong); border-radius: 2px; padding: var(--s2) var(--s3); font-size: 0.9375rem; }
.lede { font-size: 1.0625rem; }
.mono, code, pre { font-family: var(--mono); font-variant-numeric: tabular-nums; }
code { font-size: 0.9em; }
pre { font-size: 0.875rem; line-height: 1.5; border: 1px solid var(--rule); border-radius: 2px; padding: var(--s3) var(--s4); overflow-x: auto; }
mark { background: var(--mark); color: inherit; padding: 0 var(--s1); border-radius: 2px; }
.quote { font-family: var(--mono); font-size: 0.875rem; }
.stored { color: var(--stored); font-weight: 500; }
.supported { color: var(--supported); font-weight: 500; }
.sub { display: block; font-size: 0.8125rem; color: var(--ink-2); font-family: var(--sans); }
.sub.flush { font-size: 0.875rem; }
.scroll { overflow-x: auto; margin: 0 0 var(--s6); }
table { border-collapse: collapse; font-variant-numeric: tabular-nums; }
caption { caption-side: top; text-align: left; font-size: 0.8125rem; color: var(--ink-2); padding-bottom: var(--s2); }
th, td { text-align: left; vertical-align: top; padding: var(--s2) var(--s3) var(--s2) 0; border-bottom: 1px solid var(--rule); }
thead th { font-size: 0.8125rem; font-weight: 600; border-bottom: 1px solid var(--rule-strong); }
tfoot th, tfoot td { border-top: 1px solid var(--rule-strong); border-bottom: 0; font-weight: 600; }
.num { text-align: right; white-space: nowrap; }
.strong { font-weight: 600; }
table.data { width: 100%; font-size: 0.875rem; }
table.data.long td { min-width: 6ch; }
table.data.long td:nth-child(5) { min-width: 28ch; }
table.trace { width: 100%; max-width: 860px; }
table.trace th { width: 12ch; min-width: 12ch; font-weight: 500; font-size: 0.875rem; color: var(--ink-2); }
table.trace td { font-size: 0.9375rem; }
table.trace tr:first-child th, table.trace tr:first-child td { border-top: 1px solid var(--rule-strong); }
.model-quote { margin: 0 0 var(--s4); padding: var(--s2) var(--s4); border: 1px solid var(--rule); border-radius: 2px; }
.model-quote .who { font-size: 0.8125rem; color: var(--ink-2); margin-bottom: var(--s1); }
.model-quote .mono { font-size: 0.8125rem; margin: 0; }
.key { font-size: 0.875rem; color: var(--ink-2); }
details { margin: 0 0 var(--s6); }
summary { cursor: pointer; font-weight: 600; margin-bottom: var(--s3); }
summary:focus-visible { outline: 2px solid var(--supported); outline-offset: 2px; }
footer { margin-top: var(--s12); padding-top: var(--s4); border-top: 1px solid var(--rule); font-size: 0.8125rem; color: var(--ink-2); }
@media (max-width: 600px) {
  h1 { font-size: 1.4rem; }
  table.trace, table.trace tbody, table.trace tr, table.trace th, table.trace td { display: block; width: 100%; }
  table.trace caption { display: block; width: 100%; }
  table.trace th { border-bottom: 0; padding-bottom: 0; min-width: 0; }
  table.trace td { padding-top: var(--s1); }
  table.trace tr:first-child td { border-top: 0; }
}
"""


def build():
    table = read_csv("results_table.csv")
    checks = read_csv("checks.csv")
    detection = read_csv("detection.csv")
    relabeled = [r for r in read_csv("verified_relabeled.csv") if r["label_changed"] == "1"]
    g2_formats = read_csv("g2_formats.csv")
    summary = json.loads((RESULTS / "gate_summary.json").read_text())
    entries = handcheck.load(RESULTS / "handcheck.csv")
    samples = json.loads((RESULTS / "samples.json").read_text())
    log = read_csv("call_log.csv") if (RESULTS / "call_log.csv").exists() else []
    tasks = medcalc.load_splits(ROOT / "data")
    by_row = {(e["dataset"], e["row"]): e for e in entries}

    tr, te = summary["ver_train"]["counts"], summary["ver_test"]["counts"]
    changes = summary["label_changes"]
    train_rows, test_rows = tr["rows"], te["rows"]

    t1, t1x, t1t = find(table, "1", "train"), find(table, "1-extraction", "train"), find(table, "1-copied typo", "train")
    t1g = find(table, "1-g1", "train")
    s1 = find(table, "1", "test")
    g1v, g1o = find(table, "2", contains="Verified"), find(table, "2", contains="v1.2")
    prec, prec_test = find(table, "4", "train"), find(table, "4", "test")
    found_g4, found_label = find(table, "found-G4"), find(table, "found-G4-label")
    found_g4g3, found_screens, found_30x = find(table, "found-G4-G3"), find(table, "found-screens"), find(table, "found-G4-30x")
    screen_row = find(table, "range-screen")
    homa, homa_new = find(table, "homa-ir"), find(table, "homa-ir-new")
    homa_rows = [r for r in read_csv("homa_ir.csv") if r["dataset"] == "ver_train"]
    screen = [r for r in read_csv("range_screen.csv") if r["dataset"] == "ver_train"]
    check = {r["check"]: r for r in checks if r["split"] == "train"}
    r7 = find(table, "7")

    k1, kx, kt = int(t1["k"]), int(t1x["k"]), int(t1t["k"])
    v12_bad = [f for f, c in summary["v12_train"]["g1_by_formula"].items() if c.get("mismatch")]
    v12_bad_names = join([FORMULA_NAMES.get(f, f) for f in v12_bad])

    train_entries = [e for e in entries if e["dataset"] == "ver_train"]
    reviewed = [e for e in entries if e["decision"] in ("defect", "unclear")]
    unconfirmed = sum(not handcheck.confirmed_by_dev(e) for e in reviewed)
    first_pass_only = len(entries) - len(reviewed)
    not_defect = [e for e in train_entries if e["decision"] == "not a defect"]
    g2_false = [e for e in not_defect if any(c.startswith("G2:") for c in e["checks"].split(";"))]
    fmt_flags = [e for e in g2_false if e["reason"].startswith("number format")]
    wrong_no_change = sum(e["input_wrong"] == "yes" for e in not_defect)
    unclear_rows = [e["row"] for e in train_entries if e["decision"] == "unclear"]
    train_detect = [d for d in detection if d["dataset"] == "ver_train"]
    by_g3 = [d["row"] for d in train_detect if d["g4"] == "0" and d["g3"] == "1"]
    by_range = [d["row"] for d in train_detect if d["g4"] == "0" and d["g3"] == "0" and d["range_check"] == "1"]
    by_none = [d for d in train_detect if d["g4_g3_or_range"] == "0"]

    def first_quote(word):
        for e in fmt_flags:
            if word in e["reason"]:
                return e["quote"].replace("\n", " ")
        raise KeyError(word)

    q_comma, q_space, q_sci = first_quote("decimal comma"), first_quote("thousands separator"), first_quote("scientific")

    def judged(word):
        return [e["row"] for e in train_entries if e["decision"] in ("defect", "unclear") and word in e["reason"]]

    with_interval = [e for e in entries if e["decision"] == "defect" and e["defect_kind"] == "extraction" and e["note_inputs"]]
    attempted = sum(1 for r in log if r["status"] != "cached")
    completed = sum(1 for r in log if r["status"] == "ok")
    planned = len(samples["phase1"]) + 3 * len(samples["defects"]) + 2 * len(samples["control"])
    models_run = completed > 0

    t1337, e1337 = tasks[("ver_train", "1337")], by_row[("ver_train", "1337")]
    lo1337, hi1337 = t1337.accepted_range()
    vals1337 = handcheck.note_values(t1337, e1337["note_inputs"])
    b1337 = handcheck.interval(t1337, e1337["note_inputs"])
    sbp, dbp = t1337.fields["sbp"][0], t1337.fields["dbp"][0]

    built = datetime.date.today().isoformat()
    parts = []
    w = parts.append

    w('<title>MedCalc Label Gate</title>')
    w(f'<meta name="description" content="At least {k1} training labels in MedCalc-Bench Verified that pass a formula '
      f're-check but are wrong given the patient note they were extracted from.">')
    w('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>')
    w('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&'
      'family=IBM+Plex+Sans:wght@400;500;600&display=swap">')
    w(f"<style>{CSS}</style>")
    w("<main>")
    w("<header>")
    w(f"<h1>At least {k1} wrong training labels in MedCalc-Bench Verified that pass a formula re-check</h1>")
    w('<p class="byline">Dev Lakhani</p>')
    if unconfirmed:
        w(f'<p class="draft"><strong>Draft.</strong> Each flagged row ({len(entries)} in all) has a first-pass call and '
          f'reason; Dev has not yet confirmed {unconfirmed} of the {len(reviewed)} defect and unclear calls. Each call is a '
          f'quoted note span in results/handcheck.csv that anyone can redo.</p>')
    w("</header>")

    t2807 = tasks[("ver_train", "2807")]
    w(f'<p class="lede">Re-running the formula on {int(g1v["n"]):,} Verified training rows finds {g1v["k"]} mismatches, '
      f'against {g1o["k"]} on the same rows of v1.2. Reading the flagged rows against the notes they came from finds at '
      f'least {count(t1["k"], t1["n"])} training labels wrong given their notes: {kx} misread from the note, {kt} copying '
      f'a typo the note itself prints. Row 2807\'s note says <span class="quote">pulse 40-50 bpm</span>, and its label '
      f'scores a heart rate of {num(t2807.fields["heart_rate"][0])}. {t1g["k"]} of the {k1} sit in calculators the '
      f'recompute covers, and it passes every one. Only the {tr["rows_flagged"]} flagged training rows were read, so '
      f'{k1} is a floor, not an error rate. Separately, a known unit-conversion bug in the HOMA-IR calculator still makes '
      f'{homa["k"]} of its {homa["n"]} training labels 36 times too large.</p>')

    w(trace_table(t1337, e1337, f"Row Number 1337, {E(short(t1337.meta['calculator']))}, Verified train. The highlighted "
                  f"words are the note's own text.", show_recompute=False))
    w('<p class="key">Red is a stored label. Blue is a value the note supports. Yellow is quoted note text.</p>')
    w(f'<p>MAP is SBP / 3 + 2 &times; DBP / 3. The stored inputs give {raw_value(sbp)} / 3 + 2 &times; {raw_value(dbp)} / 3 '
      f'= {num(recompute.recompute(t1337))}, which is the stored label, so a formula re-check passes it. The note gives two '
      f'ranges, the one during the seizure and the patient\'s baseline, and both come before the blood-pressure treatment. Over every pair '
      f'of their endpoints, MAP runs from {span(min(vals1337), max(vals1337))} mmHg, or {span(*b1337)} after the '
      f'dataset\'s 5% tolerance. A model that reads the note and answers anywhere in that interval gets zero reward, '
      f'because the label only rewards {span(lo1337, hi1337)}. No model has been run on this row yet, so that is '
      f'arithmetic on the stored limits, not an observed answer.</p>')

    rerounded = [r for r in relabeled if r["precision_change"] == "label re-rounded"]
    intermediate = [r for r in relabeled if r["precision_change"].startswith("intermediate re-rounded")]
    other_change = [r for r in relabeled if r not in rerounded and r not in intermediate]
    w('<h2 id="relabeled">The Verified pass rewrote some of these labels</h2>')
    same_inputs = all(r["same_inputs"] == "1" for r in relabeled)
    lines = [f'<p>The Verified release changed the stored label on {len(relabeled)} of the confirmed rows'
             + (", with the extracted inputs unchanged" if same_inputs else "")
             + f'. Every new label is still impossible. {len(rerounded)} were re-rounded to more or fewer digits.']
    for r in intermediate:
        e, t = by_row[(r["dataset"], r["row"])], tasks[(r["dataset"], r["row"])]
        old, new = r["precision_change"].split(": ", 1)[1].split(" to ")
        lo, hi = t.accepted_range()
        lines.append(f' Row {r["row"]} ({E(short(r["calculator"]))}) moved from {num(r["v12_label"])} to '
                     f'{num(r["verified_label"])} because of rounding one step earlier: the v1.2 explanation rounded the '
                     f'converted input to {old}, and Verified kept {new}. The note prints <span class="quote">'
                     f'{E(handcheck.quotes(e)[0])}</span>, and the old label sits inside the new one\'s accepted range '
                     f'({span(lo, hi)}).')
    for r in other_change:
        lines.append(f' Row {r["row"]} ({E(short(r["calculator"]))}) changed from {num(r["v12_label"])} to '
                     f'{num(r["verified_label"])}.')
    if not other_change:
        lines.append(f' So all {len(relabeled)} are precision changes.')
    lines.append(' None of them touched the impossible input.</p>')
    w("".join(lines))
    w(relabeled_table(relabeled, entries))

    w('<h2 id="homa-ir">A conversion bug in the HOMA-IR calculator</h2>')
    other_homa = [t.label for (d, _r), t in tasks.items()
                  if d == "ver_train" and t.meta["calculator_id"] == 31 and t.fields["Insulin"][1] != "pmol/L"]
    pmol = sorted(float(r["stored_label"]) for r in homa_rows)
    example = next(r for r in homa_rows if r["in_confirmed_defects"] == "0")
    big = max(homa_rows, key=lambda r: float(r["stored_label"]))
    w(f'<p>{count(homa["k"], homa["n"])} HOMA-IR training rows give insulin in pmol/L. The explanation converts it to '
      f'&micro;IU/mL by multiplying by 6, as in row {big["row"]}: <span class="quote">756.0 * 6 &micro;IU/mL/pmol/L = '
      f'4536.0 &micro;IU/mL</span>. About 6 pmol/L make 1 &micro;IU/mL, so the conversion should divide, and every one '
      f'of these labels is 36 times too large. They run from {num(pmol[0])} to {num(pmol[-2])}, and {num(pmol[-1])} for '
      f'row {big["row"]}, while the HOMA-IR rows in other units top out at {num(max(other_homa))}. Row {example["row"]} '
      f'has insulin {raw_value(float(example["insulin_pmol_l"]))} pmol/L and a stored label of {num(example["stored_label"])}; '
      f'divided instead of multiplied, the same inputs give {num(example["corrected_label"])}.</p>')
    w(f'<p><a href="https://arxiv.org/abs/2603.02222">arXiv 2603.02222</a> lists this bug, and '
      f'<a href="https://github.com/nikhilk7153/MedCalc-Bench-Verified/pull/5">PR #5</a> (artuskg) proposed the one-line '
      f'fix in February 2026. It was closed without merging, so {count(homa["k"], homa["n"])} training labels in {RELEASE} '
      f'still carry it.</p>')
    w(f'<p>This is a separate count from the {k1}: {homa_new["k"]} of the {homa_new["n"]} rows are outside it. The '
      f'gate does not catch these rows, because the formula is applied consistently to inputs that match the note, '
      f'and a recompute that runs the same calculator code agrees with the label. The fix belongs in one line of the '
      f'calculator, not in {homa["k"]} separate relabels. Every row is listed in results/homa_ir.csv, and '
      f'results/fix_list.csv marks them "fix the calculator".</p>')

    w('<h2 id="numbers">Headline numbers</h2>')
    w('<p>Counts sit next to every share. Intervals are Wilson 95%. Gate precision leaves out rows marked unclear.</p>')
    rows_html = [f'<tr><td>{E(m)}</td><td>{E(s)}</td><td class="num">{E(c)}</td><td class="num">{E(sh)}</td>'
                 f'<td class="num">{E(ci)}</td></tr>' for m, s, c, sh, ci in headline_rows(table)]
    w(f'<div class="scroll"><table class="data"><caption>Verified train n = {train_rows:,}, test n = {test_rows:,}. '
      f'Source: results/results_table.csv.</caption><thead><tr><th scope="col">Measure</th><th scope="col">Split</th>'
      f'<th scope="col" class="num">Count</th><th scope="col" class="num">Share</th><th scope="col" class="num">95% CI</th>'
      f'</tr></thead><tbody>{"".join(rows_html)}</tbody></table></div>')
    if not models_run:
        w(f'<p>Two things are not measured yet, because both need model calls and none has completed: how many defects '
          f'the checks miss among unflagged rows, and how three models of different sizes answer the defect rows ({planned} calls '
          f'planned, {attempted} attempted).</p>')

    def range_hit(row):
        r = next(r for r in screen if r["row"] == row)
        unit = {"lbs": "lb", "beats per minute": "bpm"}.get(r["unit"], r["unit"])
        return f'{row} ({r["field"].replace("_", " ")} {num(r["value"])} {unit})'

    range_text = join([range_hit(r) for r in by_range])
    screen_other = [r for r in screen if r["decision"] != "defect"]
    w('<h2 id="finding">What finds them</h2>')
    w(f'<p>Cheap screens find almost all of these rows. A screen that flags any label or input more than 100 times away '
      f'from the median of its field (G4 below) catches {found_g4["k"]} of the {found_g4["n"]} train defects, and the '
      f'label alone is that far out in {found_label["k"]}. G3, the rule that diastolic pressure cannot exceed systolic, '
      f'adds row {join(by_g3)} for {found_g4g3["k"]}. Two plain range checks, heart rate from 15 to 300 bpm and weight up to '
      f'400 kg, add {range_text} for {found_screens["k"]}. Those range checks flag {screen_row["n"]} train rows in all; the '
      f'others are {join([r["row"] for r in screen_other])}. Their bounds were picked after the defects were known, so '
      f'this shows how cheap the rows are to find, and it is not a held-out test of a screen. The last row, '
      f'{join([d["row"] for d in by_none])}, is caught by G2 because its stored insulin is not in the note. G4 at 30x instead '
      f'of 100x would also catch it, and on its own would find {found_30x["k"]} of the {found_30x["n"]}, but that '
      f'threshold was also chosen after seeing the defects.</p>')
    w(f'<p>What reading the note adds is the cause and the answer the note supports. Row 2807 asks for a Wells score. '
      f'Its note says <span class="quote">pulse 40-50 bpm</span>, the stored heart rate is '
      f'{raw_value(t2807.fields["heart_rate"][0])}, and the stored label of {t2807.meta["label_text"]} is exactly the '
      f'1.5 points the heart-rate criterion gives for a rate over 100. Read as 40-50, that criterion scores 0, not 1.5, so a model that reads the note '
      f'correctly does not match the key. That reading is what decides what to do with a flagged row: '
      f'relabel it when the note gives an answer (2807, or 1337 with an interval label), drop it when the note itself '
      f'is wrong (the copied typos), and fix the calculator when one bug produced many rows (HOMA-IR above).</p>')

    calc_rows = read_csv("defects_by_calculator.csv")
    calc_html, pivot, order = calculator_table(calc_rows)
    w('<h2 id="calculators">Where the defects are</h2>')
    third = sum(pivot[order[2]].values())
    top = [f"{short(c)} ({sum(pivot[c].values())})" for c in order if sum(pivot[c].values()) >= third]
    w(f'<p>Most of the copied typos sit in kidney and electrolyte formulas, where the note prints a unit such as mmol/dl '
      f'for sodium or creatinine. The extraction defects are spread wider: platelet counts printed per 10<sup>9</sup>/L '
      f'stored a thousand times too small, heart-rate and weight ranges joined into one number, resected masses read as '
      f'the patient\'s weight, and cerebrospinal fluid cell counts read as blood white cell counts. The largest groups are '
      f'{join(top)}.</p>')
    w(calc_html)

    w('<h2 id="checks">The four checks</h2>')
    w(f'<p>Each check flags rows to read. A flag becomes a defect only after the note span that contradicts the input is '
      f'quoted. Together the checks flagged {count(tr["rows_flagged"], train_rows)} train rows and '
      f'{count(te["rows_flagged"], test_rows)} test rows. Across all four, {count(prec["k"], prec["n"])} decided flagged '
      f'train rows are wrong labels ({pct(prec["value"])}), which is the false-flag load a reviewer would face; test is '
      f'{count(prec_test["k"], prec_test["n"])}.</p>')
    w(checks_table(checks))
    w(f'<p>G1 is coded from the formula each row\'s own Ground Truth Explanation states, for 15 renal, electrolyte and '
      f'blood-pressure formulas. It agrees with every stored label on the {int(g1v["n"]):,} rows it covers (upper 95% bound '
      f'{pct(g1v["ci_high"])}). On the same rows of v1.2, {g1o["k"]} differ, all in {E(v12_bad_names)}. That matches '
      f'<a href="https://github.com/nikhilk7153/MedCalc-Bench-Verified/pull/7">PR #7</a> (open) on the Verified repo, which '
      f're-ran the calculators on both splits and reported 0 train mismatches. The maintainer\'s '
      f'<a href="https://github.com/nikhilk7153/MedCalc-Bench-Verified/releases/tag/v1.0.8">{RELEASE} release notes</a> '
      f'(2026-09-08) report 0 audit mismatches across all 11,693 rows, and commits '
      f'<a href="https://github.com/nikhilk7153/MedCalc-Bench-Verified/commit/3df69cf">3df69cf</a> and '
      f'<a href="https://github.com/nikhilk7153/MedCalc-Bench-Verified/commit/192a585">192a585</a> fixed notes that '
      f'contradicted their own entities: 8 sodium rows and the fentanyl units. So note-against-entity checks are already '
      f'part of upkeep. G1 is here to show the formulas are right, so the '
      f'remaining errors sit in the inputs.</p>')
    g2 = check["G2"]
    w(f'<p>G2 accepts a number that matches a note number times a power of ten from 10<sup>-3</sup> to 10<sup>3</sup>, to '
      f'allow unit rescaling, and reports an input whose digits equal two note numbers joined across a hyphen as a merged '
      f'range. Its precision is poor: {count(g2["defects"], g2["decided"])} ({pct(g2["precision"])}). Of its '
      f'{g2["false_flags"]} train false flags, {len(fmt_flags)} are number formats the reader does not parse, such as the '
      f'decimal comma in <span class="quote">{E(q_comma)}</span>, the space in <span class="quote">{E(q_space)}</span> '
      f'and the lost superscript in <span class="quote">{E(q_sci)}</span>.</p>')

    def g2p(part, reader):
        return find([r for r in table if r["id"] == "g2-formats"], "g2-formats", part, reader)

    dev_o, dev_n = g2p("dev", "original"), g2p("dev", "format-aware")
    ho_o, ho_n = g2p("held-out", "original"), g2p("held-out", "format-aware")
    ts_o, ts_n = g2p("test", "original"), g2p("test", "format-aware")
    lost = [r for r in g2_formats if r["decision"] == "defect" and r["still_flagged"] == "0"]
    lost_g4 = sum(any(d["row"] == r["row"] and d["g4"] == "1" for d in detection) for r in lost)
    w(f'<p>A format-aware reader, written after reading only a seeded random half of the G2-flagged train rows, handles '
      f'decimal commas, spaces as thousands separators, a space after the decimal point, and a power of ten written '
      f'without its superscript. On the other half, precision goes from {count(ho_o["k"], ho_o["n"])} to '
      f'{count(ho_n["k"], ho_n["n"])} ({pct(ho_n["value"])}, 95% CI {pct(ho_n["ci_low"])} to {pct(ho_n["ci_high"])}) and '
      f'no defect is lost. On test it goes from {count(ts_o["k"], ts_o["n"])} to {count(ts_n["k"], ts_n["n"])}. On the '
      f'half it was written on, it goes from {count(dev_o["k"], dev_o["n"])} to {count(dev_n["k"], dev_n["n"])}, and it '
      f'drops {len(lost)} real defects: {join([r["row"] for r in lost])}, platelet counts stored a thousand times too '
      f'small. The old reader only caught those because it could not read "&times;109"; once it can, the 10<sup>-3</sup> '
      f'rescaling allowance accepts the wrong value. G4 still flags {lost_g4} of the {len(lost)}. The format list was '
      f'already known from the first pass over all rows, so the held-out half is held out for the exact rules, not for '
      f'which formats exist. Every other number on this page uses the original reader.</p>')
    g3 = check["G3"]
    w(f'<p>G3 follows from definitions and needs no clinical bounds. It flagged {g3["flagged"]} train rows and is the only '
      f'check that fires on row 1545 below. G4 is a fixed 100x screen against the median of the same field in the same '
      f'file, set before any flagged row was read. It finds the copied typos and needs a file large enough for the median '
      f'to mean something.</p>')
    w(f'<p>{len(unclear_rows)} train rows were marked unclear and are left out of every count: {join(unclear_rows)}. '
      f'Most give no unit or never state the input. {wrong_no_change} train rows have a wrong input that does not change '
      f'the label; they count as not a defect.</p>')
    if set(SECOND_CHECK_UNCLEAR) <= set(unclear_rows):
        w(f'<p>On a second check, {len(SECOND_CHECK_UNCLEAR)} of the unclear rows ({join(SECOND_CHECK_UNCLEAR)}) look like '
          f'the same patterns as counted rows, so {k1} is a floor.</p>')

    w('<h2 id="examples">Worked examples</h2>')
    w('<p>Each example shows the note sentence, the extracted input, the stored label, the recompute from the extracted '
      'input, and what the note supports, so the arithmetic can be redone by hand. Quotes are literal substrings of the '
      'row\'s Patient Note, and tests/test_handcheck.py checks that.</p>')

    t1545, e1545 = tasks[("ver_train", "1545")], by_row[("ver_train", "1545")]
    w("<h3>Row 1545: systolic and diastolic from different readings</h3>")
    w(f'<p>The systolic input of {raw_value(t1545.fields["sbp"][0])} comes from a sentence about a drop in pressure, and the '
      f'diastolic of {raw_value(t1545.fields["dbp"][0])} from a later reading. The stored MAP of {num(t1545.label)} sits '
      f'below its own diastolic input, which no MAP can do, and G3 caught it. The only pair the note states together was '
      f'taken after ECMO cannulation on epinephrine and norepinephrine, and the question asks for values from admission '
      f'before any treatment. So the note supports no answer: the task cannot be computed, and the label is a number for a '
      f'question with none.</p>')
    w(trace_table(t1545, e1545, f"Row Number 1545, {E(short(t1545.meta['calculator']))}, Verified train."))
    w(model_block(t1545, "ver_train"))

    t2685, e2685 = tasks[("ver_train", "2685")], by_row[("ver_train", "2685")]
    w("<h3>Row 2685: a calcium range read as one value</h3>")
    w(f'<p>The note gives calcium as a range, and the extracted input is a single value with the digits run together, '
      f'{raw_value(t2685.fields["calcium"][0])} {E(t2685.fields["calcium"][1])}. The unit the note prints, g/L, would give '
      f'a corrected calcium near 200 mg/dL, which no patient has. The note\'s own reference range is the usual mmol/L '
      f'range, so the blue interval assumes mmol/L. That is an assumption about a second typo in the source, and it is '
      f'labeled as one.</p>')
    w(trace_table(t2685, e2685, f"Row Number 2685, {E(short(t2685.meta['calculator']))}, Verified train."))
    w(model_block(t2685, "ver_train"))

    trio = ["6171", "8473", "8678"]
    ttrio = [tasks[("ver_train", r)] for r in trio]
    w("<h3>Rows 6171, 8473 and 8678: one note typo, three wrong labels</h3>")
    w(f'<p>One note prints sodium in mmol/dl. The pipeline copied the unit as written, and the three calculators built on '
      f'that note got labels of {join([num(t.label) for t in ttrio])}. The note is wrong here, so this page gives no '
      f'corrected answer and states only what each label rewards.</p>')
    head, _ = trace_rows(ttrio[0], by_row[("ver_train", trio[0])])
    stored = []
    for t, r in zip(ttrio, trio):
        stored += stored_rows(t, by_row[("ver_train", r)], show_recompute=False,
                              label=f"Row {r}, {short(t.meta['calculator'])}")[:1]
    stored.append(("What the note supports", f'<span class="sub flush">{no_interval_text(by_row[("ver_train", trio[0])])}</span>', ""))
    w(render_trace(head + stored, "Rows 6171, 8473 and 8678, Verified train, all built on the same note and input."))
    for t in ttrio:
        w(model_block(t, "ver_train"))

    t267, e267 = tasks[("ver_train", "267")], by_row[("ver_train", "267")]
    w("<h3>Row 267: an impossible creatinine unit copied from the note</h3>")
    w(f'<p>The note prints creatinine in mmol/dl, the extraction copied it, and the stored GFR is {num(t267.label)} '
      f'mL/min/1.73 m&sup2;. Both the input and the label sit more than 100 times away from their medians in the file, '
      f'which is what G4 measures. No interval, for the same reason as the sodium rows.</p>')
    w(trace_table(t267, e267, f"Row Number 267, {E(short(t267.meta['calculator']))}, Verified train."))
    w(model_block(t267, "ver_train"))

    n_all, all_html = all_defects_table(entries, tasks)
    w('<h2 id="all-rows">All confirmed rows</h2>')
    w('<p>The full list, so any row can be checked against the dataset. It matches results/handcheck.csv and the draft '
      'issue in upstream/ISSUE.md.</p>')
    w(f'<details><summary>Show all {n_all} rows ({k1} train, {s1["k"]} test)</summary>{all_html}</details>')

    lc = changes["train"]
    w('<h2 id="method">Method</h2>')
    w(f'<p>The four CSVs (Verified and v1.2, train and test) are downloaded from pinned Hugging Face commits and checked '
      f'against sha256 before anything runs. Joined on Calculator ID plus Note ID, {count(lc["label_changed"], lc["matched"])} '
      f'train labels differ between v1.2 and Verified by more than 1e-6. Of those, '
      f'{lc["label_changed"] - lc["changed_rel_1e-4"]} differ by less than 0.01%, which is re-rounding; '
      f'{lc["changed_rel_0.1pct"]:,} differ by more than 0.1%, and {lc["changed_rel_5pct"]:,} by more than the '
      f'dataset\'s 5% tolerance. On test, {changes["test"]["label_changed"]} of {changes["test"]["matched"]:,} differ, '
      f'{changes["test"]["changed_rel_5pct"]} of them by more than 5%.</p>')
    csf, ecmo = judged("cerebrospinal"), judged("ECMO")
    review_sentence = (f'Each flagged row has a first-pass call and reason. Dev has not yet confirmed {unconfirmed} of the '
                       f'{len(reviewed)} defect and unclear calls.' if unconfirmed else
                       f'Each flagged row has a first-pass call and reason. Dev then read every defect and unclear row '
                       f'({len(reviewed)} in all) against its note on 2026-10-18 and agreed with each call. The '
                       f'{first_pass_only} rows called not a defect keep their first-pass call.')
    weights = judged("resected") + judged("surgical specimen")
    w(f'<p>Every flagged row has a line in results/handcheck.csv with the checks that fired, the quoted note span, the '
      f'stored input and label, a decision, a defect type from a fixed list, and the note inputs where they can be '
      f'computed. A row is a defect when the input contradicts the note, or the note prints an impossible unit that was '
      f'copied, and correcting the input changes the label or leaves the task with no answer. A copied typo is called only '
      f'where the note prints the unit literally and G4 fired. {review_sentence} Most calls are a quote plus arithmetic. Some are contextual clinical '
      f'reads: whether a cell count came from cerebrospinal fluid or blood ({join(csf)}), whether a pressure on pressors '
      f'counts as pre-treatment ({join(ecmo)}), and whether a weight is the patient\'s or a resected mass\'s '
      f'({join(sorted(weights, key=int))}). None of them was made by a clinician, and a clinician may overrule any of '
      f'them.</p>')
    w(f'<p>For a range in the note, the label is computed over every combination of endpoints and widened by the 5% '
      f'tolerance. For mixed readings, it uses pairs stated together in one reading. For a unit tag that does not match, '
      f'it uses the unit the note prints, unless that unit is itself impossible; for a lost power of ten, it restores '
      f'it; for an input taken after treatment, it uses the pre-treatment value the note gives. Copied typos get no interval. '
      f'{len(with_interval)} extraction rows have one, and a test checks that no stored label falls inside its own interval.</p>')
    w(f'<p>The model step is written and not run. It sends the <code>zero_shot</code> system and user strings from '
      f'MedCalc-Bench\'s <code>evaluation/run.py</code>, verbatim, through the command in scripts/run_models.py with '
      f'tools off, and caches every raw response before parsing: {len(samples["phase1"])} re-extractions of '
      f'unflagged rows by the mid-size model to estimate misses, {len(samples["defects"])} defect rows on each of three '
      f'models of different sizes, and {len(samples["control"])} clean control rows on the two smaller ones. Per 1,000 training rows, {num(r7["value"])} carry '
      f'an extraction defect ({kx} of {train_rows:,}).</p>')
    w('<p>Prior work, cited for what it covers. <a href="https://arxiv.org/abs/2512.19691">arXiv 2512.19691</a> audited the '
      'v1.0 test labels, estimating at least 27% are likely erroneous or incomputable, and recomputed labels from the note '
      'alone for a random half of the v1.0 training split. Its RL experiment trained on 4,593 of those relabeled training '
      'rows and beat training on the original labels by 13.5 points. It does not list which training rows were wrong or '
      'why, and it predates Verified. It names feature-extraction errors as a cause of wrong labels; this gate finds them '
      'on the training split without a model, by checking each Relevant Entity against a quoted span of its note, and '
      'lists each row. <a href="https://arxiv.org/abs/2603.02222">arXiv 2603.02222</a> fixes over 20 calculator '
      'implementation errors, including the HOMA-IR conversion above. '
      '<a href="https://arxiv.org/abs/2509.16584">arXiv 2509.16584</a> scores formula, extraction '
      'and arithmetic steps separately in model outputs. PR #7 re-ran the calculators and reported 0 train mismatches.</p>')
    if k1 == PRIOR_WORK["rows"]:
        w(f'<p>All {k1} rows are inherited from v1.0. {PRIOR_WORK["sampled"]} fell in 2512.19691\'s training sample, and '
          f'its released labels already disagree with the stored label on {PRIOR_WORK["differ"]} of them, without naming '
          f'the rows or the cause. The remaining {PRIOR_WORK["no_public"]} of the {k1} have no public corrected label that a search on '
          f'{PRIOR_WORK["checked"]} found, and none of the {k1} is fixed in Verified {RELEASE}.</p>')

    fluid = [tasks[("ver_train", r)] for r in INVALID_TASK_ROWS["fluids"]]
    fluid_text = (f'rows {join(INVALID_TASK_ROWS["fluids"])}, at '
                  + join([f'{raw_value(t.fields["weight"][0])} {t.fields["weight"][1]}' for t in fluid]))
    w('<h2 id="limitations">Limitations</h2>')
    w('<ul>')
    w(f'<li>This checks labels against the note they came from. It cannot tell whether the note itself is correct, and '
      f'{kt} of the {k1} train defects are typos in the original case report that the pipeline copied faithfully.</li>')
    child = {k: tasks[("ver_train", r)] for k, r in CHILD_DEFECT_ROWS.items()}
    months = raw_value(child["ckd_epi"].fields["age"][0][0])
    w(f'<li>It does not judge whether a task makes clinical sense. The gate flagged rows {join(INVALID_TASK_ROWS["fluids"] + INVALID_TASK_ROWS["child_sirs"])}, '
      f'but they are not label defects under this method: Holliday-Segar maintenance fluids on a fetus and on very small '
      f'neonates ({fluid_text}), and adult SIRS criteria on a 4-year-old (6805). Two counted defects are also adult '
      f'formulas applied to a child: {CHILD_DEFECT_ROWS["sirs"]}, adult SIRS criteria on an 8-year-old, and '
      f'{CHILD_DEFECT_ROWS["ckd_epi"]}, adult CKD-EPI on {article(months)} {months}-month-old.</li>')
    w('<li>The grounding check looks for numbers. It can miss an input read from the wrong sentence that still appears '
      'somewhere in the note, and there is no estimate yet of how many it misses.</li>')
    reviewer = (f"each flagged row has a first-pass call and reason; Dev has not yet confirmed {unconfirmed} of the "
                f"{len(reviewed)} defect and unclear calls" if unconfirmed else
                f"Dev read every defect and unclear row against its note; the {first_pass_only} rows called not a defect "
                f"keep their first-pass call")
    w(f'<li>{reviewer[:1].upper() + reviewer[1:]}. No clinician has read the rows. The quotes are checked by script, so '
      f'any reader can redo a call.</li>')
    w('<li>No RL training run was done, so this does not show that the label noise measurably hurts training. The only RL '
      'evidence cited is 2512.19691, on labels with a much higher estimated error rate.</li>')
    w('<li>The defects look like what any pipeline that extracts fields from clinical text can produce: a range read as one '
      'number, two readings mixed, a unit tag that does not match the value. That transfer is a hypothesis. The checks have '
      'run on MedCalc-Bench and a three-line fixture, and not on FHIR resources or any other format.</li>')
    w(f'<li>MedCalc-Bench Verified is maintained and changing. Every number here is pinned to commit {COMMIT} (release '
      f'{RELEASE}), and a later release may fix some of these rows. A draft issue listing the confirmed rows is in '
      f'upstream/ISSUE.md and has not been filed.</li>')
    w('</ul>')

    w('<h2 id="rerun">Rerun</h2>')
    w('<p>From the labelgate folder. The gate needs no model calls. The library uses only the Python standard library; the '
      'tests need pytest.</p>')
    w('<pre>make data     # download the four pinned CSVs, check sha256\nmake gate     # run G1 to G4, draw samples, write results/\n'
      'make models   # three models, cached in raw/\nmake report   # rebuild this page</pre>')

    w('<h2 id="sources">Sources</h2>')
    w('<ul>'
      '<li>Verified train, pinned: <a href="https://huggingface.co/datasets/nsk7153/MedCalc-Bench-Verified/resolve/'
      '58fc3de568bfc53a68f32327e58f60dc6eaa17f8/train_data.csv">huggingface.co/datasets/nsk7153/MedCalc-Bench-Verified</a></li>'
      '<li>v1.2 train, pinned: <a href="https://huggingface.co/datasets/ncbi/MedCalc-Bench-v1.2/resolve/'
      '915b1aad1fd2aa67790f369658cc365dfd440e90/train_data_11_18_final.csv">huggingface.co/datasets/ncbi/MedCalc-Bench-v1.2</a></li>'
      '<li>Verified repo and calculator code: <a href="https://github.com/nikhilk7153/MedCalc-Bench-Verified">github.com/nikhilk7153/MedCalc-Bench-Verified</a></li>'
      '<li>Recompute audit, PR #7: <a href="https://github.com/nikhilk7153/MedCalc-Bench-Verified/pull/7">github.com/nikhilk7153/MedCalc-Bench-Verified/pull/7</a></li>'
      '<li>Original zero-shot prompt: <a href="https://github.com/ncbi-nlp/MedCalc-Bench/blob/main/evaluation/run.py">github.com/ncbi-nlp/MedCalc-Bench, evaluation/run.py</a></li>'
      '<li>CKD-EPI 2021, Inker et al., NEJM: <a href="https://doi.org/10.1056/NEJMoa2102953">doi.org/10.1056/NEJMoa2102953</a></li>'
      '<li>MDRD, Levey et al. 2006: <a href="https://doi.org/10.7326/0003-4819-145-4-200608150-00004">doi.org/10.7326/0003-4819-145-4-200608150-00004</a></li>'
      '<li>Cockcroft-Gault 1976: <a href="https://doi.org/10.1159/000180580">doi.org/10.1159/000180580</a></li>'
      '</ul>')
    w('<p>Both datasets are CC-BY-SA 4.0. Note excerpts on this page are quoted from them with attribution.</p>')
    w(f'<footer>Built {built} by scripts/build_report.py from nsk7153/MedCalc-Bench-Verified, release {RELEASE}, commit '
      f'{COMMIT}. Every count and rate on this page is read from labelgate/results/ or the pinned data, except the '
      f'prior-work counts (2512.19691\'s sample and labels, the {RELEASE} release notes, commits 3df69cf and 192a585, and PR #5), '
      f'which come from those sources.</footer>')
    w("</main>")
    return "\n".join(parts)


def main():
    head, _, rest = build().partition("<main>")
    page = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            f"{head}\n</head>\n<body>\n<main>{rest}\n</body>\n</html>\n")
    (ROOT / "report.html").write_text(page, encoding="utf-8")
    print("wrote", ROOT / "report.html")


if __name__ == "__main__":
    main()
