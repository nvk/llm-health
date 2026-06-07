PYTHON ?= /opt/homebrew/bin/python3.11
VENV := .venv
BIN := $(VENV)/bin

.PHONY: venv install install-v2 test lint verify package clean

venv:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install --upgrade pip setuptools wheel

install: venv
	$(BIN)/python -m pip install '.[dev]'

install-v2: venv
	$(BIN)/python -m pip install '.[dev,v2]'

test:
	$(BIN)/pytest -q

lint:
	$(BIN)/ruff check .

verify:
	$(BIN)/python -m compileall -q src
	$(BIN)/pytest -q
	$(BIN)/ruff check .
	./scripts/verify-privacy.sh

package: verify
	$(BIN)/python -m build --wheel --sdist

clean:
	rm -rf build dist *.egg-info src/*.egg-info .pytest_cache .ruff_cache
