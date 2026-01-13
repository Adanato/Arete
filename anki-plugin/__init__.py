"""
Obsidian Source Link - Anki Add-on
Opens the source Obsidian file when reviewing cards or browsing.

Features:
1. Right-click context menu in Browse to open in Obsidian
2. Button/shortcut during Review (Ctrl+Shift+O)

Requires: Obsidian Advanced URI plugin for line-level navigation (optional).
"""

import webbrowser
from urllib.parse import quote

from aqt import gui_hooks, mw
from aqt.browser import Browser
from aqt.qt import QAction, QKeySequence, QMenu
from aqt.reviewer import Reviewer
from aqt.utils import showWarning, tooltip

# ─────────────────────────────────────────────────────────────────────────────
# Core Logic
# ─────────────────────────────────────────────────────────────────────────────


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
                import re
                clean_value = re.sub(r'<[^>]*>', '', field_value).strip()

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
    encoded_vault = quote(vault)
    encoded_path = quote(file_path)

    # Use Advanced URI for line-level navigation (Recommended)
    uri = f"obsidian://advanced-uri?vault={encoded_vault}&filepath={encoded_path}&line={card_idx}"

    # Fallback to standard URI if Advanced URI plugin is not installed
    # uri = f"obsidian://open?vault={encoded_vault}&file={encoded_path}"

    try:
        webbrowser.open(uri)
        return True
    except Exception as e:
        showWarning(f"Failed to open Obsidian: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Feature 1: Reviewer Button/Shortcut
# ─────────────────────────────────────────────────────────────────────────────


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


# ─────────────────────────────────────────────────────────────────────────────
# Feature 2: Browse Right-Click Context Menu
# ─────────────────────────────────────────────────────────────────────────────


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


# ─────────────────────────────────────────────────────────────────────────────
# AnkiConnect Custom Actions
# ─────────────────────────────────────────────────────────────────────────────


def on_anki_connect_call(method: str, params: dict, context: dict):
    """
    Handle custom AnkiConnect actions.
    Example call: {"action": "showTooltip", "params": {"msg": "Sync complete!"}}
    """
    if method == "showTooltip":
        msg = params.get("msg", "No message provided")
        period = params.get("period", 3000)
        tooltip(msg, period=period)
        return True
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Initialization
# ─────────────────────────────────────────────────────────────────────────────


# Add reviewer shortcut
setup_reviewer_shortcut()

# Add browser context menu hook
gui_hooks.browser_will_show_context_menu.append(on_browser_context_menu)

# Try to hook into AnkiConnect if it's installed
try:
    from anki_connect.anki_connect import AnkiConnect

    def wrap_anki_connect():
        # This is a bit hacky but works for adding custom actions to AnkiConnect
        original_handler = AnkiConnect.handle_request

        def custom_handler(self, request):
            method = request.get("action")
            params = request.get("params", {})

            # Check if it's our custom action
            res = on_anki_connect_call(method, params, {})
            if res is not None:
                return {"result": res, "error": None}

            return original_handler(self, request)

        AnkiConnect.handle_request = custom_handler

    # We need to wait for AnkiConnect to be initialized
    gui_hooks.main_window_did_init.append(wrap_anki_connect)
except ImportError:
    # AnkiConnect not found, skip custom actions
    pass
