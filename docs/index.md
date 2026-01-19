# Welcome to Arete

**Arete** is a robust, fast, and feature-rich tool designed to synchronize your [Obsidian](https://obsidian.md/) vault to [Anki](https://apps.ankiweb.net/).

[![CI](https://github.com/Adanato/obsidian_2_anki/actions/workflows/ci.yml/badge.svg)](https://github.com/Adanato/obsidian_2_anki/actions/workflows/ci.yml)
[![Coverage](coverage.svg)](htmlcov/index.html)
[![PyPI](https://img.shields.io/pypi/v/arete)](https://pypi.org/project/arete/)
[![License](https://img.shields.io/github/license/Adanato/obsidian_2_anki)](https://github.com/Adanato/obsidian_2_anki/blob/main/LICENSE)

It adheres to a strict **One-Way Sync** philosophy: **Obsidian is the Source of Truth**.

> [!NOTE] 
> **Arete v2.0**: This version introduces advanced features like Topological Study Queues and FSRS-based difficulty analysis.

---

## Key Features

- ⚡ **Near-Instant Sync**: SQL-based caching ensures only changed files are re-processed.
- 📐 **Topological Sort**: Automatically creates Anki decks that respect prerequisite relationships.
- 🧬 **FSRS Support**: Analyzes difficulty and retention using modern scheduling data.
- 🧹 **Prune Mode**: Automatically deletes Anki cards that no longer exist in your vault.
- 🩹 **Self-Healing**: Detects and fixes lost IDs or duplicate cards without manual intervention.
- 📸 **Media Sync**: Seamlessly syncs images and attachments.
- 💻 **Cross-Platform**: First-class support for macOS, Linux, and Windows (WSL).

## Documentation

- **[CLI Guide](CLI.md)**: Command-line usage, configuration, and syntax.
- **[Obsidian Plugin](PLUGIN.md)**: How to use the companion Obsidian plugin.
- **[Architecture](ARCHITECTURE.md)**: Deep dive into the project internals.
- **[Troubleshooting](TROUBLESHOOTING.md)**: Solutions for common networking and sync issues.
- **[Contributing](CONTRIBUTING.md)**: Guide for developers wanting to help out.

## Installation

```bash
git clone https://github.com/Adanato/obsidian_2_anki
cd obsidian_2_anki
uv sync
```

## Basic Usage

1.  **Initialize** your vault config:
    ```bash
    uv run arete init
    ```

2.  **Sync** your notes:
    ```bash
    uv run arete sync
    ```

3.  **Migrate** (if coming from v1):
    ```bash
    uv run arete migrate
    ```
