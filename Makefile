.DEFAULT_GOAL := run

PORT ?= 8050

.PHONY: help install run test lint check

help: ## Show available targets
	@grep -E '^[a-z]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}'

install: ## Install dependencies (safe to re-run)
	poetry install --with dev

run: install ## Start the app at http://127.0.0.1:$(PORT) (default target)
	poetry run lab-timeseries-grapher --port $(PORT)

test: install ## Run the test suite
	poetry run pytest

lint: install ## Lint the code
	poetry run ruff check src tests

check: lint test ## Lint and test
