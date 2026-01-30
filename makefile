SRC = trackers evaluation tests core system_platform ui main.py 

.PHONY: all format lint check run-eval test_metrics

all: check

format:
	@echo Formatting source files...
	@ruff check --fix $(SRC)
	@ruff format $(SRC)

lint:
	@echo Linting source files...
	@ruff check $(SRC)

test:
	@echo Running tests...
	@python -m pytest -p no:warnings tests/

run-eval:
	@echo Running evaluation...
	@python -m evaluation.run_evaluation $(ARGS)

check: format lint test

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
	--add-data "media/icon.png;media" \
	--name GazeControl \
	main.py