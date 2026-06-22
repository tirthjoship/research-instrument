.PHONY: test test-fast test-tab test-domain test-adapters test-smoke test-cov lint typecheck setup check

PYTEST := uv run pytest

# ── Iteration targets (fast, no coverage) ────────────────────────────────────

test-fast:
	$(PYTEST) tests/ -q -n auto --tb=short

# Usage: make test-tab tab=risk  |  make test-tab tab=weekly_brief
test-tab:
	@[ -n "$(tab)" ] || { echo "Usage: make test-tab tab=<name>  (e.g. tab=risk)"; exit 1; }
	$(PYTEST) tests/ -q -n auto -m "tab_$(tab)" --tb=short

test-domain:
	$(PYTEST) tests/domain/ -q -n auto --tb=short

test-adapters:
	$(PYTEST) tests/adapters/ -q -n auto --tb=short

test-smoke:
	$(PYTEST) tests/ -q -n auto -m smoke --tb=short

# ── Full suite, no coverage ───────────────────────────────────────────────────

test:
	$(PYTEST) tests/ -n auto --tb=short

# ── Coverage gate (CI + pre-PR only) ─────────────────────────────────────────

test-cov:
	$(PYTEST) tests/ -n auto \
	    --cov=domain --cov=adapters --cov=application \
	    --cov-fail-under=90 --tb=short

# ── Quality checks ────────────────────────────────────────────────────────────

lint:
	pre-commit run --all-files

typecheck:
	uv run mypy domain/ adapters/ application/ --strict

# ── Full gate — CI and pre-PR only, NOT during iteration ─────────────────────

check: lint typecheck test-cov

# ── Environment setup ─────────────────────────────────────────────────────────

setup:
	uv sync
	pre-commit install
