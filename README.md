# Arete

**Pro-grade synchronization from Obsidian to Anki.**

[![CI](https://github.com/Adanato/obsidian_2_anki/actions/workflows/ci.yml/badge.svg)](https://github.com/Adanato/obsidian_2_anki/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/arete)](https://pypi.org/project/arete/)
[![License](https://img.shields.io/github/license/Adanato/obsidian_2_anki)](https://github.com/Adanato/obsidian_2_anki/blob/main/LICENSE)

`arete` is a robust, fast, and feature-rich tool that adheres to a strict **One-Way Sync** philosophy: **Obsidian is the Source of Truth**. It allows you to maintain complex study materials in your vault while keeping Anki perfectly in sync.

---

## 🚀 Key Features

- ⚡ **Turbocharged Sync**: SQLite caching skips unchanged files for near-instant updates.
- 📐 **Topological Sort**: Build filtered study queues that respect prerequisite dependencies.
- 🧬 **FSRS Support**: Native difficulty and retention analysis for modern memory schedulers.
- 🧹 **Orphan Management**: Automatically prunes deleted cards from your Anki collection.
- 🩹 **Self-Healing**: Automatically repairs duplicate IDs or broken internal references.
- 📸 **Rich Media**: Full synchronization of images, SVGs, and other attachments.
- 💻 **Cross-Platform**: First-class support for macOS, Linux, and Windows (including WSL).

---

## 📦 Quick Start

### 1. Install CLI
`arete` requires [uv](https://github.com/astral-sh/uv) for high-performance dependency management.

```bash
git clone https://github.com/Adanato/obsidian_2_anki
cd obsidian_2_anki
uv sync
```

### 2. Install Plugin
Download the latest release from the [Releases](https://github.com/Adanato/obsidian_2_anki/releases) page and place the files in your plugin folder:
`.obsidian/plugins/arete/`

### 3. Initialize & Sync
```bash
uv run arete init   # Interactive setup wizard
uv run arete sync   # Your first sync
```

---

## 📚 Documentation

- [**CLI Guide**](./docs/cli_guide.md): Command-line options, configuration, and syntax.
- [**Obsidian Plugin Guide**](./docs/plugin_guide.md): How to use the GUI and Gutter features.
- [**Architecture**](./docs/ARCHITECTURE.md): Technical deep-dive into the core logic.
- [**Troubleshooting**](./docs/troubleshooting.md): Common fixes for WSL and networking.

---

## 🔄 Upgrading to v2.0
Upgrading from a legacy version? `arete` includes a migration tool to normalize your metadata:
```bash
uv run arete migrate
```

## 📄 License
MIT
