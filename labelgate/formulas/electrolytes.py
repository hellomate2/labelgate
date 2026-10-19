from labelgate import units


def _meq(value, compound):
    return units.concentration(*value, compound, "mEq/L")


def _albumin_g_dl(albumin):
    return units.concentration(*albumin, "albumin", "g/dL")


def anion_gap(sodium, chloride, bicarbonate):
    """Row explanation: "sodium (mEq/L) - (chloride (mEq/L)+ bicarbonate (mEq/L))".

    Dataset counterpart: calculator_implementations/anion_gap.py.
    """
    return _meq(sodium, "sodium") - (_meq(chloride, "chloride") + _meq(bicarbonate, "bicarbonate"))


def delta_gap(sodium, chloride, bicarbonate):
    """Row explanation: "anion gap (in mEq/L) - 12".

    Dataset counterpart: calculator_implementations/delta_gap.py.
    """
    return anion_gap(sodium, chloride, bicarbonate) - 12


def delta_ratio(sodium, chloride, bicarbonate):
    """Row explanation: "delta gap (mEq/L)/(24 - bicarbonate mEq/L)".

    Dataset counterpart: calculator_implementations/delta_ratio.py.
    """
    return delta_gap(sodium, chloride, bicarbonate) / (24 - _meq(bicarbonate, "bicarbonate"))


def albumin_corrected_anion_gap(sodium, chloride, bicarbonate, albumin):
    """Row explanation: "anion_gap (in mEq/L) + 2.5 * (4 - albumin (in g/dL))".

    Dataset counterpart: calculator_implementations/albumin_corrected_anion.py.
    """
    return anion_gap(sodium, chloride, bicarbonate) + 2.5 * (4 - _albumin_g_dl(albumin))


def albumin_corrected_delta_gap(sodium, chloride, bicarbonate, albumin):
    """Row explanation: "albumin corrected anion gap (in mEq/L) - 12".

    Dataset counterpart: calculator_implementations/albumin_corrected_delta_gap.py.
    """
    return albumin_corrected_anion_gap(sodium, chloride, bicarbonate, albumin) - 12


def albumin_corrected_delta_ratio(sodium, chloride, bicarbonate, albumin):
    """Row explanation: "albumin corrected delta gap (mEq/L)/(24 - bicarbonate mEq/L)".

    Dataset counterpart: calculator_implementations/albumin_delta_ratio.py.
    """
    gap = albumin_corrected_delta_gap(sodium, chloride, bicarbonate, albumin)
    return gap / (24 - _meq(bicarbonate, "bicarbonate"))


def serum_osmolality(sodium, bun, glucose):
    """Row explanation: "2 * Na + (BUN / 2.8) + (glucose / 18)", Na in mmol/L, BUN and glucose in mg/dL.

    Dataset counterpart: calculator_implementations/sOsm.py.
    """
    na = units.concentration(*sodium, "sodium", "mmol/L")
    urea = units.concentration(*bun, "bun", "mg/dL")
    glu = units.concentration(*glucose, "glucose", "mg/dL")
    return 2 * na + urea / 2.8 + glu / 18


def free_water_deficit(sodium, weight, age, sex):
    """Row explanation: "(total body water percentage) * (weight) * (sodium/140 - 1)", weight in kg,
    sodium in mmol/L. Total body water fraction: under 18 years 0.6; 18 to 64 years 0.6 male, 0.5 female;
    65 and over 0.5 male, 0.45 female.

    Dataset counterpart: calculator_implementations/free_water_deficit.py.
    """
    years = units.age_years(age)
    if years < 18:
        tbw = 0.6
    elif years < 65:
        tbw = 0.6 if sex == "Male" else 0.5
    else:
        tbw = 0.5 if sex == "Male" else 0.45
    na = units.concentration(*sodium, "sodium", "mmol/L")
    return tbw * units.weight_kg(*weight) * (na / 140 - 1)


def sodium_correction(sodium, glucose):
    """Hillier 1999 correction. Row explanation: "Measured sodium + 0.024 * (Serum glucose - 100)",
    sodium in mEq/L, glucose in mg/dL.

    Dataset counterpart: calculator_implementations/sodium_correction_hyperglycemia.py.
    """
    na = _meq(sodium, "sodium")
    glu = units.concentration(*glucose, "glucose", "mg/dL")
    return na + 0.024 * (glu - 100)


def calcium_correction(calcium, albumin):
    """Row explanation: "(0.8 * (Normal Albumin (in g/dL) - Patient's Albumin (in g/dL))) + Serum Calcium (in mg/dL)",
    normal albumin 4.0 g/dL.

    Dataset counterpart: calculator_implementations/calcium_correction.py.
    """
    ca = units.concentration(*calcium, "calcium", "mg/dL")
    return 0.8 * (4.0 - _albumin_g_dl(albumin)) + ca
