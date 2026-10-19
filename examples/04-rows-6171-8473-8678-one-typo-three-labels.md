# Rows 6171, 8473 and 8678: one note typo, three wrong labels

MedCalc-Bench Verified train split, release v1.0.8 (commit 58fc3de). Quotes are copied from the row's Patient Note and checked by tests/test_handcheck.py.

## Row 6171, Anion Gap

| | |
|---|---|
| Note says | `sodium of 136 mmol/dl` |
| Extracted input | sodium = `136.0` mmol/dL |
| Stored answer, as stored | `1230.0` (accepted range 1,168.5 to 1,291.5) |
| Recomputed from the extracted inputs | `1,230` |
| What the note supports | no interval: the note itself prints the impossible value |

Defect: source typo copied (copied typo). Note prints sodium 136 mmol/dl; anion gap label 1230.

## Row 8473, Delta Gap

| | |
|---|---|
| Note says | `sodium of 136 mmol/dl` |
| Extracted input | sodium = `136.0` mmol/dL |
| Stored answer, as stored | `1218.0` (accepted range 1,157.1 to 1,278.9) |
| Recomputed from the extracted inputs | `1,218` |
| What the note supports | no interval: the note itself prints the impossible value |

Defect: source typo copied (copied typo). Same note as row 6171; delta gap label 1218.

## Row 8678, Delta Ratio

| | |
|---|---|
| Note says | `sodium of 136 mmol/dl` |
| Extracted input | sodium = `136.0` mmol/dL |
| Stored answer, as stored | `-609.0` (accepted range -639.45 to -578.55) |
| Recomputed from the extracted inputs | `-609` |
| What the note supports | no interval: the note itself prints the impossible value |

Defect: source typo copied (copied typo). Same note as row 6171; delta ratio label -609.
