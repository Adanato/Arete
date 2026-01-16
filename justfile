# Arete Project Automation

# Default: list tasks
default:
    @just --list

# --- Install & Setup ---

# Install dependencies for both Python (uv) and Obsidian (npm)
install:
    uv sync
    cd obsidian-plugin && npm install
    uv run pre-commit install

# --- Backend (Python) ---

# Run backend tests
test:
    uv run pytest tests/application tests/interface tests/infrastructure tests/domain

# Run backend integration tests (requires Anki)
test-integration:
    uv run pytest tests/integration

# Lint backend code with Ruff
lint:
    uv run ruff check src tests

# Format backend code with Ruff
format:
    uv run ruff format src tests

# Fix all auto-fixable backend issues
fix:
    uv run ruff check --fix src tests
    uv run ruff format src tests

# Static type checking
check-types:
    uv run pyright src

# --- Frontend (Obsidian Plugin) ---

# Build Obsidian plugin
build-obsidian:
    cd obsidian-plugin && npm run build

# Lint Obsidian plugin
lint-obsidian:
    cd obsidian-plugin && npm run lint

# Test Obsidian plugin
test-obsidian:
    cd obsidian-plugin && npm test

# --- Release & Artifacts ---

# Build Python package (sdist + wheel)
build-python:
    uv run python -m build

# Zip Anki plugin
build-anki:
    mkdir -p release_artifacts
    cd arete_ankiconnect && zip -r ../release_artifacts/arete_ankiconnect.zip . -x "__pycache__/*"

# Full release build (all artifacts)
release: build-python build-obsidian build-anki
    @echo "📦 Release artifacts ready in release_artifacts/"
    cp dist/* release_artifacts/
    cp obsidian-plugin/main.js obsidian-plugin/manifest.json obsidian-plugin/styles.css release_artifacts/

# --- QA & CI ---

# Run full project QA (Tests + Linting for both Backend & Frontend)
qa:
    @echo "--- 🐍 Backend QA ---"
    just test
    just lint
    @echo "--- 🟦 Frontend QA ---"
    just test-obsidian
    just lint-obsidian
    just build-obsidian
    @echo "✅ QA Complete!"

# --- Docker & Integration ---

# Download and configure AnkiConnect for Docker
setup-anki-data:
    uv run python scripts/install_ankiconnect.py

# Start Dockerized Anki
docker-up:
    @just setup-anki-data
    docker compose -f docker/docker-compose.yml up -d

# Stop Dockerized Anki
docker-down:
    docker compose -f docker/docker-compose.yml down

# Wait for Anki to be ready
wait-for-anki:
    uv run python scripts/wait_for_anki.py

# Start Dockerized Anki (optimized for Mac/OrbStack)
mac-docker-up:
    @echo "Starting OrbStack..."
    @orb start
    @echo "Waiting for Docker daemon..."
    @while ! docker info > /dev/null 2>&1; do sleep 1; done
    @just setup-anki-data
    docker compose -f docker/docker-compose.yml up -d
