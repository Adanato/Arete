# ObsiAnki Plugin Guide

The `ObsiAnki` Obsidian Plugin provides a convenient interface for the underlying `o2a` CLI, allowing you to sync, lint, and fix your notes directly from Obsidian.

## Installation

### Method 1: Community Plugins (Coming Soon)
1.  Open Obsidian Settings -> Community Plugins.
2.  Turn off "Safe Mode".
3.  Search for **ObsiAnki**.
4.  Install and Enable.

### Method 2: Manual Install
1.  Go to the [GitHub Releases](https://github.com/Adanato/obsidian_2_anki/releases) page.
2.  Download the latest `main.js`, `manifest.json`, and `styles.css`.
3.  Create a folder: `<Vault>/.obsidian/plugins/obsidian-2-anki`.
4.  Place the 3 files into that folder.
5.  Reload Obsidian (Cmd+R).

### Method 3: BRAT
If you use the BRAT plugin, you can install directly from the GitHub repository URL.

## Configuration
Go to **Settings -> O2A Sync**:

- **Python Path**: Path to your python executable (e.g., `/usr/bin/python3` or `uv`).
- **O2A Script Path**: (Optional) If you installed via pip, leave this blank. The plugin will auto-detect `python -m o2a`.
- **Debug Mode**: Enable verbose logging to the developer console.

## Features & Usage

### 🔄 Sync
- **Ribbon Icon**: Click the "Sync" icon in the left ribbon.
- **Command Palette**: `O2A: Sync to Anki`
- **Hotkey**: `Mod+Shift+A` (Default)

### 🧹 Lint & Fix
- **Command**: `O2A: Check Current File`
    - Scans the active file for syntax errors.
    - Displays results in a modal with red highlights for errors.
- **Command**: `O2A: Fix Current File`
    - Auto-corrects common issues (tabs vs spaces, missing fields).
- **Integrity Check**: `O2A: Check Vault Integrity`
    - Scans the entire vault for files with invalid YAML frontmatter that Obsidian fails to parse.

## Troubleshooting
- **"Command failed"**: Check the Developer Console (Cmd+Option+I) for detailed error logs.
- **Logs**: A log file is maintained in `.obsidian/plugins/obsidian-2-anki/o2a_plugin.log`.
