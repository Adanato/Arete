# Arete v2.0 Planning Document

## Vision Overview

### 🏗️ Architecture Upgrade
| Feature | Impact |
|---------|--------|
| **Direct Apy Integration** | No subprocess spawning, 3-5x faster sync |
| **Vendor core logic** | Full control, no external dependencies |
| **FSRS parity in Apy** | Same stats available offline and online |

### ⚡ Performance
| Feature | Impact |
|---------|--------|
| **HTTP Server Mode** | Persistent connection, streaming progress |
| **Warm Anki connection** | No cold start per sync |
| **Parallel card operations** | Batch writes to DB |

### 🎨 UX Polish
| Feature | Status |
|---------|--------|
| Status bar with last sync | ✅ Done (v1.x) |
| Sync on save | ✅ Done (v1.x) |
| Gutter right-click menu | Planned |
| Due date on hover | Planned |
| Leech notifications | Planned |

### 🔬 Advanced Features
| Feature | Description |
|---------|-------------|
| **Review Mode in Obsidian** | Study cards without leaving Obsidian |
| **Graph View Coloring** | Color nodes by retention/health |
| **Learning Velocity Dashboard** | Track progress over time |
| **Bulk Card Operations** | Suspend/reschedule multiple cards |

---

## v2.0 Release Criteria

1. ✅ No subprocess calls (pure Python)
2. ✅ Stats work with both backends (Apy + AnkiConnect parity)
3. ✅ Gutter right-click menu (suspend, reschedule)
4. ✅ HTTP server mode (optional, for power users)
5. ✅ E2E tests for Obsidian plugin

---

## Versioning Strategy

| Version | Theme |
|---------|-------|
| **v1.0** | Core sync, basic plugin |
| **v1.1** | Card health gutter, stats dashboard |
| **v1.2** | UX polish (settings, commands) |
| **v2.0** | Architecture overhaul + advanced features |

---

# Implementation: Extract Core Logic from Apy

## Executive Summary

**Goal:** Remove subprocess spawning, import apy logic directly, and eventually vendor the core code.

**Current State:**
- Arete spawns `apy update-from-file` via subprocess
- Arete already has: frontmatter parsing, math conversion, `make_editor_note()`
- Apy provides: DB connection, note CRUD, markdown→HTML conversion

**Target State:**
- Direct Python imports from apy (no subprocess)
- Eventually vendor core apy files into Arete

---

## What You Already Have (Arete)

| Module | Purpose |
|--------|---------|
| `text.py` | `make_editor_note()`, `convert_math_to_tex_delimiters()`, frontmatter parsing |
| `parser.py` | Card extraction from Obsidian markdown |
| `models.py` | `WorkItem`, `UpdateItem`, domain models |
| `interfaces.py` | `AnkiBridge` interface (adapter pattern) |

---

## What You Need from Apy

### Core Files (Must Keep)

| Apy File | Lines | What to Extract |
|----------|-------|-----------------|
| `anki.py` | 749 | `Anki` class (DB connection, note operations) |
| `note.py` | 900 | `NoteData.add_to_collection()`, `NoteData.update_or_add_to_collection()` |
| `fields.py` | 287 | `convert_text_to_field()` (markdown→Anki HTML) |
| `markdown_math.py` | 67 | `MathProtectExtension` (protects $$ during markdown conversion) |

### Files to Discard

| File | Reason |
|------|--------|
| `cli.py` | You have your own CLI |
| `console.py` | Rich console output (side effects) |
| `config.py` | Apy-specific config, not needed |
| `utilities.py` | Minor helpers, can inline if needed |
| `cards.py` | Card printing, not needed for sync |

---

## The Key Function You Need

The **only** apy function you truly need that you don't have:

```python
# From apyanki/fields.py
def convert_text_to_field(text: str, use_markdown: bool) -> str:
    """Convert text to Anki field html."""
    if use_markdown:
        return _convert_markdown_to_field(text)
    return text
```

This converts your Obsidian markdown → Anki HTML with proper math handling.

Everything else (DB operations) goes through `Anki.add_notes_from_file()` which you're already using (via subprocess).

---

## Phase 1: Direct Import (No Code Changes to Apy)

### Step 1.1: Update AnkiApyAdapter

```python
# src/arete/infrastructure/adapters/anki_apy.py

from apyanki.anki import Anki
from apyanki.note import NoteData

class AnkiApyAdapter(AnkiBridge):
    def __init__(self, anki_base: Path | None, ...):
        self.anki_base = anki_base
        self._anki: Anki | None = None  # Lazy init
    
    def _get_anki(self) -> Anki:
        if self._anki is None:
            self._anki = Anki(base_path=str(self.anki_base))
        return self._anki
    
    async def sync_notes(self, work_items: list[WorkItem]) -> list[UpdateItem]:
        results = []
        with self._get_anki() as anki:
            for item in work_items:
                note_data = NoteData(
                    model=item.note.model,
                    deck=item.note.deck,
                    tags=item.note.tags_string,
                    fields=item.note.fields,
                    nid=item.note.nid,
                    cid=item.note.cid,
                    markdown=True,
                )
                try:
                    result = note_data.update_or_add_to_collection(anki)
                    results.append(UpdateItem(
                        source_file=item.source_file,
                        source_index=item.source_index,
                        new_nid=str(result.n.id),
                        new_cid=None,  # Would need to fetch
                        ok=True,
                        note=item.note,
                    ))
                except Exception as e:
                    results.append(UpdateItem(..., ok=False, error=str(e)))
        return results
```

### Step 1.2: Update pyproject.toml

```toml
dependencies = [
    "apyanki",  # From your local path or git submodule
    # ... rest
]

[tool.uv.sources]
apyanki = { path = "apy", editable = true }
```

### Step 1.3: Suppress Console Output

Apy uses `rich.console` for output. Suppress it:

```python
import contextlib
from apyanki.console import console

@contextlib.contextmanager
def suppress_apy_output():
    original = console.quiet
    console.quiet = True
    try:
        yield
    finally:
        console.quiet = original
```

---

## Phase 2: Vendor Core Logic (Full Control)

### Step 2.1: Create Arete's Anki Module

```
src/arete/infrastructure/anki/
├── __init__.py
├── collection.py      # Extracted from apyanki/anki.py
├── note_data.py       # Extracted from apyanki/note.py (NoteData only)
├── fields.py          # Extracted from apyanki/fields.py
└── markdown_math.py   # Copy from apyanki/markdown_math.py
```

### Step 2.2: Minimal collection.py (~200 lines)

```python
"""Anki collection wrapper - extracted from apyanki"""

from pathlib import Path
from typing import TYPE_CHECKING

from anki.collection import Collection
from anki.notes import Note

if TYPE_CHECKING:
    from anki.models import NotetypeDict

class AnkiCollection:
    """Minimal Anki collection wrapper for note operations."""
    
    def __init__(self, base_path: Path | None = None):
        self.base_path = base_path or self._detect_base_path()
        self.col: Collection | None = None
    
    def __enter__(self) -> "AnkiCollection":
        db_path = self.base_path / "collection.anki2"
        self.col = Collection(str(db_path))
        return self
    
    def __exit__(self, *args) -> None:
        if self.col:
            self.col.close()
    
    def find_notes(self, query: str) -> list[int]:
        return list(self.col.find_notes(query))
    
    def get_model(self, name: str) -> "NotetypeDict | None":
        return self.col.models.by_name(name)
    
    def add_note(self, model_name: str, deck_name: str, 
                 fields: dict[str, str], tags: list[str]) -> Note:
        model = self.get_model(model_name)
        note = self.col.new_note(model)
        # ... fill fields, set deck, add tags
        self.col.add_note(note, deck_id)
        return note
    
    def update_note(self, nid: int, fields: dict[str, str], 
                    tags: list[str]) -> Note:
        note = self.col.get_note(nid)
        # ... update fields and tags
        self.col.update_note(note)
        return note
```

### Step 2.3: fields.py (~50 lines needed)

```python
"""Markdown to Anki HTML conversion"""

import markdown
from .markdown_math import MathProtectExtension

def markdown_to_anki_html(text: str, latex_mode: str = "mathjax") -> str:
    """Convert markdown text to Anki-compatible HTML."""
    md = markdown.Markdown(
        extensions=[
            "fenced_code",
            "tables",
            MathProtectExtension(latex_mode),
        ]
    )
    html = md.convert(text)
    # Add apy's marker comment for consistency detection
    return f"<!-- apy markdown -->\n{html}"
```

---

## Migration Checklist

- [ ] Phase 1.1: Update `AnkiApyAdapter` to use direct imports
- [ ] Phase 1.2: Update `pyproject.toml` to include apyanki as editable dep
- [ ] Phase 1.3: Test with existing tests
- [ ] Phase 1.4: Remove subprocess code path
- [ ] Phase 2.1: Create `src/arete/infrastructure/anki/` directory
- [ ] Phase 2.2: Extract `collection.py` (~200 lines from 749)
- [ ] Phase 2.3: Extract `fields.py` (~50 lines from 287)
- [ ] Phase 2.4: Copy `markdown_math.py` (67 lines, can copy verbatim)
- [ ] Phase 2.5: Update adapter to use vendored code
- [ ] Phase 2.6: Remove apy git submodule
- [ ] Phase 2.7: Clean up pyproject.toml dependencies

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Apy internals change | You control the fork |
| Missing edge cases | Keep existing tests, they cover your usage |
| DB corruption | Apy's logic is battle-tested, keep as-is |
| FSRS compatibility | Use AnkiConnect for stats (already working) |

---

## Estimated Effort

| Phase | Hours | Complexity |
|-------|-------|------------|
| Phase 1 (Direct Import) | 2-3 | Low |
| Phase 2 (Vendor) | 4-6 | Medium |
| Testing | 2 | Low |
| **Total** | **8-11** | |

---

## Decision Points

1. **Start with Phase 1 only?** Lower risk, faster, still subprocess-free
2. **Go straight to Phase 2?** More work upfront, full control forever
3. **Keep AnkiConnect for online, Apy for offline?** Yes, this is the right dual-backend strategy

