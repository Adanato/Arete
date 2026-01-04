# Contributing to o2a

We follow a structured, iterative development process. Our goal is to make small, atomic changes and verify them completely before moving to the next task.

## 🚀 Development Lifecycle

1.  **Pick a Task**: Focus on a single issue or feature at a time.
2.  **Atomic Implementation**: Make the smallest necessary change to achieve the goal.
3.  **Verify Immediately**: Run tests and linters *before* committing.
4.  **Merge & Iterate**: Keep branches short-lived.

## 🌿 Branching Strategy

We follow a standard Feature Branch Workflow:

-   **`main`**: Production-ready code. Always stable.
-   **`feat/name`**: New features (e.g., `feat/anki-connect-url`).
-   **`fix/issue`**: Bug fixes (e.g., `fix/windows-path-bug`).
-   **`chore/task`**: Maintenance (e.g., `chore/ci-pipeline`).

**Rule**: Never push directly to `main`. Open a Pull Request for *every* change.

## 🛠 Setup

We use `uv` for Python dependency management and `just` for task automation. For the Obsidian plugin, we use `npm`.

### 1. Install Dependencies
```bash
# Python & CLI
uv sync
uv run pre-commit install

# Obsidian Plugin
cd obsidian-plugin
npm install
cd ..
```

## ✅ Verification (The "Gold Standard")

Before submitting any code, you must ensure the entire project is healthy. We have a single command for this:

```bash
just check
```
This command runs:
- Python Formatting (`ruff format`)
- Python Linting (`ruff check`)
- Python Tests (`pytest`)
- TypeScript Linting (`npm run lint`)
- TypeScript Tests (`npm test`)

**If `just check` passes, your code is ready.**

## ⚡ Workflow Commands

### Python / CLI
| Task | Command | Description |
| :--- | :--- | :--- |
| **Lint & Format** | `just lint` | Run Ruff to check and format code. |
| **Fix Issues** | `just fix` | Auto-fix Python linting errors. |
| **Type Check** | `just check-types` | Run static type checking. |
| **Unit Tests** | `just test` | Run fast unit tests. |
| **Integration** | `just test-integration`| Run E2E tests (requires Docker). |

### Obsidian Plugin
| Task | Command | Description |
| :--- | :--- | :--- |
| **Build** | `npm run build` | Compile TypeScript to `main.js`. |
| **Test** | `npm test` | Run Jest unit tests. |
| **Lint** | `npm run lint` | Run ESLint. |

### Documentation
| Task | Command | Description |
| :--- | :--- | :--- |
| **Deploy** | `just deploy-docs` | Build and deploy MkDocs to GitHub Pages. |

## 🏗 Architecture & Design

- **One-Way Sync**: Obsidian is the source of truth. We push to Anki, we do not pull back.
- **Plugin vs CLI**: The Plugin wraps the CLI. Keep complex logic in the CLI (`o2a.main`) where it can be tested easily. The Plugin should primarily handle UI and process orchestration.

Please review [ARCHITECTURE.md](./ARCHITECTURE.md) for deeper system design details.
