# Row 1545: systolic and diastolic taken from different readings

MedCalc-Bench Verified train split, release v1.0.8 (commit 58fc3de). Quotes are copied from the row's Patient Note and checked by tests/test_handcheck.py.

## Row 1545, Mean Arterial Pressure (MAP)

| | |
|---|---|
| Note says | `systolic blood pressure dropped to 70 mmHg` |
| Note says | `blood pressure was 142/74 mmHg on 0.1 μg/kg/min of epinephrine and 0.3 μg/kg/min of norepinephrine` |
| Extracted input | sbp = `70.0` mm hg |
| Extracted input | dbp = `74.0` mm hg |
| Stored answer, as stored | `72.66667` (accepted range 69.0333 to 76.3) |
| Recomputed from the extracted inputs | `72.6667` |
| What the note supports | nothing: the note gives no value this input could be replaced with |

Defect: readings mixed (extraction). SBP 70 from one sentence, DBP 74 from the pair 142/74; the only stated pair, 142/74, was taken after ECMO cannulation on epinephrine and norepinephrine, while the question asks for values before any treatment, so the note supports no answer and the task cannot be computed.
