"""Read a MedCalc-Bench CSV (v1.2 or Verified) into Tasks."""
import ast
import csv
import sys
from pathlib import Path

from labelgate.task import Task

csv.field_size_limit(sys.maxsize)

FORMULA_BY_CALCULATOR = {
    2: "cockcroft_gault",
    3: "ckd_epi_2021",
    5: "mean_arterial_pressure",
    7: "calcium_correction",
    9: "mdrd",
    26: "sodium_correction",
    30: "serum_osmolality",
    38: "free_water_deficit",
    39: "anion_gap",
    40: "fena",
    63: "delta_gap",
    64: "delta_ratio",
    65: "albumin_corrected_anion_gap",
    66: "albumin_corrected_delta_gap",
    67: "albumin_corrected_delta_ratio",
}

FIELD_NAMES = {
    "Systolic Blood Pressure": "sbp",
    "Diastolic Blood Pressure": "dbp",
    "Sodium": "sodium",
    "Chloride": "chloride",
    "Bicarbonate": "bicarbonate",
    "Albumin": "albumin",
    "Calcium": "calcium",
    "Glucose": "glucose",
    "Blood Urea Nitrogen (BUN)": "bun",
    "Urine sodium": "urine_sodium",
    "Urine creatinine": "urine_creatinine",
    "Race": "race",
    "Temperature": "temperature",
    "Heart Rate or Pulse": "heart_rate",
    "respiratory rate": "respiratory_rate",
    "White blood cell count": "wbc",
    "PaCO2": "paco2",
    "O₂ saturation percentage": "oxygen_saturation",
    "Alanine aminotransferase": "alt",
    "Aspartate aminotransferase": "ast",
    "Platelet count": "platelets",
}

EXTRA_BY_CALCULATOR = {8: "wells_pe", 19: "fib4", 48: "perc", 51: "sirs"}


def parse_entities(text):
    """Turn the Relevant Entities string into {name: (value, unit)}.

    A [number, unit] pair keeps its unit. Age and height stay whole, as (parts, None), because
    they can come as years plus months or feet plus inches. Any other list, bare number, bool or
    string gets unit None.
    """
    fields = {}
    for name, raw in ast.literal_eval(text).items():
        key = FIELD_NAMES.get(name, name)
        is_pair = isinstance(raw, list) and len(raw) == 2 and isinstance(raw[1], str)
        if is_pair and key not in ("age", "height") and not isinstance(raw[0], str):
            fields[key] = (raw[0], raw[1])
        elif isinstance(raw, list):
            fields[key] = (tuple(raw), None)
        else:
            fields[key] = (raw, None)
    return fields


def _number(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def load(path, split):
    tasks = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            calculator = int(row["Calculator ID"])
            tasks.append(Task(
                id=row["Row Number"],
                source_text=row["Patient Note"],
                fields=parse_entities(row["Relevant Entities"]),
                label=_number(row["Ground Truth Answer"]),
                formula=FORMULA_BY_CALCULATOR.get(calculator),
                lower=_number(row["Lower Limit"]),
                upper=_number(row["Upper Limit"]),
                meta={
                    "split": split,
                    "calculator_id": calculator,
                    "calculator": row["Calculator Name"],
                    "extra_formula": EXTRA_BY_CALCULATOR.get(calculator),
                    "note_id": row["Note ID"],
                    "output_type": row["Output Type"],
                    "question": row["Question"],
                    "label_text": row["Ground Truth Answer"],
                    "explanation": row["Ground Truth Explanation"],
                },
            ))
    return tasks


def load_splits(data_dir, datasets=("ver_train", "ver_test")):
    """{(dataset, row): Task} for the named CSVs in data_dir, e.g. data/ver_train.csv."""
    tasks = {}
    for dataset in datasets:
        for t in load(Path(data_dir) / f"{dataset}.csv", dataset):
            tasks[(dataset, t.id)] = t
    return tasks


def raw_path(root, model, kind, dataset, row):
    """Where a cached model call lives: raw/<model>/<kind>-<row>.json, test rows prefixed by dataset."""
    name = row if dataset == "ver_train" else f"{dataset}-{row}"
    return Path(root) / "raw" / model / f"{kind}-{name}.json"
