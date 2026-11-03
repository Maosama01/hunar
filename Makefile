# Hunar: one command entry points. Run `make help` for the list.
UV := $(shell command -v uv 2>/dev/null || echo $(HOME)/Library/Python/3.13/bin/uv)
PY := $(UV) run python
NPM := npm --prefix frontend

DL ?= $(HOME)/Downloads
CSV ?= data/study/items.csv

.PHONY: help setup data parse test lint eval eval-m1 eval-m2 study results seed api web demo report clean \
        vision voice eval-voice import-detector ppe-split notebook design-sim study-items bench \
        quiz-sim quiz-calibrate translate staff

help:
	@echo "setup    install Python 3.11 env (uv) and frontend packages"
	@echo "data     download official QP PDFs (nqr.gov.in) + PPE test images; parse QPs"
	@echo "test     run the test suite"
	@echo "eval     run M1 mapper and M2 hashing evaluations -> experiments/*.json"
	@echo "study    analyse M4 rater data -> experiments/m4_*.json and figures"
	@echo "results  rebuild the README results table from experiments/*.json"
	@echo "seed     load the clearly labelled sample worker into the local database"
	@echo "demo     seed, then start the API (:8000) and the web app (:5173)"
	@echo "report   build docs/report/Hunar_Report.docx from the Markdown draft"
	@echo "vision   install YOLO (ultralytics) for detector inference on the laptop"
	@echo "voice    install faster-whisper for spoken declarations"
	@echo "eval-voice  voice pipeline check on SYNTHETIC text-to-speech audio (macOS) -> experiments/"
	@echo "design-sim  M4 study sizing: SIMULATION OF THE METHOD -> experiments/m4_design_simulation.json"
	@echo "study-items load consented study photos for rater mode (CSV=data/study/items.csv)"
	@echo "import-detector  bring Colab results back (newest m2_detector*.json, best*.pt in DL=~/Downloads)"
	@echo "ppe-split  class balance of published vs re-split PPE data -> experiments/m2_ppe_split.json"
	@echo "notebook   regenerate the Colab notebook (embeds hunar/evidence/ppe_split.py)"
	@echo "quiz-sim   quiz design check: SIMULATION OF THE METHOD -> experiments/quiz_cat_simulation.json"
	@echo "quiz-calibrate  re-estimate quiz difficulties from real answers (RESULT PENDING until enough)"
	@echo "translate  machine-translate UI + quiz into 22 languages with Bhashini (needs BHASHINI_* env)"
	@echo "staff      create a staff account: make staff ROLE=assessor PHONE=98xxxxxxxx NAME='...'"
	@echo "bench      CPU speed + memory per photo, declaration and second of audio -> experiments/bench_cpu.json"

setup:
	$(UV) python install 3.11
	$(UV) sync
	cd frontend && npm install

data:
	$(PY) scripts/fetch_qps.py
	$(PY) -m hunar.mapper.qp_parser
	$(PY) scripts/fetch_ppe_test.py

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

# --inexact keeps the other optional extra installed.
vision:
	$(UV) sync --extra vision --inexact

voice:
	$(UV) sync --extra voice --inexact

eval-voice:
	$(PY) -m hunar.speech.evaluate
	$(PY) scripts/build_results_table.py

design-sim:
	$(PY) -m hunar.study.design_sim

study-items:
	$(PY) -m hunar.study.items "$(CSV)"

# Newest matching downloads (browsers rename repeats to "name (1).ext").
DET_JSON = $(shell ls -t "$(DL)"/m2_detector*.json 2>/dev/null | head -1)
DET_PT = $(shell ls -t "$(DL)"/best*.pt 2>/dev/null | head -1)
DET_CM = $(shell ls -t "$(DL)"/confusion_matrix*.png 2>/dev/null | head -1)

import-detector:
	$(PY) scripts/import_detector_results.py --json "$(DET_JSON)" --weights "$(DET_PT)" \
		$(if $(DET_CM),--confusion "$(DET_CM)",)

ppe-split:
	$(PY) scripts/fetch_ppe_test.py train valid test
	$(PY) scripts/ppe_split_report.py

notebook:
	$(PY) scripts/make_colab_notebook.py

clean:
	rm -rf .pytest_cache .ruff_cache frontend/dist data/hunar.db

# WEIGHTS defaults to the trained detector; WEIGHTS=<path to yolov8n.pt> times the same-size COCO model.
bench:
	$(PY) scripts/bench_cpu.py $(if $(WEIGHTS),--weights "$(WEIGHTS)",)

quiz-sim:
	$(PY) -m hunar.quiz.simulate
	$(PY) scripts/build_results_table.py

quiz-calibrate:
	$(PY) -m hunar.quiz.calibrate

translate:
	$(PY) scripts/translate.py

staff:
	$(PY) -m hunar.accounts.cli create --role "$(ROLE)" --phone "$(PHONE)" --name "$(NAME)"
