.PHONY: test test-fast test-tab test-domain test-adapters test-cov lint typecheck setup check

# ── Iteration targets (fast, no coverage) ────────────────────────────────────

test-fast:
	pytest tests/ -q -n auto --tb=short

# Usage: make test-tab tab=risk  |  make test-tab tab=weekly_brief
test-tab:
	pytest tests/ -q -n auto -m "tab_$(tab)" --tb=short

test-domain:
	pytest tests/domain/ -q -n auto --tb=short

test-adapters:
	pytest tests/adapters/ -q -n auto --tb=short

# ── Full suite, no coverage ───────────────────────────────────────────────────

test:
	pytest tests/ -n auto --tb=short

# ── Coverage gate (CI + pre-PR only) ─────────────────────────────────────────

test-cov:
	pytest tests/ -n auto \
	    --cov=domain --cov=adapters --cov=application \
	    --cov-fail-under=90 --tb=short

# ── Quality checks ────────────────────────────────────────────────────────────

lint:
	pre-commit run --all-files

typecheck:
	mypy domain/ adapters/ application/ --strict

# ── Full gate — CI and pre-PR only, NOT during iteration ─────────────────────

check: lint typecheck test-cov

# ── Environment setup ─────────────────────────────────────────────────────────

setup:
	uv sync
	pre-commit install
