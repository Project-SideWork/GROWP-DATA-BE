.PHONY: install run test lint format typecheck check

install:
	python3 -m venv .venv
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install -e ".[dev]"

run:
	.venv/bin/uvicorn app.main:app --app-dir src --reload

test:
	.venv/bin/pytest

lint:
	.venv/bin/ruff check .

format:
	.venv/bin/ruff format .
	.venv/bin/ruff check --fix .

typecheck:
	.venv/bin/mypy

check: lint typecheck test

