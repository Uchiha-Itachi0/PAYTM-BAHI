# BAHI
#
# Versions are pinned. On the day we have 5.5 hours and cannot spend any of
# them on a tool that changed its output overnight.

.PHONY: help db db-migrate db-check rhythm decide expire voice voice-list \
        api web web-check check lint typecheck test

help:
	@echo "db           drop, migrate and seed. one shop, 60 udhaar customers, 6 months"
	@echo "db-migrate   apply pending migrations, keep the data"
	@echo "db-check     read the seed back in SQL and print what it contains"
	@echo ""
	@echo "rhythm       CUSTOMER=sharma - his own gap, and the working behind it"
	@echo "decide       tonight's hold/send list, with the reason for each"
	@echo "expire       what has passed the limitation line, and what is about to"
	@echo ""
	@echo "api          the service on :8000"
	@echo "web          the two surfaces on :3000"
	@echo ""
	@echo "voice        render the demo lines to disk. needs SARVAM_API_KEY"
	@echo "voice-list   what is already in the offline cache"
	@echo ""
	@echo "check        ruff, ruff format, mypy strict, pytest"
	@echo "web-check    tsc, eslint, vitest"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

# Drops the schema and rebuilds from scratch, then writes contract/shop.json from
# what it built. Safe by design: the seed is deterministic, so there is never
# anything in here worth preserving. Creates the database on a fresh machine.
db:
	@createdb bahi 2>/dev/null || true
	cd api && uv run python -m data.migrate --reset
	cd api && uv run python -m data.generate

db-migrate:
	cd api && uv run python -m data.migrate

db-check:
	cd api && uv run python -m data.check

# ---------------------------------------------------------------------------
# The engine, each piece runnable on its own
# ---------------------------------------------------------------------------

# One person's own rhythm: the median gap between his settled entries, how many
# we computed it from, and whether today sits inside it. Arithmetic, printed.
rhythm:
	cd api && uv run python -m bahi.rhythm $(or $(CUSTOMER),sharma)

# Tonight's decision for every open entry - hold or send, at what hour, and the
# figures behind it. The count of who is being left alone is the point.
decide:
	cd api && uv run python -m bahi.decide

# Limitation Act s.18: what has expired, and what we have stopped prompting on
# because prompting would restart a three-year clock.
expire:
	cd api && uv run python -m bahi.expiry

# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------

api:
	cd api && uv run uvicorn bahi.service:app --port 8000 --reload

web:
	npm --prefix web run dev

# Types, lint, and the tests that hold the UI to its rules: no amount typed
# into a screen, no shaming words, no colour outside globals.css.
web-check:
	npm --prefix web run check

# ---------------------------------------------------------------------------
# Voice
# ---------------------------------------------------------------------------

# Fills the offline cache. Costs Sarvam credits the first time and nothing
# after - a line already on disk is skipped. Sets SARVAM_OFFLINE=0 for its own
# process, because spending network is this command's whole job.
voice:
	cd api && uv run python -m bahi.voice generate

voice-list:
	cd api && uv run python -m bahi.voice list

# ---------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------

check: lint typecheck test

lint:
	cd api && uv run ruff check .
	cd api && uv run ruff format --check .

typecheck:
	cd api && uv run mypy .

test:
	cd api && uv run pytest -q
