"""Scores and indexes outside the 15 renal and electrolyte formulas.

G1 does not use these. They exist so a hand-check can compute what the label would be
from the values the note prints. Each follows the criteria text in the row's own
Ground Truth Explanation and is tested against stored labels on unflagged rows.
"""
import math

from labelgate import units

LITERS_PER_UNIT = {"L": 1.0, "dL": 0.1, "mL": 1e-3, "cm^3": 1e-3, "µL": 1e-6, "mm^3": 1e-6}


def _celsius(temperature):
    value, unit = temperature
    return value if unit == "degrees celsius" else (value - 32) * 5 / 9


def sirs(temperature, heart_rate, wbc, respiratory_rate=None, paco2=None, **_):
    """SIRS criteria count. Row explanation: temperature >38 or <36 °C; heart rate >90;
    respiratory rate >20 or PaCO2 <32 mm Hg; WBC >12,000/mm³ or <4,000/mm³.

    Dataset counterpart: calculator_implementations/sirs_criteria.py.
    """
    count = 0
    t = _celsius(temperature)
    count += t > 38 or t < 36
    count += heart_rate[0] > 90
    cells = wbc[0] / LITERS_PER_UNIT[units.clean(wbc[1])] * 1e-6
    count += cells > 12000 or cells < 4000
    fast = respiratory_rate is not None and respiratory_rate[0] > 20
    low_co2 = paco2 is not None and paco2[0] < 32
    count += fast or low_co2
    return count


def perc(age, heart_rate, oxygen_saturation, **criteria):
    """PERC rule count. Row explanation: age >=50, heart rate >=100, O2 saturation <95%, then one point
    each for unilateral leg swelling, hemoptysis, recent surgery or trauma, prior PE or DVT, hormone use.

    Dataset counterpart: calculator_implementations/perc_rule.py.
    """
    count = (units.age_years(age) >= 50) + (heart_rate[0] >= 100) + (oxygen_saturation[0] < 95)
    for name in ("Unilateral Leg Swelling", "Hemoptysis", "Recent surgery or trauma", "Hormone use"):
        count += bool(criteria.get(name))
    prior = criteria.get("Previously Documented Pulmonary Embolism") or criteria.get("Previously documented Deep Vein Thrombosis")
    return count + bool(prior)


def wells_pe(heart_rate, **criteria):
    """Wells' criteria for PE. Row explanation: clinical DVT signs 3, PE #1 diagnosis 3, heart rate >100 1.5,
    immobilization or recent surgery 1.5, previous PE or DVT 1.5, hemoptysis 1, malignancy 1.

    Dataset counterpart: calculator_implementations/wells_criteria_pe.py.
    """
    def has(name):
        return bool(criteria.get(name))

    score = 1.5 * (heart_rate[0] > 100)
    score += 3 * has("Clinical signs and symptoms of Deep Vein Thrombosis")
    score += 3 * has("Pulmonary Embolism is #1 diagnosis OR equally likely")
    score += 1.5 * (has("Immobilization for at least 3 days") or has("Surgery in the previous 4 weeks"))
    score += 1.5 * (has("Previously Documented Pulmonary Embolism") or has("Previously documented Deep Vein Thrombosis"))
    score += has("Hemoptysis") + has("Malignancy with treatment within 6 months or palliative")
    return score


def fib4(age, ast, alt, platelets):
    """FIB-4. Row explanation: "(Age * AST) / (Platelet count (in billions) * √ALT)", platelets per liter
    divided by 1e9, AST and ALT in U/L.

    Dataset counterpart: calculator_implementations/fibrosis_4.py.
    """
    per_liter = platelets[0] / LITERS_PER_UNIT[units.clean(platelets[1])]
    return units.age_years(age) * ast[0] / (per_liter / 1e9 * math.sqrt(alt[0]))
