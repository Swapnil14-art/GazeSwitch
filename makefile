SRC = trackers tests core system_platform ui main.py 

.PHONY: all format lint check

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

check: format lint test

clean:
ifeq ($(OS),Windows_NT)
	@rmdir /s /q build dist
	@del /q GazeControl.spec
endif

build:
	@echo Building exe/app...
ifeq ($(OS),Windows_NT)
	@ # Windows
	@pyinstaller --clean --noconsole --onefile \
		--hidden-import=eyetrax.gaze \
		--hidden-import=eyetrax.calibration \
		--collect-data mediapipe \
		--collect-submodules eyetrax \
		--add-data "media/icon.png;media" \
		--add-data "media/icon.ico;media" \
		--icon "media/icon.ico" \
		--name GazeControl \
		main.py 
endif