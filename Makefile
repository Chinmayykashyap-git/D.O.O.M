.PHONY: help eval eval-holdout frontend demo demo-offline verify e2e

help:
	@echo "Targets: eval eval-holdout frontend demo demo-offline verify e2e"

eval: eval-holdout
	python -m doom.evaluation

eval-holdout:
	python -m doom.holdout_eval

frontend:
	npm --prefix frontend run build

demo: eval frontend
	python -m doom.demo

demo-offline:
	python -m doom.offline_demo

e2e: frontend
	python -m doom.e2e

verify: eval frontend
	python -m ruff check doom holdout_attacks tests
	python -m mypy doom holdout_attacks
	npm --prefix frontend test
	python -m doom.demo --no-server
	python -m pytest
	python -m doom.e2e
	python -m pytest -k detector_import_graph
	python -m pytest -k holdout_families_are_isolated
	python -m pytest -k multiseed_metrics_meet_regression_targets
