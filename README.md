# o2a (Obsidian to Anki)

`o2a` is a robust, fast, and feature-rich CLI tool for synchronizing your Obsidian notes directly to Anki. It adheres to a strict **One-Way Sync** philosophy: **Obsidian is the Source of Truth**. `o2a` acts as a compiler that enforces the state of your vault onto Anki.

## Key Features

-   ⚡ **Fast & Cache-Aware**: Uses a local SQLite cache to skip files that haven't changed, making syncs lightning fast.
-   🛡️ **Accident-Proof Sync**: Persistent `nid` (Note ID) and `cid` (Card ID) tracking ensures cards stay linked correctly even if you move them.
-   🩹 **Self-Healing**: Automatically detects and fixes duplicate cards by adopting existing IDs from Anki.
-   🧹 **Prune Mode**: Automatically identifies and deletes cards and decks in Anki that are no longer found in your vault (Stage 5).
-   📂 **Hierarchy Support**: Mirrors your Obsidian folder structure as nested decks in Anki.
-   📐 **LaTeX & MathJax**: Built-in protection for math symbols and "Complex Search" sanitization to handle `\rho`, `\v`, etc.
-   WSL Support: Native support for Windows Subsystem for Linux via a robust `curl.exe` bridge.

## Installation

`o2a` is a Python package. For development or local usage:

```bash
# Clone the repository
git clone https://github.com/Adanato/obsidian_2_anki
cd obsidian_2_anki

# Install (Important: installs the 'o2a' command)
pip install .
```

## Quick Start

### 1. Initialize Configuration
Run the wizard to set up your vault path and Anki media directory:
```bash
uv run o2a init
```

### 2. Prepare your Markdown
Add Anki-specific frontmatter to any markdown file you want to sync:

```markdown
---
anki_template_version: 1
deck: MyDeck
model: Basic
tags: [math, analysis]
cards:
  - Front: |
      What is the derivative of $x^2$?
    Back: |
      The derivative is $2x$.
---
```

### 3. Sync to Anki
```bash
# Basic sync (safe, only adds/updates)
uv run o2a sync

# Sync with Pruning (deletes orphaned decks/notes)
uv run o2a sync --prune
```

## Markdown Syntax

`o2a` parses a `cards` list in your file's YAML frontmatter.

### Basic & Cloze Models
```markdown
---
cards:
  - Front: Simple Question
    Back: Simple Answer
  - model: Cloze
    Text: This is a {{c1::cloze}} deletion.
---
```

### Custom Models
Any fields defined in your Anki model can be used:
```markdown
---
model: "My Custom Model"
cards:
  - Question: "What is this?"
    Answer: "A demonstration."
    ExtraInfo: "Note that field names must match Anki exactly."
---
```

### Images & Media
`o2a` handles local image links automatically. It supports both standard Markdown and Obsidian Wikilinks:
-   `![[my_image.png]]`
-   `![Image Description](attachments/my_image.png)`

**Note**: Images are automatically copied to your Anki `collection.media` folder during sync.

## CLI Usage

| Command | Description |
| :--- | :--- |
| Command | Description |
| :--- | :--- |
| `o2a sync [path]` | Sync a specific folder or file (default CWD). |
| `o2a sync --prune` | Perform a full sync and propose deletion of orphaned items. |
| `o2a sync --force` | Bypass confirmation prompts for pruning. |
| `o2a sync --clear-cache` | **Important**: Force a full re-sync by clearing the local cache database. |
| `o2a sync --dry-run` | Show what *would* happen without making any changes. |
| `o2a sync --backend <type>` | Choose backend: `ankiconnect` (default) or `apy`. |
| `o2a sync --workers <n>` | Parallel sync workers (default: 1). |
| `o2a init` | Launch the interactive setup wizard. |
| `o2a config show` | Print the resolved configuration. |
| `o2a config open` | Open the config file directory. |
| `o2a logs` | Open the log directory (Finder/Explorer). |
| `o2a -v`, `o2a -vv` | Verbose / Debug mode (Global flag). |

## Development
See [docs/CONTRIBUTING.md](./docs/CONTRIBUTING.md) for setup and testing instructions.

## Backends

`o2a` supports two ways of talking to Anki:

1.  **AnkiConnect** (Default): Uses HTTP to talk to the AnkiConnect add-on. Works great on WSL (via `curl` bridge) and macOS. Supports "Healing" logic.
2.  **apy**: Uses the `apy` CLI tool to directly manipulate the Anki database. Faster for massive imports but requires Anki to be closed.
    *   *Note*: **Prune mode is NOT supported** with the `apy` backend. You must use AnkiConnect if you wish to automatically delete orphaned cards.

## Configuration
Configuration is stored in `~/.config/o2a/config.toml` (XDG standard).

```toml
root_input = "/path/to/vault"
anki_media_dir = "/path/to/anki/collection.media"
backend = "ankiconnect" # or "apy"
prune = false
force = false
```

## Architecture
`o2a` follows a modular architecture for reliability:
-   **Scanner**: Recursively finds compatible markdown files.
-   **Parser**: Transforms frontmatter and content into Anki notes.
-   **AnkiBridge**: Interface for multiple backends (AnkiConnect or `apy`).
-   **Pruner**: Cleans up orphans while preserving deck hierarchies.

For detailed architecture, see [ARCHITECTURE.md](./ARCHITECTURE.md).

## Future Goals

- [ ] **Native Obsidian Plugin**: A companion plugin to provide a GUI (Sync buttons, status indicators) directly within Obsidian.
- [x] **Parallelism 2.0**: Migration to `asyncio` for backend requests to further optimize sync speed for high-latency setups.
- [ ] **Smart Tagging**: Automatic tag generation based on file properties and vault folder paths.
- [ ] **PDF Clipping**: Support for extracting and embedding specific pages or regions from PDFs referenced in your vault.
- [ ] **Pre-rendered Math**: Support for server-side MathJax rendering to ensure consistent formula display across all Anki clients.

## License
MIT
