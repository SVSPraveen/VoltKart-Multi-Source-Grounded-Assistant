# Makefile for VoltKart Multi-Source Chat Assistant
# Cross-platform: delegates directly to scripts/runner.py

.PHONY: help setup dev verify test golden lint format no-hardcode variants clean eval e2e fresh-clone-test

# Detect python executable
ifeq ($(OS),Windows_NT)
    VENV_PYTHON := .venv/Scripts/python.exe
else
    VENV_PYTHON := .venv/bin/python
endif

PYTHON := $(if $(wildcard $(VENV_PYTHON)),$(VENV_PYTHON),python)

help:
	@echo "Available commands:"
	@echo "  make setup            - Install requirements into virtualenv"
	@echo "  make dev              - Start development server"
	@echo "  make verify           - Run verification suite, print summary table, write report"
	@echo "  make test             - Run unit tests"
	@echo "  make golden           - Run golden evaluation tests"
	@echo "  make lint             - Run Ruff linting"
	@echo "  make format           - Run Ruff code formatter"
	@echo "  make no-hardcode      - Run sample entity hardcoding scan"
	@echo "  make variants         - Generate full variant bundle"
	@echo "  make clean            - Remove cache artifacts"

setup:
	$(PYTHON) -m pip install -r requirements.txt

dev:
	$(PYTHON) scripts/runner.py dev

verify:
	$(PYTHON) scripts/runner.py verify

test:
	$(PYTHON) scripts/runner.py test

golden:
	$(PYTHON) scripts/runner.py golden

lint:
	$(PYTHON) scripts/runner.py lint

format:
	$(PYTHON) scripts/runner.py format

no-hardcode:
	$(PYTHON) scripts/runner.py no-hardcode

variants:
	$(PYTHON) tests/variants/make_variant.py --preset full_variation --output evaluation/variant_bundle

clean:
	$(PYTHON) scripts/runner.py clean

eval:
	$(PYTHON) scripts/runner.py eval

e2e:
	$(PYTHON) scripts/runner.py e2e

fresh-clone-test:
	$(PYTHON) scripts/runner.py fresh-clone-test
