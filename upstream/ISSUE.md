# Training rows whose label follows a misread or mistyped input (train_data.csv, v1.0.8)

Draft, not filed.

The recompute audit in PR #7 re-runs each row's calculator on its Relevant Entities and finds 0 mismatches
in train_data.csv. The rows below also pass that check, because the label follows from its Relevant Entities and
the entity is what is wrong: it does not match what the Patient Note says, or the note itself prints an impossible
unit and the entity copies it.

Each row lists the exact note text, the stored entity and the stored answer. Every quote is a literal substring
of that row's Patient Note at commit 58fc3de. I read each row against its note and agree with each call. No clinician has read them. Please treat the list as a set of rows to look at,
not as final. Four more rows (6414, 6639, 6653, 6769) look like the same patterns on a second check. They are marked unclear and left out of the tables.

9 of these rows have a different stored answer in Verified than in v1.2 (267, 311, 409, 463, 467, 3175, 3211, 3337, 3394). 8 were re-rounded; 3211 moved from 12129.9063 to 11632.92792 because the v1.2 explanation rounded an intermediate value: v1.2 used 0.012 where Verified kept 0.012443. In each case the new answer still follows from the impossible entity.

## train_data.csv: The entity does not match the note (22 rows)

| Row | Calculator | Note text | Stored entity | Stored answer | Why |
|---|---|---|---|---|---|
| 463 | CKD-EPI Equations for Glomerular Filtration Rate | `around 200mol/L` | creatinine=200.0 mmol/L | 0.0087006 | the question asks for pre-treatment values; the note's first creatinine is 274 mmol/L, and the extraction took the later follow-up value (around 200mol/L) and tagged it mmol/L; both units the note prints are impossible for creatinine (likely µmol/L), so there is no interval, and the GFR label of 0.0087 is wrong either way |
| 1337 | Mean Arterial Pressure (MAP) | `150-160/80-90 mmHg` / `baseline of 100-130/70-80 mmHg` | sbp=150160.0 mm hg; dbp=8090.0 mm hg | 55446.66667 | range 150-160/80-90 read as SBP 150160 and DBP 8090; the note also gives a baseline range of 100-130/70-80, and both come before the blood-pressure treatment, so the interval spans both ranges |
| 1545 | Mean Arterial Pressure (MAP) | `systolic blood pressure dropped to 70 mmHg` / `blood pressure was 142/74 mmHg on 0.1 μg/kg/min of epinephrine and 0.3 μg/kg/min of norepinephrine` | sbp=70.0 mm hg; dbp=74.0 mm hg | 72.66667 | SBP 70 from one sentence, DBP 74 from the pair 142/74; the only stated pair, 142/74, was taken after ECMO cannulation on epinephrine and norepinephrine, while the question asks for values before any treatment, so the note supports no answer and the task cannot be computed |
| 2685 | Calcium Correction for Hypoalbuminemia | `serum calcium 1.95-2.25 g/L` | calcium=952.25 g/L | 95225.4 | range 1.95-2.25 read as 952.25; the note prints g/L, which would give an impossible corrected calcium of about 186 to 237 mg/dL, and its own reference range (2.10-2.55) is the usual mmol/L range, so the interval assumes mmol/L |
| 2807 | Wells' Criteria for Pulmonary Embolism | `pulse 40-50 bpm` | heart_rate=4050.0 beats per minute | 1.5 | pulse 40-50 read as 4050, which scores the heart rate >100 criterion (1.5 points); read as 40-50, that criterion scores 0, not 1.5 |
| 3703 | Ideal Body Weight | `her height was 160 mm` | height=(160.0, 'm') | 14395.6968 | note prints height 160 mm, itself impossible (likely cm); extraction tagged it m, which is not what the note says either; IBW label 14,395.7 kg |
| 4309 | Fibrosis-4 (FIB-4) Index for Liver Fibrosis | `platelets 140 × 109 l−1` | platelets=140000000.0 L | 2273.48119 | note prints 140 x 10^9 per L; the unit tag is L, as in the note, and the stored 140,000,000 per L lost a factor of 1,000 |
| 4318 | Fibrosis-4 (FIB-4) Index for Liver Fibrosis | `platelets 213 × 109/L` | platelets=213000000.0 L | 1691.60545 | note prints 213 x 10^9/L; the unit tag is L, as in the note, and the stored 213,000,000 per L lost a factor of 1,000 |
| 4323 | Fibrosis-4 (FIB-4) Index for Liver Fibrosis | `platelet count of 294 × 109/L` | platelets=294000000.0 L | 3705.36697 | note prints 294 x 10^9/L; the unit tag is L, as in the note, and the stored 294,000,000 per L lost a factor of 1,000 |
| 4336 | Fibrosis-4 (FIB-4) Index for Liver Fibrosis | `platelet count was 111*109/L` / `alanine aminotransferase (ALT): 41 IU/L` / `(AST): 41 IU/L` / `ALT: 52 U/L, AST: 54 U/L` / `297*109/L after 18 days` | platelets=297000000.0 L; ast=54.0 U/L; alt=52.0 U/L | 1664.10059 | inputs come from post-treatment time points: platelets 297 x 10^9/L at day 18, stored as 297 x 10^6/L, and AST/ALT 54/52 measured on entecavir; the pre-treatment values are platelets 111 x 10^9/L and AST/ALT 41/41, which give FIB-4 3.81 |
| 4347 | Fibrosis-4 (FIB-4) Index for Liver Fibrosis | `platelet 398×109/L` / `AST 0.42 ukat/L` / `ALT 0.6 ukat/L` | platelets=398000000.0 L; ast=0.42 U/L; alt=0.6 U/L | 31.33419 | platelets stored as 398,000,000 per L against 398 x 10^9/L in the note (the unit tag is L, as in the note, and a factor of 1,000 was lost), and AST and ALT printed in ukat/L were tagged U/L; interval converts 1 ukat/L = 60 U/L |
| 4711 | Maintenance Fluids Calculations | `with a weight of 500 grams` | weight=500.0 g | 2.0 | weight of the resected fetus-in-fetu mass read as the patient's weight; the note gives no patient weight |
| 4943 | Maintenance Fluids Calculations | `The weight of the cyst was around 300 g` | weight=300.0 g | 1.2 | weight of a resected cyst read as the patient's weight; the note gives no patient weight |
| 4981 | Maintenance Fluids Calculations | `The specimen weighted 260 g` | weight=260.0 g | 1.04 | weight of a surgical specimen read as the patient's weight; the note gives no patient weight |
| 5088 | Maintenance Fluids Calculations | `weighed 270 g` | weight=270.0 g | 1.08 | weight of a surgical specimen read as the patient's weight; the note gives no patient weight |
| 5880 | HOMA-IR (Homeostatic Model Assessment for Insulin Resistance) | `insulin level of 21 pmol/l` | Insulin=756.0 pmol/L | 1089.76 | note prints insulin 21 pmol/l; stored 756 pmol/L; no interval because the row's own conversion multiplies pmol/L by 6 where it should divide, the HOMA-IR bug that inflates 32 of 77 training labels 36x (results/homa_ir.csv) |
| 5924 | Free Water Deficit | `weight loss (approximately 30–35 lb)` | weight=3035.0 lbs | -26.54971 | the range of weight lost, 30-35 lb, read as a body weight of 3035 lb; the note gives no body weight |
| 6596 | PERC Rule for Pulmonary Embolism | `heart rate range of 75-90 beats per minute` / `discharged on Leuprolide Depot 11.25 mg injections every three months and norethindrone hormonal therapy` | heart_rate=7590.0 beats per minute; Hormone use=True | 2 | range 75-90 read as 7590, which scores the >=100 criterion; the stored Hormone use=True also fails the question's pre-treatment rule, because the only hormones in the note are given at discharge; with both read from the note, PERC is 0 |
| 6640 | SIRS Criteria | `white blood cell count=6.3×109/L` | wbc=6.3 L | 3 | note prints 6.3 x 10^9/L; the unit tag is L, as in the note, and the x 10^9 was dropped, so the stored 6.3 per L scores the <4,000 criterion |
| 6665 | SIRS Criteria | `The lumbar puncture results showed a pressure of 23 cm·H2O, a white blood cell count of 2` | wbc=2.0 µL | 2 | cerebrospinal fluid white cell count read as blood WBC; the note gives no blood WBC; the label counts a WBC point that rests on the CSF count |
| 6732 | SIRS Criteria | `(white blood cell count – 20)` / `His hematological and biochemical parameters were normal` | wbc=20.0 µL | 4 | cerebrospinal fluid white cell count (20) read as blood WBC, which scores the WBC criterion; the note says his hematological parameters were normal, so the WBC point does not stand and the note supports SIRS 3 against the stored 4; adult SIRS criteria on an 8-year-old is also a questionable task |
| 6801 | SIRS Criteria | `White blood cell count was 6.4×109/L` | wbc=6.4 L | 3 | note prints 6.4 x 10^9/L; the unit tag is L, as in the note, and the x 10^9 was dropped, so the stored 6.4 per L scores the <4,000 criterion |

## train_data.csv: The note prints an impossible unit and the entity copies it (30 rows)

| Row | Calculator | Note text | Stored entity | Stored answer | Why |
|---|---|---|---|---|---|
| 34 | Creatinine Clearance (Cockcroft-Gault Equation) | `creatinine 78 mmol/L` | creatinine=78.0 mmol/L | 0.12759 | note prints creatinine 78 mmol/L; extraction copied it; CrCl label 0.13 mL/min |
| 255 | CKD-EPI Equations for Glomerular Filtration Rate | `1.05 µg/dL` | creatinine=1.05 µg/dL | 540.37042 | note prints creatinine 1.05 µg/dL; GFR label 540 |
| 267 | CKD-EPI Equations for Glomerular Filtration Rate | `Creatinine was 130 mmol/dl` | creatinine=130.0 mmol/dL | 0.00096752 | note prints 130 mmol/dl; GFR label 0.00097 |
| 311 | CKD-EPI Equations for Glomerular Filtration Rate | `creatinine 120 mmol/L` | creatinine=120.0 mmol/L | 0.016671 | note prints 120 mmol/L; GFR label 0.017 |
| 409 | CKD-EPI Equations for Glomerular Filtration Rate | `119 to 270 mmol/L` | creatinine=270.0 mmol/L | 0.0057034 | note prints 270 mmol/L; GFR label 0.0057 |
| 458 | CKD-EPI Equations for Glomerular Filtration Rate | `creatinine 25 mmol/L` | creatinine=25.0 mmol/L | 0.10711 | note prints 25 mmol/L; GFR label 0.11 |
| 467 | CKD-EPI Equations for Glomerular Filtration Rate | `blood creatinine at 127 mmol/L` | creatinine=127.0 mmol/L | 0.011586 | note prints 127 mmol/L; GFR label 0.012 |
| 2533 | Body Mass Index (BMI) | `height: 1.78 cm` | height=(1.78, 'cm') | 220931.70054 | note prints height 1.78 cm; BMI label 220,931.7 |
| 2572 | Calcium Correction for Hypoalbuminemia | `Albumin: 2.5 mg/dL` | albumin=2.5 mg/dL | 14.298 | note prints albumin 2.5 mg/dL; label treats it as 0.0025 g/dL |
| 2593 | Calcium Correction for Hypoalbuminemia | `Albumin 4.3 mg/dL` | albumin=4.3 mg/dL | 12.09656 | note prints albumin 4.3 mg/dL; label treats it as 0.0043 g/dL |
| 2665 | Calcium Correction for Hypoalbuminemia | `Albumin: 3.6 mg/dL` / `Ca2+: 7.0 mEq/L` | albumin=3.6 mg/dL; calcium=7.0 mEq/L | 17.22512 | note prints albumin 3.6 mg/dL; label treats it as 0.0036 g/dL; the note's Ca2+ 7.0 mEq/L is probably also a typo for 7.0 mg/dL (after total thyroidectomy, with numb lips and feet and phosphorus 6.5), so the note supports no single corrected answer |
| 2673 | Calcium Correction for Hypoalbuminemia | `Albumin 3.2 mg/dL` | albumin=3.2 mg/dL | 12.09744 | note prints albumin 3.2 mg/dL; label treats it as 0.0032 g/dL |
| 3175 | MDRD GFR Equation | `creatinine 877 mol/l` | creatinine=877.0 mol/L | 4.7378e-07 | note prints 877 mol/l; MDRD label 4.7e-07 |
| 3211 | MDRD GFR Equation | `creatinine was 1.1 μmol/L` | creatinine=1.1 µmol/L | 11632.92792 | note prints 1.1 µmol/L; MDRD label 11,632.9 |
| 3337 | MDRD GFR Equation | `elevated at 120 mmol/l` | creatinine=120.0 mmol/L | 0.018366 | note prints 120 mmol/l; MDRD label 0.018 |
| 3394 | MDRD GFR Equation | `elevated at 254 mmol/L` | creatinine=254.0 mmol/L | 0.0097267 | note prints 254 mmol/L; MDRD label 0.0097 |
| 3794 | Ideal Body Weight | `height of 155 meters` | height=(155.0, 'm') | 13942.94065 | note prints height 155 meters; IBW label 13,942.9 kg |
| 4368 | Fibrosis-4 (FIB-4) Index for Liver Fibrosis | `blood platelet count of 109,000/L` | platelets=109000.0 L | 26402211.47939 | note prints 109,000/L; FIB-4 label 26,402,211; the quoted labs are from one day after chemotherapy, so the note gives no pre-treatment values either |
| 5439 | Sodium Correction for Hyperglycemia | `sodium 143 mmol/mL` | sodium=143.0 mmol/mL | 143003.312 | note prints sodium 143 mmol/mL; label 143,003.3 |
| 5564 | Serum Osmolality | `glucose 61 g/dL` / `urea 102.72 mg/dL` | glucose=61.0 g/dL; bun=102.72 mg/dL | 3683.5746 | note prints glucose 61 g/dL, an impossible unit the label copied (osmolality label 3,683.6); separately, the note's urea 102.72 mg/dL was stored as BUN, which would be about 48 mg/dL, so a second input is wrong too; counted once, as a copied typo, because the impossible label comes from the glucose unit |
| 5768 | Serum Osmolality | `fasting blood sugar: 90 mmol/dL` | glucose=90.0 mmol/dL | 1171.44286 | note prints 90 mmol/dL; osmolality label 1,171.4; the row's explanation prints the equation 2 * 133.0 + (13.0 / 2.8) + (13.0 / 18), which evaluates to 271.37, not the stored 1,171.44 |
| 6171 | Anion Gap | `sodium of 136 mmol/dl` | sodium=136.0 mmol/dL | 1230.0 | note prints sodium 136 mmol/dl; anion gap label 1230 |
| 6660 | SIRS Criteria | `White blood cell count was 11.6 cells/microL` | wbc=11.6 µL | 3 | note prints 11.6 cells/microL; label counts it as <4,000 |
| 8473 | Delta Gap | `sodium of 136 mmol/dl` | sodium=136.0 mmol/dL | 1218.0 | same note as row 6171; delta gap label 1218 |
| 8678 | Delta Ratio | `sodium of 136 mmol/dl` | sodium=136.0 mmol/dL | -609.0 | same note as row 6171; delta ratio label -609 |
| 8853 | Delta Ratio | `serum sodium 124 mEq/mL` | sodium=124.0 mEq/mL; chloride=89.0 mEq/mL; bicarbonate=15.0 mEq/mL | -1.33467 | note prints all three electrolytes in mEq/mL; delta ratio label -1.33 where the mEq/L reading gives 0.89 |
| 8935 | Albumin Corrected Anion Gap | `Albumin: 2.5 mg/dL` | albumin=2.5 mg/dL | 18.99375 | same note as row 2572 |
| 8980 | Albumin Corrected Delta Gap | `Albumin: 2.5 mg/dL` | albumin=2.5 mg/dL | 6.99375 | same note as row 2572 |
| 8997 | Albumin Corrected Delta Ratio | `S.albumin 3.2 mg/dl` | albumin=3.2 mg/dL | -0.18173 | note prints albumin 3.2 mg/dl |
| 9027 | Albumin Corrected Delta Ratio | `Albumin: 2.5 mg/dL` | albumin=2.5 mg/dL | -3.49688 | same note as row 2572 |

## test_data.csv: The note prints an impossible unit and the entity copies it (1 rows)

| Row | Calculator | Note text | Stored entity | Stored answer | Why |
|---|---|---|---|---|---|
| 877 | Albumin Corrected Delta Ratio | `Albumin 3.5 mg/ dL` | albumin=3.5 mg/dL | 5.49563 | note prints albumin 3.5 mg/dL; label treats it as 0.0035 g/dL |

## HOMA-IR: pmol/L insulin is multiplied by 6 instead of divided

arXiv 2603.02222 lists this bug, and PR #5 (artuskg) proposed the one-line fix in February 2026. It was closed without merging, so 32 of 77 training labels in v1.0.8 still carry it.

32 of the 77 HOMA-IR rows in train_data.csv give insulin in pmol/L. The explanation converts it with "* 6 µIU/mL/pmol/L" (calculator_implementations/homa_ir.py). About 6 pmol/L make 1 µIU/mL, so the conversion should divide, and each of these labels is 36 times too large. For example, row 9797 has insulin 55 pmol/L and a stored answer of 76.3343; dividing gives about 2.12. Only row 5880 is also in the tables above. Rows: 5880, 9797, 9801, 9805, 9806, 9811, 9814, 9815, 9818, 9820, 9822, 9823, 9826, 9827, 9829, 9832, 9833, 9836, 9838, 9839, 9840, 9845, 9847, 9849, 9850, 9852, 9855, 9856, 9857, 9861, 9862, 9864.
