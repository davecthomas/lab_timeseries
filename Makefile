.DEFAULT_GOAL := run

PORT ?= 8050

.PHONY: help install run stop test lint check

help: ## Show available targets
	@grep -E '^[a-z]+:.*## ' $(MAKEFILE_LIST) \
		| awk -F ':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}' \
		| sed 's/[$$][(]PORT[)]/$(PORT)/g'

install: ## Install dependencies (safe to re-run)
	poetry install --with dev

stop: ## Stop whatever is serving $(PORT)
	@pids=$$(lsof -ti :$(PORT) 2>/dev/null); \
	if [ -n "$$pids" ]; then \
		echo "Stopping process on port $(PORT): $$pids"; \
		kill $$pids 2>/dev/null || true; \
		for i in 1 2 3 4 5 6 7 8 9 10; do \
			sleep 0.3; \
			[ -z "$$(lsof -ti :$(PORT) 2>/dev/null)" ] && break; \
		done; \
		remaining=$$(lsof -ti :$(PORT) 2>/dev/null); \
		if [ -n "$$remaining" ]; then \
			echo "Process $$remaining ignored SIGTERM; sending SIGKILL"; \
			kill -9 $$remaining 2>/dev/null || true; \
			sleep 0.5; \
		fi; \
	fi

# Reclaim the port first: otherwise a stale server keeps serving the old code
# while this run exits with "Address already in use".
run: install stop ## Start the app at http://127.0.0.1:$(PORT) (default target)
	poetry run lab-timeseries-grapher --port $(PORT)

test: install ## Run the test suite
	poetry run pytest

lint: install ## Lint the code
	poetry run ruff check src tests

check: lint test ## Lint and test
