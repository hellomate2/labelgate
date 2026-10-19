import math

from labelgate import stats, units
from labelgate.checks import consistency, grounding, recompute
from labelgate.task import Task


def test_row_1337_flagged(tasks, flags):
    task = tasks[("ver_train", "1337")]
    hits = {f["field"]: f for f in grounding.check(task)}
    assert hits["sbp"]["kind"] == "range_merged" and hits["sbp"]["span"] == "150-160"
    assert hits["dbp"]["kind"] == "range_merged" and hits["dbp"]["span"] == "80-90"
    assert recompute.check(task)["status"] == "match"
    assert ("ver_train", "1337") in flags


def test_row_1545_map(tasks):
    assert consistency.check(tasks[("ver_train", "1545")]) == ["dbp_above_sbp", "map_outside_bp"]


def test_power_of_ten():
    task = Task(id="x", source_text="creatinine 88 µmol/L and WBC 12.5", fields={"wbc": (12500, "mm^3")}, label=None)
    assert grounding.check(task) == []


def test_unit_conversion():
    assert math.isclose(units.concentration(88.4, "µmol/L", "creatinine", "mg/dL"), 1.0, rel_tol=0.01)
    assert math.isclose(units.concentration(2.5, "mmol/L", "calcium", "mg/dL"), 10.02)
    assert units.concentration(140, "mmol/L", "sodium", "mEq/L") == 140
    assert units.age_years((2, "years", 11, "months")) == 2


def test_wilson():
    low, high = stats.wilson(0, 100)
    assert low == 0 and math.isclose(high, 0.037, abs_tol=0.0005)
    low, high = stats.wilson(7, 9)
    assert 0.45 < low < 0.46 and 0.93 < high < 0.94


def test_bootstrap_seeded():
    a, b = [1, 1, 0, 1, 0, 1], [0, 1, 0, 0, 0, 1]
    assert stats.paired_bootstrap(a, b) == stats.paired_bootstrap(a, b)


def test_jsonl_adapter():
    from pathlib import Path

    from labelgate.adapters import jsonl

    tasks = {t.id: t for t in jsonl.load(Path(__file__).parent / "fixtures/tasks.jsonl")}
    assert recompute.check(tasks["ok"])["status"] == "match"
    assert [f["kind"] for f in grounding.check(tasks["merged"])] == ["range_merged", "range_merged"]
    assert recompute.check(tasks["wrong"])["status"] == "mismatch"


def test_reads_note_formats():
    text = "creatinine 3,79 mg/dL, WBC 9 500, weight 64. 4 kg, platelets 1.79×105"
    numbers = grounding.note_numbers(text, formats=True)
    for want in (3.79, 9500.0, 64.4, 1.79e5):
        assert any(math.isclose(n, want) for n in numbers), want


def test_formats_only_add():
    text = "BP 150-160/80-90 mmHg, sodium 1,230 and 3,5"
    plain = grounding.note_numbers(text)
    assert set(plain) <= set(grounding.note_numbers(text, formats=True))


def test_jsonl_rejects_bad_rows(tmp_path):
    from labelgate.adapters import jsonl

    rows = [
        '{"id": "a", "source_text": "Na 140", "fields": {"sodium": [140, null]}, "label": 1}',
        '{"id": "b", "source_text": "Na 140", "fields": {"sodium": [140]}, "label": 1}',
        '{"id": "c", "source_text": "Na 140", "fields": {"sodium": [140, "mmol/L"]}, "label": "12"}',
        '{"id": "d", "source_text": "Na 140", "fields": {"sodium": [NaN, "mmol/L"]}, "label": 1}',
        '{"id": "e", "source_text": "Cr", "fields": {"creatinine": [-1, "mg/dL"]}, "label": 1}',
        '{"id": "f", "source_text": "x", "fields": {"sex": "Female"}, "label": 1}',
        '{"id": "g", "source_text": "x", "fields": {"sodium": [140, "mmol/L"]}, "label": 1, "formula": "nope"}',
        '{"id": "ok", "source_text": "Na 140, Cl 100, HCO3 24.", "fields": {"sodium": [140, "mmol/l"], '
        '"chloride": [100, "mmol/l"], "bicarbonate": [24, "mmol/l"], "sex": ["female", null]}, "label": 30, '
        '"formula": "anion_gap"}',
    ]
    path = tmp_path / "tasks.jsonl"
    path.write_text("\n".join(rows) + "\n")
    tasks, rejected = jsonl.read(path)
    assert [r[1] for r in rejected] == list("abcdefg")
    (task,) = tasks
    assert task.fields["sex"] == ("Female", None) and task.fields["sodium"][1] == "mmol/L"
    assert recompute.check(task)["status"] == "mismatch"


def test_g4_skips_small_groups():
    from labelgate.checks import outliers

    pair = [Task(id=str(i), source_text="", fields={}, label=v, meta={"calculator": "c"}) for i, v in enumerate((1, 1000))]
    assert outliers.check(pair) == {}


def test_parse_exponent():
    from labelgate import answers

    assert answers.parse('{"answer": 4.74e-07}', 1) == 4.74e-07
    assert answers.parse('{"answer": "12.5 mL/min/1.73 m²"}', 3) == 12.5
