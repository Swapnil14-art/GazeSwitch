SRC = trackers evaluation

.PHONY: all format lint check run-eval

all: format

format:
	@echo Formatting source files...
	@autoflake --remove-all-unused-imports --recursive --in-place $(SRC)
	@isort $(SRC)
	@black $(SRC)

lint:
	@echo Linting source files...
	@flake8 $(SRC)

run-eval:
	@echo Running evaluation...
	@python -m evaluation.run_evaluation $(ARGS)

check: format lint
