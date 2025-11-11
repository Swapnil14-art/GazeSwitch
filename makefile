SRC = trackers evaluation main.py

.PHONY: all format lint check

all: format

format:
	autoflake --remove-all-unused-imports --recursive --in-place $(SRC)
	isort $(SRC)
	black $(SRC)

lint:
	flake8 $(SRC)

check: format lint
