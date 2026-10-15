.PHONY: sync native test lint typecheck ci
sync:
	uv sync --group dev

native:
	bash scripts/build-native.sh

test:
	uv run pytest -q

lint:
	uv run ruff check src tests

typecheck:
	uv run mypy src/falcon

ci: lint typecheck test
