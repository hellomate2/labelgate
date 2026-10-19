"""Unit conversion for the quantities the renal and electrolyte formulas use.

Molar masses and valences are the ones the MedCalc-Bench Verified calculators use
(calculator_implementations/*.py at v1.0.8), so a recompute converts units the same way
the label generator did.
"""

MOLAR_MASS = {
    "creatinine": 113.12,
    "sodium": 22.99,
    "chloride": 35.45,
    "bicarbonate": 61.02,
    "calcium": 40.08,
    "albumin": 66500.0,
    "bun": 28.02,
    "glucose": 180.16,
}

VALENCE = {"sodium": 1, "chloride": 1, "bicarbonate": 1, "calcium": 2}

MOLES = {"mol": 1.0, "mmol": 1e-3, "µmol": 1e-6, "pmol": 1e-9}
GRAMS = {"kg": 1e3, "g": 1.0, "mg": 1e-3, "µg": 1e-6}
LITERS = {"L": 1.0, "dL": 0.1, "mL": 1e-3}


class UnitError(ValueError):
    pass


def clean(unit):
    unit = unit.strip().replace("μ", "µ")
    if unit.startswith("u"):
        unit = "µ" + unit[1:]
    return unit


def _amount_to_mol(value, mass_unit, compound):
    """Convert an amount (mol, g or mEq family) to moles."""
    if mass_unit in MOLES:
        return value * MOLES[mass_unit]
    if mass_unit in GRAMS:
        return value * GRAMS[mass_unit] / MOLAR_MASS[compound]
    if mass_unit == "mEq":
        if compound not in VALENCE:
            raise UnitError(f"no valence for {compound}")
        return value * 1e-3 / VALENCE[compound]
    raise UnitError(f"unknown amount unit {mass_unit}")


def _mol_to_amount(mol, mass_unit, compound):
    if mass_unit in MOLES:
        return mol / MOLES[mass_unit]
    if mass_unit in GRAMS:
        return mol * MOLAR_MASS[compound] / GRAMS[mass_unit]
    if mass_unit == "mEq":
        if compound not in VALENCE:
            raise UnitError(f"no valence for {compound}")
        return mol * VALENCE[compound] * 1e3
    raise UnitError(f"unknown amount unit {mass_unit}")


def concentration(value, unit, compound, target):
    """Convert a concentration such as 1.2 mg/dL into the target unit such as µmol/L."""
    unit = clean(unit)
    if unit == target:
        return float(value)
    try:
        src_amount, src_vol = unit.split("/")
        tgt_amount, tgt_vol = target.split("/")
    except ValueError:
        raise UnitError(f"cannot read concentration unit {unit!r}")
    if src_vol not in LITERS or tgt_vol not in LITERS:
        raise UnitError(f"unknown volume in {unit!r} or {target!r}")
    mol_per_liter = _amount_to_mol(value, src_amount, compound) / LITERS[src_vol]
    return _mol_to_amount(mol_per_liter * LITERS[tgt_vol], tgt_amount, compound)


def weight_kg(value, unit):
    unit = unit.strip()
    if unit == "kg":
        return float(value)
    if unit == "lbs":
        return value * 0.453592
    if unit == "g":
        return value / 1000
    raise UnitError(f"unknown weight unit {unit!r}")


def height_m(height):
    """height is (value, unit) or the dataset's 4-item form (feet, 'ft', inches, 'in')."""
    if len(height) == 4:
        return (height[0] * 12 + height[2]) * 0.0254
    value, unit = height
    factor = {"m": 1.0, "cm": 0.01, "in": 0.0254, "ft": 0.3048}.get(unit.strip())
    if factor is None:
        raise UnitError(f"unknown height unit {unit!r}")
    return value * factor


def age_years(age):
    """Whole years, the way the dataset counts them: months // 12, weeks // 52, days as 0.

    The first unit in the list decides, as in the dataset's age_conversion.py.
    """
    for i in range(0, len(age) - 1, 2):
        value, unit = age[i], age[i + 1]
        if "year" in unit:
            return value
        if "month" in unit:
            return value // 12
        if "week" in unit:
            return value // 52
        if "day" in unit:
            return 0
    raise UnitError(f"cannot read age {age!r}")
