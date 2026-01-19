# Arete CLI Guide

This guide covers the advanced usage, configuration, and syntax for the `arete` command-line tool.

## Installation

`arete` uses [uv](https://github.com/astral-sh/uv) for lightning-fast dependency management and isolated environments.

```bash
git clone https://github.com/Adanato/Arete
cd obsidian_2_anki
uv sync
```

## Commands Reference

| Command | Description |
| :--- | :--- |
| `arete init` | Initialize a new vault configuration. |
| `arete sync` | Standard sync from Obsidian to Anki. |
| `arete sync --prune` | Sync and delete notes in Anki that were removed from Obsidian. |
| `arete sync --force` | Bypass cache and force re-processing of all files. |
| `arete migrate` | **(v2.0)** Upgrade a v1.x vault and configuration to v2.0 standards. |
| `arete server` | **(v2.0)** Start a persistent FastAPI server for faster plugin interaction. |
| `arete queue build` | **(v2.0)** Generate an ordered study queue based on concept dependencies. |
| `arete config show` | View current resolved configuration. |
| `arete logs` | Open the run logs directory. |

## Advanced Sync Options

- `--dry-run`: Preview changes without applying to Anki.
- `--clear-cache`: Wipe the local SQLite cache and force re-sync.
- `--keep-going`: Continue processing even if individual notes error out.

## Topological Sort & Queues (v2.0)

Arete v2.0 supports dependency-aware study queues. By tagging notes with prerequisites, you can generate filtered decks in Anki that ensure you learn concepts in the correct order.

```bash
uv run arete queue build --concepts "Heart" "Valves" --create-deck
```

## Persistence Server

The `server` command starts a local API that the Obsidian plugin uses for near-instant interaction (hover previews, metadata checks).

```bash
uv run arete server --port 8080
```

## Configuration (`~/.config/arete/config.toml`)

```toml
root_input = "/path/to/vault"
anki_media_dir = "/path/to/anki/collection.media"
backend = "ankiconnect"  # 'ankiconnect' or 'apy'
prune = false
```

> [!IMPORTANT]
> **WSL Media Sync**: If you are using WSL, ensure your Anki media directory is a regular Windows path that `arete` can resolve (e.g., `/mnt/c/Users/.../collection.media`).
