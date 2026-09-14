.PHONY: install migrate seed run test lint typecheck format-check django-check check

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

format-check:
	uv run ruff format --check .

django-check:
	uv run python manage.py check
	uv run python manage.py makemigrations --check --dry-run

check: lint format-check typecheck test django-check
