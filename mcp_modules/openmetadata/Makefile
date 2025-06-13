.PHONY: run run-sse build publish

run:
	uv run python src

run-sse:
	uv run python src --transport sse

lint:
	uv run ruff check src --fix

format:
	uv run ruff format src

build:
	rm -r dist
	uv run python -m build

publish:
	uv run python -m twine upload --config-file .pypirc dist/*
