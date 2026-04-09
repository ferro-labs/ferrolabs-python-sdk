.PHONY: install test lint format build clean

install:
	pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check ferrolabsai tests
	mypy ferrolabsai

format:
	ruff format ferrolabsai tests

build:
	python3 -m build

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache
