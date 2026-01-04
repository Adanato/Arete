# Contributing to o2a

We welcome contributions! Please follow these guidelines to ensure a smooth process.

## Development Setup

`o2a` uses `uv` for dependency management and `just` for task automation.

### 1. Install Dependencies
```bash
# Install dependencies
uv sync

# Install pre-commit hooks via uv (Critical for linting/formatting)
uv run pre-commit install
```

### 2. Run Tests
We use `pytest` for unit and integration testing.

| Task | Command | Description |
| :--- | :--- | :--- |
| **Lint** | `just lint` | Run Ruff linter and formatter. |
| **Fix** | `just fix` | Auto-fix linting issues. |
| **Type Check** | `just check-types` | Run static type checking with `ty`. |
| **Test** | `just test` | Run unit and service tests (fast). |
| **Integration** | `just test-integration`| Run E2E integration tests (requires Dockerized Anki). |

### 3. Integration Testing
Integration tests run against a real Anki instance in Docker.

1.  Start Anki: `just docker-up`
2.  Run tests: `just test-integration`
3.  Stop Anki: `just docker-down`

## Architecture

Please review [ARCHITECTURE.md](./ARCHITECTURE.md) to understand the system design before making significant changes.

## Pull Requests

1.  Ensure all tests pass (`just test` and `just test-integration`).
2.  Ensure code is linted and type-checked (`just lint`, `just check-types`).
3.  Describe your changes clearly in the PR description.
