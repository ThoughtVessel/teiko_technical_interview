# python3 exists on both Codespaces and macOS; bare `python` does not.
PYTHON ?= python3
PIP ?= $(PYTHON) -m pip

.PHONY: setup pipeline dashboard clean

setup:
	$(PIP) install -r requirements.txt

pipeline:
	$(PYTHON) load_data.py
	$(PYTHON) run_analysis.py

dashboard:
	$(PYTHON) app.py

clean:
	rm -f cell_count.db
	rm -rf outputs __pycache__
