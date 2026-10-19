"""Read tasks from JSONL, one object per line:

{"id": "t1", "source_text": "...", "fields": {"sodium": [140, "mmol/L"], "sex": ["Female", null]},
 "label": 12.0, "formula": "anion_gap", "tolerance": 0.05, "calculator": "Anion Gap"}

formula, tolerance and calculator are optional. Without a formula the row still gets G2, G3 and G4.
calculator names the group G4 takes its label medians over; without it, tasks are grouped by formula.

Every row is checked when it is read. A row is rejected, with its line number and the reason, when a
field is not a [value, unit] pair, a number has no unit, a number is negative, NaN or infinite, the
label is not a number, sex is not male or female, or the formula name is unknown. Sex is normalized to
"Male" or "Female", and unit case is normalized ("mmol/l" reads as "mmol/L", "KG" as "kg").
"""
import json
import math

from labelgate import units
from labelgate.formulas import FORMULAS
from labelgate.task import Task

SEX = {"male": "Male", "m": "Male", "man": "Male", "female": "Female", "f": "Female", "woman": "Female"}
AMOUNTS = {u.lower(): u for u in [*units.MOLES, *units.GRAMS, "mEq"]}
VOLUMES = {u.lower(): u for u in units.LITERS}
WEIGHTS = {"kg": "kg", "g": "g", "lb": "lbs", "lbs": "lbs"}


class RowError(ValueError):
    pass


def _is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _number(x, what):
    if not _is_number(x):
        raise RowError(f"{what} must be a number, got {x!r}")
    if not math.isfinite(x):
        raise RowError(f"{what} is {x!r}")
    return x


def _unit(unit):
    """Normalize the case of a concentration or weight unit; leave anything else as written."""
    text = unit.strip()
    if text.lower() in WEIGHTS:
        return WEIGHTS[text.lower()]
    if "/" in text:
        amount, volume = text.split("/", 1)
        amount = units.clean(amount)
        if amount.lower() in AMOUNTS and volume.lower() in VOLUMES:
            return f"{AMOUNTS[amount.lower()]}/{VOLUMES[volume.lower()]}"
    return text


def _field(name, pair):
    if not isinstance(pair, list) or len(pair) != 2:
        raise RowError(f"field {name!r} must be a [value, unit] pair, got {pair!r}")
    value, unit = pair
    if unit is not None and not isinstance(unit, str):
        raise RowError(f"field {name!r} has a unit that is not a string: {unit!r}")
    if name == "sex":
        if not isinstance(value, str) or value.strip().lower() not in SEX:
            raise RowError(f"sex must be male or female, got {value!r}")
        return SEX[value.strip().lower()], None
    if isinstance(value, list):
        for part in value:
            if _is_number(part):
                _number(part, f"field {name!r}")
                if part < 0:
                    raise RowError(f"field {name!r} is negative: {part!r}")
        return tuple(value), unit
    if _is_number(value):
        _number(value, f"field {name!r}")
        if value < 0:
            raise RowError(f"field {name!r} is negative: {value!r}")
        if unit is None:
            raise RowError(f"field {name!r} is a number with no unit")
        return value, _unit(unit)
    if isinstance(value, (bool, str)) or value is None:
        return value, unit
    raise RowError(f"field {name!r} has a value of type {type(value).__name__}")


def _task(row):
    if not isinstance(row, dict):
        raise RowError("line is not a JSON object")
    for key in ("id", "source_text", "fields"):
        if key not in row:
            raise RowError(f"missing {key!r}")
    if not isinstance(row["source_text"], str):
        raise RowError("source_text must be a string")
    if not isinstance(row["fields"], dict) or not row["fields"]:
        raise RowError("fields must be a non-empty object")
    label = row.get("label")
    if label is not None:
        _number(label, "label")
    formula = row.get("formula")
    if formula is not None and formula not in FORMULAS:
        raise RowError(f"unknown formula {formula!r}; known: {', '.join(sorted(FORMULAS))}")
    tolerance = _number(row.get("tolerance", 0.05), "tolerance")
    if not 0 <= tolerance < 1:
        raise RowError(f"tolerance must be between 0 and 1, got {tolerance!r}")
    fields = {str(k): _field(str(k), v) for k, v in row["fields"].items()}
    return Task(id=str(row["id"]), source_text=row["source_text"], fields=fields, label=label, formula=formula,
                tolerance=tolerance, meta={"calculator": row.get("calculator")})


def read(path):
    """Return (tasks, rejected), where rejected lists (line number, id, reason) for every row not loaded."""
    tasks, rejected = [], []
    with open(path, encoding="utf-8") as f:
        for number, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as err:
                rejected.append((number, "", f"not valid JSON: {err}"))
                continue
            try:
                tasks.append(_task(row))
            except RowError as err:
                rejected.append((number, str(row.get("id", "")) if isinstance(row, dict) else "", str(err)))
    return tasks, rejected


def load(path):
    """Return the tasks, or raise ValueError naming the first row that cannot be read."""
    tasks, rejected = read(path)
    if rejected:
        number, id_, reason = rejected[0]
        raise ValueError(f"{path}, line {number} (id {id_ or '?'}): {reason}")
    return tasks
