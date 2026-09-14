.PHONY: install migrate seed run test lint typecheck check

install:
	uv sync --dev

migrate:
	uv run python manage.py migrate

seed:
	uv run python manage.py seed_demo

run:
	uv run python manage.py runserver

test:
	uv run pytest

lint:
	uv run ruff check .

typecheck:
	uv run mypy config orders

check: lint typecheck test
