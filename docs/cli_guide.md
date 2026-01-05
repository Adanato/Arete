# o2a CLI Guide

This guide covers the advanced usage, configuration, and syntax for the `o2a` command-line tool.

## Key Features
- **Fast & Cache-Aware**: Skips unchanged files.
- **Prune Mode**: Automatically deletes orphaned cards from Anki.
- **Hierarchy Support**: Mirrors folder structure to nested decks.
- **LaTeX & MathJax**: Built-in sanitization.
- **WSL Support**: Native Windows Subsystem for Linux support.

## Installation
```bash
git clone https://github.com/Adanato/obsidian_2_anki
cd obsidian_2_anki
pip install .
```

## Quick Start (CLI)
### 1. Initialize
```bash
uv run o2a init
```
### 2. Sync
```bash
uv run o2a sync
```

## Markdown Syntax
`o2a` looks for a `cards` list in YAML frontmatter.

### Basic Model
```markdown
---
cards:
  - Front: Question
    Back: Answer
---
```

### Cloze Model
```markdown
---
cards:
  - model: Cloze
    Text: This is a {{c1::cloze}}.
---
```

### Custom Models
Matches fields exactly by name.
```markdown
---
model: "My Custom Model"
cards:
  - MyField1: "Value 1"
    MyField2: "Value 2"
---
```

## CLI Usage References

| Command | Description |
| :--- | :--- |
| `o2a sync` | Standard sync. |
| `o2a sync --prune` | Sync + orphan deletion. |
| `o2a sync --force` | Bypass cache checks and prompts. |
| `o2a sync --dry-run` | Preview changes without applying to Anki. |
| `o2a sync --clear-cache` | Wipe the local SQLite cache and force re-sync. |
| `o2a sync --keep-going` | Continue processing even if individual notes error out. |
| `o2a config show` | View current resolved configuration. |
| `o2a config open` | Open `config.toml` in your default editor. |
| `o2a logs` | Open the run logs directory. |

> [!IMPORTANT]
> **WSL Media Sync**: If you are using WSL, ensure your Anki media directory is a regular Windows path that `o2a` can resolve (e.g., `/mnt/c/Users/.../collection.media`).

## Configuration (`~/.config/o2a/config.toml`)
```toml
root_input = "/path/to/vault"
anki_media_dir = "/path/to/anki/collection.media"
backend = "ankiconnect"
prune = false
```
