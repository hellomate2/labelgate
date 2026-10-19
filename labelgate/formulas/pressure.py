def mean_arterial_pressure(sbp, dbp):
    """Row explanation: "1/3 * (systolic blood pressure) + 2/3 * (diastolic blood pressure)", in mm Hg.

    Dataset counterpart: calculator_implementations/mean_arterial_pressure.py.
    """
    return sbp[0] / 3 + 2 * dbp[0] / 3
