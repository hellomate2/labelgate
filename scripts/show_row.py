"""Print what a reviewer needs to hand-check a flagged row: fields, label, flags and note context.

For each flagged field the note context comes from the first source that matches:
the stored value, the span G2 recorded (for a merged range such as 150-160), the quotes in
results/handcheck.csv, then a list of words notes use for that field (pulse, BP, platelet ...).

usage: python scripts/show_row.py ver_train 1337 [1545 ...]
       python scripts/show_row.py ver_train --flagged      (every flagged row of that dataset)
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from labelgate import handcheck
from labelgate.adapters import medcalc

WINDOW = 90
BP = [r"blood pressure", r"\bB\.?P\b", r"\d{2,3}\s*/\s*\d{2,3}\s*mm"]
SYNONYMS = {
    "sbp": BP + [r"systolic"],
    "dbp": BP + [r"diastolic"],
    "heart_rate": [r"pulse", r"heart rate", r"\bHR\b", r"bpm", r"beats"],
    "respiratory_rate": [r"respirat", r"\bRR\b", r"breaths"],
    "temperature": [r"temperature", r"febrile", r"°\s*[CF]"],
    "wbc": [r"white blood", r"\bWBC\b", r"leukocyt", r"white cell"],
    "platelets": [r"platelet", r"\bPLT\b"],
    "Insulin": [r"insulin"],
    "glucose": [r"glucose", r"sugar"],
    "bun": [r"\bBUN\b", r"urea"],
    "creatinine": [r"creatinine", r"\bs?Cr\b"],
    "urine_creatinine": [r"urine creatinine", r"creatinine"],
    "urine_sodium": [r"urine sodium", r"sodium"],
    "weight": [r"weigh", r"\bkg\b", r"\blbs?\b"],
    "oxygen_saturation": [r"saturation", r"SpO2", r"\bSaO2\b", r"\bO2\b"],
    "alt": [r"\bALT\b", r"alanine"],
    "ast": [r"\bAST\b", r"aspartate"],
    "albumin": [r"albumin"],
    "calcium": [r"calcium", r"\bCa\b"],
    "sodium": [r"sodium", r"\bNa\b"],
    "chloride": [r"chloride", r"\bCl\b"],
    "bicarbonate": [r"bicarbonate", r"HCO3"],
    "paco2": [r"PaCO2", r"pCO2"],
    "height": [r"height", r"\btall\b", r"\bcm\b"],
}


def snippets(text, pattern, limit=4):
    out = []
    for m in re.finditer(pattern, text, flags=re.I):
        start, end = max(0, m.start() - WINDOW), min(len(text), m.end() + WINDOW)
        out.append("..." + text[start:end].replace("\n", " ") + "...")
        if len(out) == limit:
            break
    return out


def number_pattern(value):
    text = str(int(value)) if float(value).is_integer() else str(value)
    return r"(?<![\d.])" + re.escape(text) + r"(?![\d])"


def keyword(field):
    words = re.findall(r"[A-Za-z]{3,}", field.replace("_", " "))
    return re.escape(words[0]) if words else None


def first_number(value):
    """The field's number, or the first number of a compound value such as (160.0, 'm')."""
    parts = value if isinstance(value, tuple) else (value,)
    for part in parts:
        if isinstance(part, (int, float)) and not isinstance(part, bool):
            return part
    return None


def context(task, name, g2_spans, quotes):
    """Note snippets for one field, and where they came from."""
    value = first_number(task.fields[name][0])
    text = task.source_text
    if value is not None:
        hits = snippets(text, number_pattern(value))
        if hits:
            return "stored value", hits
    if g2_spans.get(name):
        hits = snippets(text, re.escape(g2_spans[name]))
        if hits:
            return "G2 span", hits
    hits = [h for q in quotes for h in snippets(text, re.escape(q), limit=1)]
    if hits:
        return "hand-check quote", hits
    for pattern in SYNONYMS.get(name, []) + ([keyword(name)] if keyword(name) else []):
        hits = snippets(text, pattern)
        if hits:
            return "field name", hits
    return "nothing matched", []


def show(task, flag, entry=None):
    """Return the review printout for one row as a list of lines."""
    lines = [f"=== {task.meta['split']} row {task.id} | {task.meta['calculator']} | label {task.meta['label_text']}",
             "fields: " + str({k: v for k, v in task.fields.items()})]
    if flag:
        lines.append(f"checks: {flag['checks']} | recomputed: {flag['recomputed']}")
        details = json.loads(flag["details"])
        g2_spans = {f["field"]: f["span"] for f in details["G2"] if f.get("span")}
        fields = {f["field"] for f in details["G2"]} | {f["field"] for f in details["G4"] if f["kind"] == "input"}
        if details["G3"] or any(f["kind"] == "label" for f in details["G4"]):
            fields |= {k for k, (v, _u) in task.fields.items() if first_number(v) is not None and k != "age"}
        quotes = handcheck.quotes(entry) if entry else []
        for name in sorted(fields):
            source, hits = context(task, name, g2_spans, quotes)
            lines.append(f"  [{name} = {task.fields[name]}]  context from: {source}")
            lines += ["      " + h for h in hits]
    if entry:
        lines.append(f"hand-check: {entry['decision']} | {entry['reason']}")
    lines.append("")
    return lines


def main():
    dataset, args = sys.argv[1], sys.argv[2:]
    tasks = {t.id: t for t in medcalc.load(ROOT / f"data/{dataset}.csv", dataset)}
    with open(ROOT / "results/flags.csv", newline="", encoding="utf-8") as f:
        flags = {r["row"]: r for r in csv.DictReader(f) if r["dataset"] == dataset}
    entries = {e["row"]: e for e in handcheck.load(ROOT / "results/handcheck.csv") if e["dataset"] == dataset}
    ids = list(flags) if args == ["--flagged"] else args
    for row_id in ids:
        print("\n".join(show(tasks[row_id], flags.get(row_id), entries.get(row_id))))


if __name__ == "__main__":
    main()
