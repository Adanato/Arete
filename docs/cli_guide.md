# arete CLI Guide

This guide covers the advanced usage, configuration, and syntax for the `arete` command-line tool.

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
uv run arete init
```
### 2. Sync
```bash
uv run arete sync
```

## Markdown Syntax
`arete` looks for a `cards` list in YAML frontmatter.

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
| `arete sync` | Standard sync. |
| `arete sync --prune` | Sync + orphan deletion. |
| `arete sync --force` | Bypass cache checks and prompts. |
| `arete sync --dry-run` | Preview changes without applying to Anki. |
| `arete sync --clear-cache` | Wipe the local SQLite cache and force re-sync. |
| `arete sync --keep-going` | Continue processing even if individual notes error out. |
| `arete config show` | View current resolved configuration. |
| `arete config open` | Open `config.toml` in your default editor. |
| `arete logs` | Open the run logs directory. |

> [!IMPORTANT]
> **WSL Media Sync**: If you are using WSL, ensure your Anki media directory is a regular Windows path that `arete` can resolve (e.g., `/mnt/c/Users/.../collection.media`).

## Configuration (`~/.config/arete/config.toml`)
```toml
root_input = "/path/to/vault"
anki_media_dir = "/path/to/anki/collection.media"
backend = "ankiconnect"
prune = false
```
