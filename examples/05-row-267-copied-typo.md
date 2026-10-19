# Row 267: an impossible unit copied from the note

MedCalc-Bench Verified train split, release v1.0.8 (commit 58fc3de). Quotes are copied from the row's Patient Note and checked by tests/test_handcheck.py.

## Row 267, CKD-EPI Equations for Glomerular Filtration Rate

| | |
|---|---|
| Note says | `Creatinine was 130 mmol/dl` |
| Extracted input | creatinine = `130.0` mmol/dL |
| Stored answer, as stored | `0.00096752` (accepted range 0.00091914 to 0.0010159) |
| Recomputed from the extracted inputs | `0.000967517` |
| What the note supports | no interval: the note itself prints the impossible value |

Defect: source typo copied (copied typo). Note prints 130 mmol/dl; GFR label 0.00097.
