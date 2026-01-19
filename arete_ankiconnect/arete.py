import json
import os
import re
import webbrowser
from urllib.parse import quote

from aqt import mw
from aqt.browser import Browser
from aqt.qt import QAction, QKeySequence, QMenu
from aqt.utils import showWarning, tooltip

# ─────────────────────────────────────────────────────────────────────────────
# Arete Config & Logic
# ─────────────────────────────────────────────────────────────────────────────

ADDON_PATH = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(ADDON_PATH, "config.json")
CONFIG = {}


def load_config():
    global CONFIG
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                CONFIG = json.load(f)
        except Exception:
            CONFIG = {}


load_config()


def get_obsidian_source(note) -> tuple[str, str, int] | None:
    """
    Extract Obsidian source info from note's _obsidian_source field.
    Returns (vault_name, file_path, card_index) or None if not found.
    """
    for field_name in note.keys():
        if field_name == "_obsidian_source":
            field_value = note[field_name]
            if field_value:
                # Strip HTML tags if any (legacy sync issues)
                clean_value = re.sub(r"<[^>]*>", "", field_value).strip()

                # Format: vault|path|index
                parts = clean_value.split("|")
                if len(parts) >= 3:
                    vault = parts[0]
                    file_path = parts[1]
                    try:
                        card_idx = int(parts[2])
                    except ValueError:
                        card_idx = 1
                    return vault, file_path, card_idx
    return None


def open_obsidian_uri(vault: str, file_path: str, card_idx: int = 1) -> bool:
    """
    Open Obsidian via URI scheme.
    Returns True on success, False on failure.
    """
    # Allow config to override vault name
    actual_vault = CONFIG.get("vault_name_override", vault) or vault

    encoded_vault = quote(actual_vault)
    encoded_path = quote(file_path)

    # Use Advanced URI for line-level navigation (requires Advanced URI plugin in Obsidian)
    uri = f"obsidian://advanced-uri?vault={encoded_vault}&filepath={encoded_path}&line={card_idx}"

    # Fallback: Standard URI (no line navigation, but works without plugins)
    # uri = f"obsidian://open?vault={encoded_vault}&file={encoded_path}"

    try:
        webbrowser.open(uri)
        return True
    except Exception as e:
        showWarning(f"Failed to open Obsidian: {e}")
        return False


def open_current_card_in_obsidian():
    """Open current reviewing card's source in Obsidian."""
    reviewer = mw.reviewer
    if not reviewer or not reviewer.card:
        showWarning("No card is currently being reviewed.")
        return

    note = reviewer.card.note()
    source = get_obsidian_source(note)

    if not source:
        showWarning(
            "No Obsidian source found for this card.\n\n"
            "Make sure the card was synced with arete and has the "
            "'_obsidian_source' field."
        )
        return

    vault, file_path, card_idx = source
    if open_obsidian_uri(vault, file_path, card_idx):
        tooltip(f"Opening in Obsidian: {file_path}")


def setup_reviewer_shortcut():
    """Add keyboard shortcut and menu item."""
    action = QAction("Open in Obsidian", mw)
    action.setShortcut(QKeySequence("Ctrl+Shift+O"))
    action.triggered.connect(open_current_card_in_obsidian)
    mw.form.menuTools.addAction(action)


def on_browser_context_menu(browser: Browser, menu: QMenu):
    """Add 'Open in Obsidian' to browser right-click menu."""
    selected = browser.selectedNotes()
    if not selected:
        return

    action = menu.addAction("Open in Obsidian")
    action.triggered.connect(lambda: open_selected_notes_in_obsidian(browser))


def open_selected_notes_in_obsidian(browser: Browser):
    """Open selected notes in Obsidian (first one if multiple selected)."""
    selected = browser.selectedNotes()
    if not selected:
        showWarning("No notes selected.")
        return

    # Open first selected note
    note_id = selected[0]
    note = mw.col.get_note(note_id)

    source = get_obsidian_source(note)
    if not source:
        showWarning(
            "No Obsidian source found for this note.\n\n"
            "Make sure the note was synced with arete and has the "
            "'_obsidian_source' field."
        )
        return

    vault, file_path, card_idx = source
    if open_obsidian_uri(vault, file_path, card_idx):
        tooltip(f"Opening in Obsidian: {file_path}")

    # If multiple selected, notify user
    if len(selected) > 1:
        tooltip(f"Opened first of {len(selected)} selected notes")
