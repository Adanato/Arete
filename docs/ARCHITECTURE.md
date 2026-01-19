# Project Architecture

`arete` follows a modular **Domain-Driven Design (DDD)** approach. The code is organized into layers, separating core domain logic from application services and infrastructure adapters.

## Directory Structure

```text
src/arete/               # Core Python Logic
├── domain/             # Data Structures & Interfaces
│   ├── types.py        # Core data classes (AnkiNote, AnkiDeck, AnkiCard)
│   └── interfaces.py   # Abstract Base Classes (AnkiBridge)
│
├── application/        # Business Logic & Orchestration
│   ├── pipeline.py     # Main sync orchestration layer
│   ├── queue_builder.py # Topological resolution & study queues
│   ├── parser.py       # Markdown -> Anki transformation logic
│   └── vault_service.py # Obsidian vault crawler & ID management
│
├── infrastructure/     # External Adapters & Data Persistence
│   ├── adapters/       # AnkiBridge implementations (Direct, Connect, Apy)
│   └── repository.py   # Low-level DB / FS interactions
│
├── interface/          # User Entry Points
│   ├── cli.py          # Click-based Command Line Interface
│   └── server.py       # FastAPI-based persistence server
│
└── main.py             # Global entry point

obsidian-plugin/        # Obsidian GUI
├── src/                # TypeScript source files
│   ├── application/    # Frontend services (Sync, Stats, Graph)
│   ├── infrastructure/ # API clients (AreteClient)
│   └── presentation/   # UI Components & Views (Gutter, QueueBuilder)
└── styles.css          # Core UI styling
```

## CLI vs Plugin

-   **CLI**: Handles all the heavy lifting—scanning files, hashing content, communicating with AnkiConnect, and writing IDs back to Markdown.
-   **Plugin**: Provides a settings page in Obsidian and a simple "Sync" ribbon icon. When clicked, it spawns a child process to run `arete sync` and captures the output to display in a modal.

This split ensures that advanced users can automate syncs via crontab or shell scripts, while causal users get a seamless integrated experience.

## The Pipeline

The application runs in 5 distinct stages, orchestrated by `core/pipeline.py`:

1.  **Scanning (`VaultService`)**:
    *   Walks the directory tree.
    *   Checks `ContentCache` (MD5 hash) to see if a file needs processing.
    *   Returns a list of compatible markdown files.

2.  **Media Indexing (`media.py`)**:
    *   Builds a global filename index of all common attachment folders (e.g., `attachments`, `assets`).
    *   Enables resolving wikilinks and markdown images without needing full paths.

3.  **Async Processing (Producer/Consumer pairing)**:
    *   **Producers (`Parsing`)**: Parse Markdown, calculate content hashes, and transform media links.
    *   **Consumers (`Syncing`)**: Multi-threaded sync to Anki (via AnkiConnect or `apy`). 
    *   Caching happens here: If a card's content hash matches the cache, it's skipped.

4.  **ID Write-back (`VaultService`)**:
    *   Writes assigned `nid` (Note ID) and `cid` (Card ID) back to the Markdown frontmatter.
    *   Ensures future runs track existing cards correctly.

5.  **Pruning**:
    *   Calculates the set difference between "All IDs in Vault" vs "All IDs in Anki".
    *   Deletes Anki notes and decks that no longer exist in Obsidian (if `--prune` is enabled).

## Key Design Decisions

### 1. Filesystem-Based Media Sync
Unlike note syncing which uses an API, **Media Sync is filesystem-based**. `arete` copies images directly from your vault into Anki's `collection.media` folder. 
*   **Implication**: The CLI must have write access to the Anki media directory.
*   **Uniqueness**: Files are hashed to avoid duplicates (e.g., `image.png` becomes `image_a1b2c3d4.png`).

### 2. Obsidian as Source of Truth
The system is designed to be **Stateless** regarding logic. The state lives in Obsidian (text) and Anki (reviews). `arete` is just the bridge. We write IDs back to Obsidian so it "owns" the link to the card.

### 3. WSL Compatibility
`anki_connect.py` contains specific logic to detect WSL environments.
*   **Problem**: WSL's `localhost` != Windows `localhost`.
*   **Solution**: It attempts to find `curl.exe` (Windows binary) accessible from Linux and uses it as a bridge to communicate with Anki on the host.

### 3. Caching
`infrastructure/cache.py` maintains a lightweight SQLite database of file hashes. This allows the tool to run in milliseconds for unchanged vaults, only processing what you've actually edited.

## Development Stack

`arete` is built with a focus on developer velocity and code quality:

-   **Package Management**: `uv` for lightning-fast dependency resolution and isolated environments.
-   **Task Automation**: `just` (via `justfile`) replaces complex Makefiles for common tasks (test, lint, docker).
-   **Code Quality**: `ruff` for linting and formatting, ensuring a 100% clean codebase with modern Python rules.
-   **Testing**: `pytest` for unit/service tests, and a **Dockerized Anki** environment for end-to-end integration tests.

## Convenience Features

-   **`debug_anki.py`**: A specialized diagnostic tool to verify connectivity between the CLI and Anki (handles WSL/Networking edge cases).
-   **Self-Healing**: Automatic recovery from "Duplicate" errors by adopting existing NIDs, making it robust against manual edits in Anki.
-   **Integrated Logs**: Use `arete --open-logs` to quickly access detailed execution logs for debugging.

## Logging & Reporting

Every execution of `arete` is fully audited:

1.  **Console Output**: Clean and high-level, with verbosity controlled by `-v`.
2.  **Debug Logs**: A comprehensive log file (`run_*.log`) is generated in `~/.config/arete/logs/` for every run, capturing full stack traces and internal transitions.
3.  **Run Reports**: `logging_utils.py` generates a human-readable Markdown report (`report_*.md`) for every sync, providing stats on files scanned, cards updated, and specific error tables.
