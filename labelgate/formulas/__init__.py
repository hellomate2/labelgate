from labelgate.formulas import electrolytes, kidney, pressure, scores

FORMULAS = {
    "ckd_epi_2021": kidney.ckd_epi_2021,
    "mdrd": kidney.mdrd,
    "cockcroft_gault": kidney.cockcroft_gault,
    "fena": kidney.fena,
    "anion_gap": electrolytes.anion_gap,
    "delta_gap": electrolytes.delta_gap,
    "delta_ratio": electrolytes.delta_ratio,
    "albumin_corrected_anion_gap": electrolytes.albumin_corrected_anion_gap,
    "albumin_corrected_delta_gap": electrolytes.albumin_corrected_delta_gap,
    "albumin_corrected_delta_ratio": electrolytes.albumin_corrected_delta_ratio,
    "serum_osmolality": electrolytes.serum_osmolality,
    "free_water_deficit": electrolytes.free_water_deficit,
    "sodium_correction": electrolytes.sodium_correction,
    "calcium_correction": electrolytes.calcium_correction,
    "mean_arterial_pressure": pressure.mean_arterial_pressure,
}

EXTRA = {
    "sirs": scores.sirs,
    "perc": scores.perc,
    "wells_pe": scores.wells_pe,
    "fib4": scores.fib4,
}
