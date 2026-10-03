# BAHI
#
# Versions are pinned. On the day we have 5.5 hours and cannot spend any of
# them on a tool that changed its output overnight.

.PHONY: help db db-migrate db-check rhythm decide expire voice voice-list \
        voice-eval names-hi munshi-eval memory-db memory-check \
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
	@echo "voice        render the demo clips; with SARVAM_API_KEY, Sarvam transcribes them"
	@echo "voice-list   what is already in the offline cache"
	@echo "voice-eval   replay the 1,338-recording test through today's checker (no network)"
	@echo "names-hi     fetch the seed's names in Devanagari from Sarvam (needs the key)"
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
	cd api && uv run python -m data.memory_db --reset

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

# The test behind slide 4: 1,338 recordings Sarvam heard and read on 24 Sep,
# replayed through the checker the app runs today. No network, no credits.
voice-eval:
	cd api && uv run python -m bahi.voice.replay

# The munshi, tested as it is used: another model plays the shopkeeper with a
# hidden goal, and each run is scored on the entry the book would hold. Real
# Sarvam calls on the seeded book, rolled back. Costs credits; never in `check`.
munshi-eval:
	cd api && uv run python -m bahi.munshi.eval $(or $(TIMES),2) $(ONLY)

# M3: memory's own role and databases on the local Postgres (needs
# `brew install pgvector` first). Once; running it again changes nothing.
memory-db:
	cd api && uv run python -m data.memory_db

# M3: memory end to end with real Sarvam, OpenAI and Cognee, on the check
# databases only (bahi_check, bahi_memory_check). Spends a few credits.
memory-check:
	cd api && DATABASE_URL=postgresql:///bahi_check SARVAM_OFFLINE=0 uv run python -m bahi.memory.check

# Only names missing from api/data/names_hi.json are fetched.
names-hi:
	cd api && uv run python -m data.names_hi

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
