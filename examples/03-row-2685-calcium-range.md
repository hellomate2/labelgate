# Row 2685: a calcium range read as one value

MedCalc-Bench Verified train split, release v1.0.8 (commit 58fc3de). Quotes are copied from the row's Patient Note and checked by tests/test_handcheck.py.

## Row 2685, Calcium Correction for Hypoalbuminemia

| | |
|---|---|
| Note says | `serum calcium 1.95-2.25 g/L` |
| Extracted input | calcium = `952.25` g/L |
| Stored answer, as stored | `95225.4` (accepted range 90,464.1 to 99,986.7) |
| Recomputed from the extracted inputs | `95,225.4` |
| What the note supports, if the note's g/L is read as mmol/L | `8.2156` to `9.418` (`7.80482` to `9.8889` with the 5% tolerance) |

Defect: range merged (extraction). Range 1.95-2.25 read as 952.25; the note prints g/L, which would give an impossible corrected calcium of about 186 to 237 mg/dL, and its own reference range (2.10-2.55) is the usual mmol/L range, so the interval assumes mmol/L.
