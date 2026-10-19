"""Read results/handcheck.csv and compute note-supported intervals.

note_inputs is a JSON list of alternatives. Each alternative maps a field to a list of
[value, unit] candidates; a range in the note gives two candidates. Fields not named keep
their stored value. The interval is the min to max of the label over every combination,
widened by 5% for decimal outputs, matching the dataset's tolerance.
"""
import csv
import itertools
import json

from labelgate.checks import recompute

TOLERANCE = 0.05


def load(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def confirmed_by_dev(entry):
    """True when the reviewer cell records Dev's own read of the row."""
    reviewer = entry["reviewer"]
    return "confirmed by Dev" in reviewer and "not yet confirmed" not in reviewer


def quotes(entry):
    return [q for q in entry["quote"].split(" || ") if q]


def note_values(task, note_inputs):
    """Every label value the note supports, or [] when no note_inputs are given."""
    if not note_inputs:
        return []
    formula = task.formula or task.meta.get("extra_formula")
    values = []
    for alternative in json.loads(note_inputs):
        names = list(alternative)
        for combo in itertools.product(*(alternative[n] for n in names)):
            fields = dict(task.fields)
            for name, (value, unit) in zip(names, combo):
                fields[name] = (value, unit)
            values.append(recompute.recompute(task, fields=fields, formula=formula))
    return values


def interval(task, note_inputs):
    values = note_values(task, note_inputs)
    if not values:
        return None
    low, high = min(values), max(values)
    if task.meta.get("output_type") == "decimal":
        low, high = low - abs(low) * TOLERANCE, high + abs(high) * TOLERANCE
    return low, high
