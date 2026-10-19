# Row 1337: a blood pressure range read as one number

MedCalc-Bench Verified train split, release v1.0.8 (commit 58fc3de). Quotes are copied from the row's Patient Note and checked by tests/test_handcheck.py.

## Row 1337, Mean Arterial Pressure (MAP)

| | |
|---|---|
| Note says | `150-160/80-90 mmHg` |
| Note says | `baseline of 100-130/70-80 mmHg` |
| Extracted input | sbp = `150160.0` mm hg |
| Extracted input | dbp = `8090.0` mm hg |
| Stored answer, as stored | `55446.66667` (accepted range 52,674.3 to 58,219) |
| Recomputed from the extracted inputs | `55,446.7` |
| What the note supports | `80` to `113.333` (`76` to `119` with the 5% tolerance) |

Defect: range merged (extraction). Range 150-160/80-90 read as SBP 150160 and DBP 8090; the note also gives a baseline range of 100-130/70-80, and both come before the blood-pressure treatment, so the interval spans both ranges.

Arithmetic: MAP = SBP / 3 + 2 x DBP / 3. With the stored inputs that is 150160 / 3 + 2 x 8090 / 3 = 55,446.7.
