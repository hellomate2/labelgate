PY ?= python3
export PYTHONPATH := $(CURDIR)

.PHONY: data gate models report test

data:
	scripts/fetch_data.sh

gate: data
	$(PY) scripts/run_gate.py
	$(PY) scripts/sample.py
	$(PY) scripts/score.py
	$(PY) scripts/write_examples.py
	$(PY) scripts/write_issue.py

models:
	$(PY) scripts/run_models.py all
	$(PY) scripts/score.py
	$(PY) scripts/write_examples.py

report:
	$(PY) scripts/fix_list.py
	$(PY) scripts/build_report.py

test:
	$(PY) -m pytest -q tests
