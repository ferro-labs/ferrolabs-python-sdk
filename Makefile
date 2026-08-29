.PHONY: install test lint format build contract clean

install:
	pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check ferrolabsai tests
	ruff format --check ferrolabsai tests
	mypy ferrolabsai

format:
	ruff format ferrolabsai tests

build:
	python3 -m build

# Boots a real ai-gateway (FERRO_GATEWAY_SOURCE, default ../ai-gateway) against
# the stub upstream and runs tests/contract. Needs go and curl on PATH.
contract:
	./scripts/with-gateway.sh

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache
