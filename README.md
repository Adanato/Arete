# ObsiAnki (formerly o2a)

**Pro-grade synchronization from Obsidian to Anki.**

`o2a` is a robust, fast, and feature-rich tool that adheres to a strict **One-Way Sync** philosophy: **Obsidian is the Source of Truth**.

---

## 📚 Documentation
- **[CLI Guide](./docs/cli_guide.md)**: Command-line usage, configuration, and syntax.
- **[Obsidian Plugin Guide](./docs/plugin_guide.md)**: Installation and usage of the Obsidian plugin.

---

## Quick Start

### 1. Install Code
```bash
git clone https://github.com/Adanato/obsidian_2_anki
cd obsidian_2_anki
pip install .
```

### 2. Install Plugin (Optional)
Download `main.js`, `manifest.json`, `styles.css` from [Releases](https://github.com/Adanato/obsidian_2_anki/releases) and place in `.obsidian/plugins/obsidian-2-anki`.

### 3. Initialize
```bash
uv run o2a init
```

### 4. Create Card
```markdown
---
cards:
  - Front: What is the derivative of $x^2$?
    Back: $2x$
---
```

### 5. Sync
```bash
uv run o2a sync
```

## Key Features
- ⚡ **Fast**: SQLite caching skips unchanged files.
- 🧹 **Prune Mode**: Deletes orphaned cards from Anki.
- 🩹 **Self-Healing**: Fixes duplicates and ID mismatches.
- 📐 **MathJax**: Built-in LaTeX protection.

## License
MIT

## Roadmap
- [ ] **Community Plugin**: Submit `ObsiAnki` to the official Obsidian Community Plugins list.
- [ ] **PyPI Release**: Publish `obsianki` package to PyPI (`uv publish`).

