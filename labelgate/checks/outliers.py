"""G4: values more than 100 times away from the median of the same field in the same dataset.

Labels are grouped by calculator. Inputs are grouped by field name after conversion to one unit
per field where the conversion is known, and by (field, unit) otherwise. Zeros are skipped.
Groups with fewer than MIN_GROUP values are skipped, since a median of two or three values says
nothing (on MedCalc-Bench the smallest group behind any flag has 7 values, so this changes no flag).
This is a screen. A flag here is a row to read, not a defect.
"""
import math
import statistics

from labelgate import units

CANONICAL = {
    "creatinine": ("creatinine", "mg/dL"),
    "urine_creatinine": ("creatinine", "mg/dL"),
    "sodium": ("sodium", "mmol/L"),
    "urine_sodium": ("sodium", "mmol/L"),
    "chloride": ("chloride", "mmol/L"),
    "bicarbonate": ("bicarbonate", "mmol/L"),
    "calcium": ("calcium", "mg/dL"),
    "albumin": ("albumin", "g/dL"),
    "glucose": ("glucose", "mg/dL"),
    "bun": ("bun", "mg/dL"),
}

FACTOR = 100
MIN_GROUP = 5


def _canonical(name, value, unit):
    try:
        if name in CANONICAL:
            compound, target = CANONICAL[name]
            return (name, target), units.concentration(value, unit, compound, target)
        if name == "weight":
            return (name, "kg"), units.weight_kg(value, unit)
    except (units.UnitError, KeyError):
        pass
    return (name, unit), float(value)


def _inputs(task):
    for name, (value, unit) in task.fields.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        yield name, value, _canonical(name, value, unit)


def _group(task):
    return task.meta.get("calculator") or task.formula


def _far(value, median, factor=FACTOR):
    return value != 0 and median > 0 and abs(math.log10(abs(value) / median)) > math.log10(factor)


def check(tasks, factor=FACTOR):
    """Return {task.id: [flag, ...]} for the tasks with at least one outlier.

    factor is fixed at 100 for every gate count; other values are only for describing the screen.
    """
    label_values, input_values = {}, {}
    for t in tasks:
        if t.label is not None and t.label != 0:
            label_values.setdefault(_group(t), []).append(abs(t.label))
        for _name, _value, (key, number) in _inputs(t):
            if number != 0:
                input_values.setdefault(key, []).append(abs(number))
    label_median = {k: statistics.median(v) for k, v in label_values.items() if len(v) >= MIN_GROUP}
    input_median = {k: statistics.median(v) for k, v in input_values.items() if len(v) >= MIN_GROUP}

    flags = {}
    for t in tasks:
        found = []
        if t.label is not None and _far(t.label, label_median.get(_group(t), 0), factor):
            found.append({"kind": "label", "field": "label", "value": t.label,
                          "median": label_median[_group(t)]})
        for name, value, (key, number) in _inputs(t):
            if _far(number, input_median.get(key, 0), factor):
                found.append({"kind": "input", "field": name, "value": value,
                              "median": input_median[key], "canonical": number, "unit": key[1]})
        if found:
            flags[t.id] = found
    return flags
