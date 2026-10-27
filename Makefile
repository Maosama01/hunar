# Hunar: one command entry points. Run `make help` for the list.
UV := $(shell command -v uv 2>/dev/null || echo $(HOME)/Library/Python/3.13/bin/uv)
PY := $(UV) run python
NPM := npm --prefix frontend

.PHONY: help setup data parse test lint eval eval-m1 eval-m2 study results seed api web demo report clean

help:
	@echo "setup    install Python 3.11 env (uv) and frontend packages"
	@echo "data     download official QP PDFs from nqr.gov.in and parse them to JSON"
	@echo "test     run the test suite"
	@echo "eval     run M1 mapper and M2 hashing evaluations -> experiments/*.json"
	@echo "study    analyse M4 rater data -> experiments/m4_*.json and figures"
	@echo "results  rebuild the README results table from experiments/*.json"
	@echo "seed     load the clearly labelled sample worker into the local database"
	@echo "demo     seed, then start the API (:8000) and the web app (:5173)"
	@echo "report   build docs/report/Hunar_Report.docx from the Markdown draft"

setup:
	$(UV) python install 3.11
	$(UV) sync
	cd frontend && npm install

data:
	$(PY) scripts/fetch_qps.py
	$(PY) -m hunar.mapper.qp_parser

parse:
	$(PY) -m hunar.mapper.qp_parser

test:
	$(UV) run pytest -m "not slow"

test-all:
	$(UV) run pytest

lint:
	$(UV) run ruff check backend tests scripts

eval: eval-m1 eval-m2 results

eval-m1:
	$(PY) -m hunar.mapper.evaluate

eval-m2:
	$(PY) -m hunar.evidence.eval_hashing

study:
	$(PY) -m hunar.study.analyse

results:
	$(PY) scripts/build_results_table.py

seed:
	$(PY) -m hunar.api.seed

api:
	$(UV) run uvicorn hunar.api.main:app --reload --port 8000

web:
	$(NPM) run dev

demo: seed
	@echo "Starting API on :8000 and web app on :5173 (Ctrl+C stops both)"
	$(UV) run uvicorn hunar.api.main:app --port 8000 & $(NPM) run dev; kill %1

report:
	$(PY) scripts/build_report.py

clean:
	rm -rf .pytest_cache .ruff_cache frontend/dist data/hunar.db
