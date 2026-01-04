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

    # We need to monkeypatch Path.home.
    # Since Path.home() is a method, we patch it on Path class or instance?
    # Actually it's a class method.
    # Monkeypatching built-ins is tricky.
    # Better to rely on env var HOME if pathlib uses it?
    monkeypatch.setenv("HOME", str(home))
    return home
