SRC = trackers evaluation tests core system_platform ui main.py 

.PHONY: all format lint check run-eval test_metrics

all: format

format:
	@echo Formatting source files...
	@autoflake --remove-all-unused-imports --recursive --in-place $(SRC)
	@isort --profile black $(SRC)
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

clean:
	@rmdir /s /q build dist
	@del /q GazeControl.spec

build:
	@echo Building exe...
	@pyinstaller --clean --noconsole --onefile \
	--hidden-import=eyetrax.gaze \
	--hidden-import=eyetrax.calibration \
	--collect-data mediapipe \
	--collect-submodules eyetrax \
	--name GazeControl \
	main.py