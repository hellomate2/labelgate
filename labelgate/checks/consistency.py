"""G3: rules that follow from definitions, with no clinical bounds.

Diastolic pressure cannot exceed systolic, and a mean arterial pressure must lie between them.
The third rule from the spec, that a label equals its own recompute, is reported by G1.
"""


def _number(task, name):
    value, _unit = task.fields.get(name, (None, None))
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def check(task):
    sbp, dbp = _number(task, "sbp"), _number(task, "dbp")
    flags = []
    if sbp is None or dbp is None:
        return flags
    if dbp > sbp:
        flags.append("dbp_above_sbp")
    if task.formula == "mean_arterial_pressure" and task.label is not None:
        if not dbp <= task.label <= sbp:
            flags.append("map_outside_bp")
    return flags
