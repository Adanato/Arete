# Welcome to ObsiAnki

**ObsiAnki (formerly o2a)** is a robust, fast, and feature-rich tool designed to synchronize your [Obsidian](https://obsidian.md/) vault to [Anki](https://apps.ankiweb.net/).

It adheres to a strict **One-Way Sync** philosophy: **Obsidian is the Source of Truth**.

> [!NOTE] 
> **Current Status**: This project is in active development. While robust, we recommend backing up your Anki collection before large-scale syncs.

---

## Key Features

- ⚡ **Fast**: SQL-based caching ensures only changed files are re-processed.
- 🧹 **Prune Mode**: Automatically deletes Anki cards that no longer exist in your vault.
- 🩹 **Self-Healing**: Detects and fixes lost IDs or duplicate cards without manual intervention.
- 📸 **Media Sync**: Seamlessly syncs images and attachments.
- 📐 **MathJax/LaTeX**: Built-in protection for mathematical content.
- 💻 **Cross-Platform**: First-class support for Windows (WSL), macOS, and Linux.

## Documentation

- **[CLI Guide](cli_guide.md)**: Command-line usage, configuration, and syntax.
- **[Obsidian Plugin](plugin_guide.md)**: How to use the companion Obsidian plugin.
- **[Architecture](ARCHITECTURE.md)**: Deep dive into the project internals.
- **[Troubleshooting](troubleshooting.md)**: Solutions for common networking and sync issues.
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
    uv run o2a init
    ```

2.  **Sync** your notes:
    ```bash
    uv run o2a sync
    ```
