"""Tests for utility functions."""

import platform
from pathlib import Path
from unittest.mock import patch

from arete.utils import detect_anki_paths, sanitize, to_list

# --- to_list tests ---


def test_to_list_with_none():
    """Test to_list returns empty list for None."""
    assert to_list(None) == []


def test_to_list_with_list():
    """Test to_list converts list items to strings."""
    assert to_list([1, 2, 3]) == ["1", "2", "3"]
    assert to_list(["a", "b"]) == ["a", "b"]


def test_to_list_with_single_value():
    """Test to_list wraps single value in list."""
    assert to_list("single") == ["single"]
    assert to_list(42) == ["42"]


# --- sanitize tests ---


def test_sanitize_with_none():
    """Test sanitize returns empty string for None."""
    assert sanitize(None) == ""


def test_sanitize_with_string():
    """Test sanitize strips trailing whitespace."""
    assert sanitize("hello  ") == "hello"
    assert sanitize("hello\n") == "hello"
    assert sanitize("  hello  ") == "  hello"  # Only trailing is stripped


def test_sanitize_with_number():
    """Test sanitize converts numbers to strings."""
    assert sanitize(42) == "42"
    assert sanitize(3.14) == "3.14"


# --- detect_anki_paths tests ---


def test_detect_anki_paths_darwin():
    """Test Anki path detection on macOS."""
    with patch.object(platform, "system", return_value="Darwin"):
        base, media = detect_anki_paths()
        assert base is not None
        # Use endswith or string replacement to handle potential separator differences
        # if the test runner OS differs from the mocked OS path conventions
        assert str(base).replace("\\", "/").endswith("Library/Application Support/Anki2")
        assert str(media).replace("\\", "/").endswith("collection.media")


def test_detect_anki_paths_windows(tmp_path):
    """Test Anki path detection on Windows."""
    with (
        patch.object(platform, "system", return_value="Windows"),
        patch.object(Path, "exists", return_value=True),
        patch.object(Path, "iterdir", return_value=[tmp_path / "User 1"]),
    ):
        # We need to ensure the mocked iterdir return has a 'collection.anki2' check if we want to cover lines 33-37 fully
        # The code checks: (p / "collection.anki2").exists()
        # So we need to mock exist for that specific path query too if we want to be strict.
        # But 'exists' is already mocked to True globally above.

        base, media = detect_anki_paths()
        assert base is not None
        assert "AppData/Roaming/Anki2" in str(base).replace("\\", "/")
        assert "collection.media" in str(media).replace("\\", "/")


def test_detect_anki_paths_linux():
    """Test Anki path detection on Linux (non-WSL)."""
    with (
        patch.object(platform, "system", return_value="Linux"),
        patch.object(
            platform, "uname", return_value=type("obj", (), {"release": "5.15.0-generic"})()
        ),
    ):
        base, media = detect_anki_paths()
        assert base is not None
        assert str(base).replace("\\", "/").endswith(".local/share/Anki2")


def test_detect_anki_paths_linux_wsl(tmp_path):
    """Test Anki path detection on WSL (Linux with microsoft in release)."""
    with (
        patch.object(platform, "system", return_value="Linux"),
        patch.object(
            platform,
            "uname",
            return_value=type("obj", (), {"release": "5.15.0-microsoft-standard-WSL2"})(),
        ),
        patch.object(Path, "exists", return_value=False),  # /mnt/c/Users doesn't exist
    ):
        base, media = detect_anki_paths()
        # Falls back to regular Linux path
        assert str(base).replace("\\", "/").endswith(".local/share/Anki2")


def test_detect_anki_paths_unknown_os():
    """Test Anki path detection on unknown OS."""
    with patch.object(platform, "system", return_value="UnknownOS"):
        base, media = detect_anki_paths()
        assert base is None
        assert media == Path(".")
