"""G1: recompute the label from the extracted fields with an independent reference formula."""
import inspect

from labelgate.formulas import EXTRA, FORMULAS
from labelgate.units import UnitError


def _argument(value, unit):
    return value if unit is None else (value, unit)


def recompute(task, fields=None, formula=None):
    """Return the formula value for the task's fields, or for replacement fields if given.

    formula defaults to task.formula and may name a function in FORMULAS or EXTRA.
    """
    fields = task.fields if fields is None else fields
    formula = formula or task.formula
    fn = FORMULAS.get(formula) or EXTRA[formula]
    params = inspect.signature(fn).parameters
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return fn(**{k: _argument(*v) for k, v in fields.items()})
    kwargs = {}
    for name, param in params.items():
        if name not in fields:
            if param.default is inspect.Parameter.empty:
                raise KeyError(f"missing field {name}")
            continue
        kwargs[name] = _argument(*fields[name])
    return fn(**kwargs)


def check(task):
    """status is one of: no_formula, skipped, match, mismatch."""
    if task.formula is None or task.formula not in FORMULAS:
        return {"status": "no_formula", "recomputed": None, "reason": ""}
    try:
        value = recompute(task)
    except (KeyError, UnitError, ZeroDivisionError, TypeError, ValueError) as err:
        return {"status": "skipped", "recomputed": None, "reason": str(err)}
    status = "match" if task.accepts(value) else "mismatch"
    return {"status": status, "recomputed": value, "reason": ""}
