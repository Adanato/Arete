# Arete Project Automation
set shell := ["bash", "-cu"]

# --- Project Constants ---
PY         := "uv run python"
PYTEST     := "uv run pytest"
RUFF       := "uv run ruff"
NPM        := "npm --prefix obsidian-plugin"
SRC        := "src"
TESTS      := "tests"
PLUGIN     := "obsidian-plugin"
RELEASE    := "release_artifacts"

# Default: List all available tasks
default:
    @just --list

# --- Setup ---

# Install dependencies for both Python (uv) and Obsidian (npm)
@install:
    uv sync
    {{NPM}} install
    uv run pre-commit install

# --- Development ---

# Start backend dev server with hot-reload
@dev-backend:
    uv run uvicorn arete.interface.main:app --reload

# Start plugin dev watcher
@dev-plugin:
    {{NPM}} run dev

# --- Backend (Python) ---

# Run backend tests
test *args:
    {{PYTEST}} {{TESTS}}/application {{TESTS}}/interface {{TESTS}}/infrastructure {{TESTS}}/domain {{args}}

# Run backend integration tests (requires Anki)
test-integration:
    {{PYTEST}} {{TESTS}}/integration

# Lint backend code with Ruff
@lint:
    {{RUFF}} check {{SRC}} {{TESTS}} scripts/

# Format backend code with Ruff
@format:
    {{RUFF}} format {{SRC}} {{TESTS}} scripts/

# Fix all auto-fixable backend issues
@fix:
    {{RUFF}} check --fix {{SRC}} {{TESTS}} scripts/
    {{RUFF}} format {{SRC}} {{TESTS}} scripts/

# Static type checking
@check-types:
    uv run pyright {{SRC}}

# --- Frontend (Obsidian Plugin) ---

# Build Obsidian plugin
@build-obsidian:
    {{NPM}} run build

# Lint Obsidian plugin
@lint-obsidian:
    {{NPM}} run lint

# Test Obsidian plugin
@test-obsidian:
    {{NPM}} run test

# --- Release & Artifacts ---

# Build Python package (sdist + wheel)
@build-python:
    {{PY}} -m build

# Zip Anki plugin for distribution
@build-anki:
    mkdir -p {{RELEASE}}
    cd arete_ankiconnect && zip -r ../{{RELEASE}}/arete_ankiconnect.zip . -x "__pycache__/*"
    cp {{RELEASE}}/arete_ankiconnect.zip {{RELEASE}}/arete_ankiconnect.ankiaddon

# Full release build (all artifacts)
@release: build-python build-obsidian build-anki
    @echo "📦 Packaging release artifacts..."
    @cp dist/* {{RELEASE}}/
    @cp {{PLUGIN}}/main.js {{PLUGIN}}/manifest.json {{PLUGIN}}/styles.css {{RELEASE}}/
    @echo "✨ Release ready in {{RELEASE}}/"

# Automate AnkiWeb publishing (requires ANKIWEB_USER/PASS env vars)
@publish-anki id="2055492159":
    {{PY}} scripts/publish_anki_addon.py --id {{id}}

# --- QA & CI ---

# Verify V2 migration logic against mock vault
@test-migration:
    {{PY}} -m arete migrate {{TESTS}}/mock_vault -v

# Run full project QA (Tests + Linting + Formatting)
@qa:
    @echo "--- 🐍 Backend QA ---"
    just fix
    just test
    @echo "--- 🟦 Frontend QA ---"
    {{NPM}} run format
    just test-obsidian
    just lint-obsidian
    just build-obsidian
    @echo "✅ All QA checks passed!"

# --- System ---

# Clean up build artifacts and caches
@clean:
    @echo "🧹 Cleaning project..."
    rm -rf dist/ {{RELEASE}}/
    find . -type d -name "__pycache__" -exec rm -rf {} +
    rm -rf .pytest_cache/ .ruff_cache/ .mypy_cache/
    @echo "✨ Cleaned."

# --- Infrastructure ---

# Download and configure AnkiConnect for Docker
@setup-anki-data:
    {{PY}} scripts/install_ankiconnect.py

# Start Dockerized Anki
@docker-up: setup-anki-data
    docker compose -f docker/docker-compose.yml up -d

# Stop Dockerized Anki
@docker-down:
    docker compose -f docker/docker-compose.yml down

# Wait for Anki to be ready
@wait-for-anki:
    {{PY}} scripts/wait_for_anki.py

# Start Dockerized Anki (optimized for Mac/OrbStack)
@mac-docker-up:
    @echo "🚀 Starting OrbStack..."
    @orb start
    @echo "⌛ Waiting for Docker daemon..."
    @while ! docker info > /dev/null 2>&1; do sleep 1; done
    @just docker-up
