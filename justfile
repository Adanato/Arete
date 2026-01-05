# o2a Project Automation

# Default: list tasks
default:
    @just --list

# Install dependencies and pre-commit hooks
install:
    uv sync
    uv run pre-commit install

# Run all unit and functional tests (excludes integration)
test:
    uv run pytest tests/core tests/infrastructure tests/services tests/test_media.py tests/test_text.py

# Run integration tests (Anki must be running)
test-integration:
    uv run pytest tests/integration

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

# Format and lint with ruff
lint:
    uv run ruff format src tests
    uv run ruff check src tests

# Run Astral's ty type checker
check-types:
    uv run ty check .

# Fix lint issues with ruff
fix:
    uv run ruff check --fix .
    uv run ruff format .

# Clear local cache
clear-cache:
    rm -rf .pytest_cache .ruff_cache
    find . -name "__pycache__" -type d -exec rm -rf {} +

# Run tests with coverage report
coverage:
    uv run pytest --cov=src/o2a --cov-report=term-missing --cov-report=html tests/core tests/infrastructure tests/services tests/test_media.py tests/test_text.py

# Wait for Anki to be ready
wait-for-anki:
    uv run python scripts/wait_for_anki.py

# Run comprehensive checks (Python + TS: Lint, Format, Test)
check:
    @echo "--- 🐍 Python: Formatting & Linting ---"
    uv run ruff format src tests
    uv run ruff check src tests
    @echo "--- 🐍 Python: Testing ---"
    uv run pytest
    @echo "--- 🟦 TypeScript: Linting ---"
    cd obsidian-plugin && npm run lint
    @echo "--- 🟦 TypeScript: Testing ---"
    cd obsidian-plugin && npm test
    @echo "✅ All Checks Passed!"

# Deploy documentation to GitHub Pages
deploy-docs:
    uv run mkdocs gh-deploy --force
