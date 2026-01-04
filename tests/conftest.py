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
