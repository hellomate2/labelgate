from labelgate import units


def ckd_epi_2021(creatinine, age, sex):
    """CKD-EPI 2021 creatinine equation, race-free (Inker et al., NEJM 2021, doi:10.1056/NEJMoa2102953).

    eGFR = 142 * min(Scr/k, 1)**a * max(Scr/k, 1)**-1.200 * 0.9938**age * 1.012 [if female],
    k = 0.7 (female) or 0.9 (male), a = -0.241 (female) or -0.302 (male), Scr in mg/dL.
    Dataset counterpart: calculator_implementations/ckd-epi_2021_creatinine.py.
    """
    scr = units.concentration(*creatinine, "creatinine", "mg/dL")
    years = units.age_years(age)
    female = sex == "Female"
    k = 0.7 if female else 0.9
    a = -0.241 if female else -0.302
    ratio = scr / k
    gfr = 142 * min(ratio, 1) ** a * max(ratio, 1) ** -1.200 * 0.9938 ** years
    return gfr * 1.012 if female else gfr


def mdrd(creatinine, age, sex, race=None):
    """IDMS-traceable 4-variable MDRD (Levey et al., Ann Intern Med 2006, doi:10.7326/0003-4819-145-4-200608150-00004).

    GFR = 175 * Scr**-1.154 * age**-0.203 * 0.742 [if female] * 1.212 [if Black], Scr in mg/dL.
    Row explanation: "The race coefficient is 1.212 if the patient is Black and 1.0 otherwise."
    Dataset counterpart: calculator_implementations/mdrd_gfr.py.
    """
    scr = units.concentration(*creatinine, "creatinine", "mg/dL")
    years = units.age_years(age)
    gfr = 175 * scr ** -1.154 * years ** -0.203
    if sex == "Female":
        gfr *= 0.742
    if race == "Black":
        gfr *= 1.212
    return gfr


def ideal_body_weight(height, sex):
    """Devine formula as the dataset states it: 50 kg (male) or 45.5 kg (female) + 2.3 kg per inch over 60."""
    inches = units.height_m(height) / 0.0254
    base = 50 if sex == "Male" else 45.5
    return base + 2.3 * (inches - 60)


def cockcroft_gault(creatinine, age, sex, weight, height):
    """Cockcroft-Gault creatinine clearance (Cockcroft and Gault, Nephron 1976, doi:10.1159/000180580).

    Row explanation: "CrCl = ((140 - age) * adjusted weight * (gender_coefficient)) / (serum creatinine * 72),
    where the gender_coefficient is 1 if male, and 0.85 if female." Adjusted weight follows the task question:
    actual weight if BMI < 18.5, min(ideal, actual) if 18.5 <= BMI <= 24.9, otherwise
    ideal + 0.4 * (actual - ideal).
    Dataset counterpart: calculator_implementations/creatinine_clearance.py.
    """
    scr = units.concentration(*creatinine, "creatinine", "mg/dL")
    years = units.age_years(age)
    kg = units.weight_kg(*weight)
    bmi = kg / units.height_m(height) ** 2
    ibw = ideal_body_weight(height, sex)
    if bmi < 18.5:
        adjusted = kg
    elif bmi <= 24.9:
        adjusted = min(ibw, kg)
    else:
        adjusted = ibw + 0.4 * (kg - ibw)
    coefficient = 1 if sex == "Male" else 0.85
    return (140 - years) * adjusted * coefficient / (scr * 72)


def fena(sodium, creatinine, urine_sodium, urine_creatinine):
    """Fractional excretion of sodium, in percent.

    Row explanation: "(creatinine * urine_sodium)/(sodium * urine_creatinine) * 100", creatinine values in mg/dL,
    sodium values in mEq/L.
    Dataset counterpart: calculator_implementations/compute_fena.py.
    """
    na = units.concentration(*sodium, "sodium", "mEq/L")
    scr = units.concentration(*creatinine, "creatinine", "mg/dL")
    una = units.concentration(*urine_sodium, "sodium", "mEq/L")
    ucr = units.concentration(*urine_creatinine, "creatinine", "mg/dL")
    return scr * una / (na * ucr) * 100
