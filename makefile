SRC = trackers evaluation

.PHONY: all format lint check run-eval test_metrics

all: format

format:
	@echo Formatting source files...
	@autoflake --remove-all-unused-imports --recursive --in-place $(SRC)
	@isort $(SRC)
	@black $(SRC)

lint:
	@echo Linting source files...
	@flake8 $(SRC)

test_metrics:
	@echo Running tests...
	@pytest evaluation/test_metrics.py

run-eval:
	@echo Running evaluation...
	@python -m evaluation.run_evaluation $(ARGS)

check: format lint
