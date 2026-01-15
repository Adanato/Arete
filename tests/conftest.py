import sys
from unittest.mock import MagicMock

# MOCK ANKI DEPENDENCY GLOBALLY
# This prevents ImportErrors during test collection if 'anki' package
# is missing or fails to initialize in the test environment.
mock_anki = MagicMock()
mock_anki.__path__ = []
mock_anki.__spec__ = None  # Required for importlib


# Helper to create submodule mocks
def create_mock_module():
    m = MagicMock()
    m.__spec__ = None
    m.__path__ = []
    return m


mock_collection = create_mock_module()
mock_collection.Collection = MagicMock()

mock_notes = create_mock_module()
mock_notes.Note = MagicMock()

mock_models = create_mock_module()
mock_models.NotetypeDict = dict

mock_errors = create_mock_module()
mock_errors.NotFound = Exception

sys.modules["anki"] = mock_anki
sys.modules["anki.collection"] = mock_collection
sys.modules["anki.notes"] = mock_notes
sys.modules["anki.models"] = mock_models
sys.modules["anki.errors"] = mock_errors

import pytest


@pytest.fixture
def mock_vault(tmp_path):
    """Creates a temporary directory structure mimicking a vault."""
    d = tmp_path / "MyVault"
    d.mkdir()
    return d


@pytest.fixture
def mock_home(tmp_path, monkeypatch):
    """Mocks Path.home() to point to a temp dir."""
    home = tmp_path / "home"
    home.mkdir()

    # Mocking HOME to a temp directory to isolate config/logs
    monkeypatch.setenv("HOME", str(home))
    return home
