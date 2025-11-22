SRC = trackers evaluation tests

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

test:
	@echo Running tests...
	@python -m pytest -p no:warnings tests/

run-eval:
	@echo Running evaluation...
	@python -m evaluation.run_evaluation $(ARGS)

check: format lint
