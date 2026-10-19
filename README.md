# labelgate

A check for training labels that are wrong given the source text they came from: an input misread from the text, or a typo the text itself prints, copied into the input. Re-running the formula cannot catch this kind of error, because the formula is applied correctly to the wrong input.

It was built on MedCalc-Bench Verified (release v1.0.8, commit 58fc3de). An open audit (PR #7 on the Verified repo) re-runs every training row's calculator on its extracted inputs and reports 0 mismatches in train_data.csv. This repo's re-implementation of 15 renal, electrolyte and blood-pressure formulas agrees: 0 mismatches on 3,794 Verified training rows, against 27 on the same rows of v1.2. Row Number 1337 still stores a mean arterial pressure of 55,446.67 mmHg, because the note says "150-160/80-90 mmHg" and the extracted inputs say 150160 and 8090.

Reading the 194 flagged training rows against their notes finds at least 52 of 10,538 training labels wrong given their notes: 22 misread from the note, 30 copying a typo the note itself prints. Only flagged rows were read, so 52 is a floor, not an error rate. On a second check, 4 of the 9 unclear rows (6414, 6639, 6653, 6769) also look like the same patterns, and they are not in the 52.

Cheap screens find almost all of them. A 100x-from-median outlier screen (G4 below) flags 47 of the 52, the diastolic-above-systolic rule (G3) adds 1 for 48, and plain range checks on heart rate and weight add 3 more for 51 (row 2807 stores a heart rate of 4050, row 5924 a weight of 3,035 lb). The range bounds were picked after the defects were known. What reading each row against its note adds is the cause and the answer the note supports: row 2807's note says "pulse 40-50 bpm", so the label should score that criterion 0, not 1.5. That decides whether a row gets relabeled, dropped, or traced back to a calculator bug.

One such bug: the HOMA-IR calculator multiplies pmol/L insulin by 6 where it should divide, so 32 of the 77 HOMA-IR training labels are 36 times too large (`results/homa_ir.csv`). 31 of those 32 are outside the 52. arXiv 2603.02222 lists this bug, and PR #5 (artuskg) proposed the one-line fix in February 2026. It was closed without merging, so 32 of 77 training labels in v1.0.8 still carry it.

The maintainer's v1.0.8 release notes (2026-09-08) report 0 audit mismatches across all 11,693 rows, and commits 3df69cf and 192a585 fixed notes that contradicted their own entities: 8 sodium rows and the fentanyl units. None of the rows here is among them.

`results/fix_list.csv` is the list to act on, 84 rows under one rule: relabel the 11 whose note gives the inputs, drop the 41 with no note-supported answer (30 train and 1 test copied typos, 10 extraction rows), and fix the HOMA-IR calculator and regenerate its 32 rows (including 5880). It is a filtered view of `results/handcheck.csv` and `results/homa_ir.csv`, rebuilt by `make report`.

Current counts are in `results/results_table.csv`. Dev read every defect and unclear row (62 in all) against its note on 2026-10-18 and agreed with each call. See "Status".

## Rerun

```
make data     # download the four pinned CSVs and check their sha256
make gate     # run the checks, draw samples, write results/, examples/ and upstream/ISSUE.md
make report   # rebuild results/fix_list.csv and report.html from results/
make test
```

`make models` runs the model phases on three models of different sizes with the command in `scripts/run_models.py`. Every response is cached in `raw/`, so a rerun costs nothing. The runner stops at 390 calls and stops at once on an authentication error.

The Makefile uses `python3` and puts this folder on `PYTHONPATH`. To run a script directly, run it from this folder with `PYTHONPATH=.` in front (for example `PYTHONPATH=. python3 scripts/show_row.py ver_train 1337`), or `pip install -e .` first. The library uses only the standard library. The tests need a Python with pytest; if `python3` lacks it, pass one that has it, as in `make test PY=/path/to/venv/bin/python`.

## The four checks

- G1 recompute. 15 reference formulas (CKD-EPI 2021, MDRD, Cockcroft-Gault, FENa, anion gap, delta gap, delta ratio, the three albumin-corrected versions, serum osmolality, free water deficit, sodium correction, calcium correction, MAP), each written from the formula the row's own explanation states, with the source cited in the docstring. It is expected to agree with the stored labels, which shows the remaining errors sit in the inputs.
- G2 grounding. Every numeric input has to appear in the note as a number, allowing a power of ten for unit rescaling. An input whose digits equal two note numbers joined across a hyphen is reported as a merged range. `grounding.check(task, formats=True)` also reads decimal commas, space thousands separators and lost superscripts; the report gives its precision on a held-out half, but every headline count uses the original reader.
- G3 definitions. Diastolic pressure no greater than systolic, and a MAP between the two.
- G4 dataset outliers. A nonzero label, or an input in its canonical unit, more than 100 times away from the median of the same field in the same file. Groups with fewer than 5 values are skipped, since their median means nothing.

G2 has known blind spots: it cannot see a negative input, a 10x or 100x decimal slip (it accepts any power of ten from 10^-3 to 10^3), or a range written with "to" instead of a hyphen.

A flag is a row to read. A row counts as a defect only after someone quotes the note span that contradicts the input.

## Folders

- `labelgate/` the library: the Task schema, the four checks, the reference formulas, unit conversion, and adapters for MedCalc-Bench CSVs and JSONL.
- `scripts/` the pipeline, one script per step, plus `show_row.py` to print a row with its note context for review.
- `results/` every table the report reads, plus `fix_list.csv`.
- `examples/` five worked examples with the note span, the extracted input, the stored label, the recompute and what the note supports.
- `upstream/ISSUE.md` a draft issue for the Verified maintainers. It has not been filed.
- `tests/` formula, check and hand-check tests.

## Hand-check

`results/handcheck.csv` has one line per flagged row: the checks that fired, the decision (defect, not a defect, unclear), the defect type, the exact quoted note text, the stored input and label, the note-supported inputs as JSON, any assumption the interval makes, and a reason. `tests/test_handcheck.py` asserts that every quote is a literal substring of that row's note and that every flagged row has an entry.

A defect is either an extraction defect (the input contradicts the note) or a copied source typo (the note itself prints an impossible unit, and the input copies it). It counts only when correcting the input changes the label or leaves the task with no answer. For copied typos the repo reports only what the stored label rewards. Rows where the note gives no unit, never states the input, or where the corrected label is unknown are marked unclear and left out of the counts.

Each flagged row has a first-pass call and reason. Dev then read every defect and unclear row against its note on 2026-10-18 and agreed with each call; the 144 rows called not a defect keep their first-pass call. Some calls are clinical reads: a cerebrospinal fluid cell count read as blood WBC, a pressure taken on pressors read as an admission value, a resected mass's weight read as the patient's. No clinician has read them, and the report lists those rows so one can overrule them. `PYTHONPATH=. python3 scripts/show_row.py ver_train <row>` prints a row with its note context for that pass, and `--flagged` prints every flagged row.

## Point it at your own tasks

Write one JSON object per line:

```json
{"id": "t1", "source_text": "BP 150-160/80-90 mmHg.", "fields": {"sbp": [150160, "mm hg"], "dbp": [8090, "mm hg"]}, "label": 55446.67, "formula": "mean_arterial_pressure", "calculator": "MAP"}
```

Then run `PYTHONPATH=. python3 scripts/check_tasks.py tasks.jsonl`. `formula`, `tolerance` (default 0.05) and `calculator` are optional. Without a formula a task still gets G2, G3 and G4. `calculator` names the group G4 takes its label medians over; without it, tasks are grouped by formula. The reader is `labelgate/adapters/jsonl.py`.

Each row is checked when it is read. The script prints, with the line number and reason, every row it rejects: a field that is not a `[value, unit]` pair, a number with no unit, a negative, NaN or infinite number, a label that is not a number, a sex that is not male or female, or an unknown formula name. It also prints every task whose formula could not be recomputed, so a skipped check is never reported as clean. Sex is normalized to Male or Female, and unit case is normalized (`mmol/l` reads as `mmol/L`).

This has been run on MedCalc-Bench, the three-line fixture in `tests/fixtures/` and the malformed rows in `tests/test_checks.py`. It has not been tested on FHIR resources or any other format, and G4 needs at least 5 tasks per calculator to say anything.

## Model prompts

The calculation prompt is the `zero_shot` system and user strings from MedCalc-Bench's `evaluation/run.py`, copied verbatim into `labelgate/prompts.py`. Answers are parsed with a port of that file's `extract_answer`, with two changes: an answer written as `str(...)` is not evaluated, because the original calls `eval` on model output, and a percent sign is not divided by 100, because FENa labels are themselves in percent.

## Status

The `reviewer` column of `results/handcheck.csv` says who checked each call. The 53 defect rows and 9 unclear rows read "confirmed by Dev 2026-10-18"; the 144 not-a-defect rows are still first-pass calls. The report shows a draft notice while any defect or unclear row is unconfirmed, so it shows none now.

No model call has completed. On 2026-10-17 and 2026-10-18 the model command line on this machine returned "OAuth session expired and could not be refreshed". Log in once in a terminal, then run `make models`.

## Data and license

Both datasets are CC-BY-SA 4.0. `data/` is not committed; `make data` downloads it from pinned Hugging Face commits.
