import pytest

from labelgate.checks import recompute
from labelgate.formulas import EXTRA, FORMULAS


def rows_where_other_checks_pass(tasks, flags, key):
    return [t for k, t in tasks.items() if key(t) and k not in flags]


@pytest.mark.parametrize("formula", sorted(FORMULAS))
def test_reference_formula(tasks, flags, formula):
    rows = rows_where_other_checks_pass(tasks, flags, lambda t: t.formula == formula)
    assert rows
    misses = [t.id for t in rows if not t.accepts(recompute.recompute(t))]
    assert misses == []


@pytest.mark.parametrize("formula", sorted(EXTRA))
def test_interval_formula(tasks, flags, formula):
    rows = rows_where_other_checks_pass(tasks, flags, lambda t: t.meta["extra_formula"] == formula)
    assert rows
    misses = [t.id for t in rows if not t.accepts(recompute.recompute(t, formula=formula))]
    assert misses == []


def test_formula_coverage(tasks):
    covered = sum(1 for (dataset, _), t in tasks.items() if dataset == "ver_train" and t.formula)
    assert len(FORMULAS) == 15
    assert covered == 3794
