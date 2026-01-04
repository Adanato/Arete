# Project Architecture

`o2a` follows a modular **Clean Architecture** approach. The code is organized into layers, separating the core domain logic from external services and infrastructure.

## Directory Structure

```text
src/o2a/
├── core/           # Application Logic
│   ├── pipeline.py # The main orchestration loop (Producer/Consumer)
│   ├── config.py   # Configuration loading & argument parsing
│   └── wizard.py   # Interactive setup wizard
│
├── domain/         # Data Structures & Interfaces
│   ├── types.py    # Core data classes (AnkiNote, AnkiDeck, AnkiModel, UpdateItem)
│   └── interfaces.py # Abstract Base Classes (AnkiBridge)
│
├── services/       # Business Logic Implementations
│   ├── vault.py    # "Scanner": Crawls Obsidian vault, handles cache
│   ├── parser.py   # "Transpiler": Markdown -> AnkiNote conversion
│   ├── anki_connect.py # Adapter for AnkiConnect (HTTP)
│   └── anki_apy.py     # Adapter for apy (CLI/DB)
│
├── infrastructure/ # Low-level tools
│   └── cache.py    # SQLite ContentCache implementation
│
└── main.py         # Entry Point
```

## The Pipeline

The application runs in 5 distinct stages, orchestrated by `core/pipeline.py`:

1.  **Scanning (`VaultService`)**:
    *   Walks the directory tree.
    *   Checks `ContentCache` (MD5 hash) to see if a file needs processing.
    *   Returns a list of changed files.

2.  **Parsing (`MarkdownParser`)**:
    *   Reads Markdown files.
    *   Extracts Frontmatter (deck, tags).
    *   Identifies Cards (Front/Back/Equation).
    *   Sanitizes Media links.

3.  **Syncing (`AnkiBridge`)**:
    *   **AnkiConnect**: Uses HTTP (or `curl` on WSL) to push notes to Anki.
        *   *Healing*: If Anki reports a "Duplicate" error, it searches for the existing note using properly sanitized content (handling `\v`, quotes, etc.) and adopts its ID.
    *   **apy**: Uses direct database access via `apy` tool.
    *   Returns `UpdateItem` results containing the final `nid` and `cid`.

4.  **Persisting (`VaultService`)**:
    *   Writes the assigned `nid` (Note ID) and `cid` (Card ID) back to the Markdown frontmatter.
    *   This ensures future runs know exactly which card corresponds to which text, enabling "Accident-Proof Sync".

5.  **Pruning**:
    *   Calculates the set difference between "All IDs found in Vault" vs "All IDs in Anki Deck".
    *   Deletes or suspends Anki cards that no longer exist in Obsidian (if `--prune` is enabled).

## Key Design Decisions

### 1. Obsidian as Source of Truth
The system is designed to be **Stateless** regarding logic. The state lives in Obsidian (text) and Anki (reviews). `o2a` is just the bridge. We write IDs back to Obsidian so it "owns" the link to the card.

### 2. WSL Compatibility
`ankiconnect.py` contains specific logic to detect WSL environments.
*   **Problem**: WSL's `localhost` != Windows `localhost`.
*   **Solution**: It attempts to find `curl.exe` (Windows binary) accessible from Linux and uses it to bridge the request to `127.0.0.1` on the host, bypassing complex networking configuration.

### 3. Caching
`infrastructure/cache.py` maintains a lightweight SQLite database of file hashes. This allows the tool to run in milliseconds for unchanged vaults, only processing what you've actually edited.

## Development Stack

`o2a` is built with a focus on developer velocity and code quality:

-   **Package Management**: `uv` for lightning-fast dependency resolution and isolated environments.
-   **Task Automation**: `just` (via `justfile`) replaces complex Makefiles for common tasks (test, lint, docker).
-   **Code Quality**: `ruff` for linting and formatting, ensuring a 100% clean codebase with modern Python rules.
-   **Testing**: `pytest` for unit/service tests, and a **Dockerized Anki** environment for end-to-end integration tests.

## Convenience Features

-   **`debug_anki.py`**: A specialized diagnostic tool to verify connectivity between the CLI and Anki (handles WSL/Networking edge cases).
-   **Self-Healing**: Automatic recovery from "Duplicate" errors by adopting existing NIDs, making it robust against manual edits in Anki.
-   **Integrated Logs**: Use `o2a --open-logs` to quickly access detailed execution logs for debugging.

## Logging & Reporting

Every execution of `o2a` is fully audited:

1.  **Console Output**: Clean and high-level, with verbosity controlled by `-v`.
2.  **Debug Logs**: A comprehensive log file (`run_*.log`) is generated in `~/.config/o2a/logs/` for every run, capturing full stack traces and internal transitions.
3.  **Run Reports**: `logging_utils.py` generates a human-readable Markdown report (`report_*.md`) for every sync, providing stats on files scanned, cards updated, and specific error tables.
