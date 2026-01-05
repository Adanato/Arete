from pathlib import Path
from unittest.mock import patch

import pytest

from o2a.core.wizard import run_init_wizard


@pytest.fixture
def mock_home(tmp_path):
    # Mock Path.home() to return a temp dir so we don't mess with real config
    with patch("pathlib.Path.home", return_value=tmp_path):
        yield tmp_path


def test_wizard_default_flow(mock_home):
    # Ensure default paths exist to avoid "path does not exist" prompt
    (mock_home / "Obsidian Vault").mkdir(parents=True)

    # Inputs:
    # 1. Vault Root (default) -> Enter
    # 2. Anki Media (default) -> Enter
    # 3. Backend (default 1) -> Enter
    inputs = ["", "", ""]

    with patch("builtins.input", side_effect=inputs):
        with patch(
            "o2a.core.wizard.detect_anki_paths",
            return_value=(Path("/anki/base"), Path("/anki/media")),
        ):
            # Smart existence mock
            original_exists = Path.exists

            def default_exists_side_effect(self):
                # Config file should NOT exist for this test
                if self.name == "config.toml":
                    return False
                # The detected media path SHOULD exist to avoid prompt
                # Loose match for "anki/media" regardless of slashes/drives
                s = str(self).replace("\\", "/")
                if "anki/media" in s:
                    return True
                return original_exists(self)

            with patch(
                "pathlib.Path.exists", autospec=True, side_effect=default_exists_side_effect
            ):
                run_init_wizard()

    config_dir = mock_home / ".config/o2a"
    config_file = config_dir / "config.toml"
    assert config_file.exists()

    content = config_file.read_text()
    assert 'vault_root = "' in content
    # Loose assertion for media path
    assert "anki" in content and "media" in content
    assert 'backend = "auto"' in content


def test_wizard_custom_flow(mock_home):
    # Inputs:
    # 1. Vault Root -> /custom/vault
    # 2. Anki Media -> /custom/media
    # 3. Backend -> 2 (ankiconnect)
    inputs = [str(Path("/custom/vault")), str(Path("/custom/media")), "2"]

    # We need to mock Path.exists for custom paths to avoid "does not exist" warning prompt logic
    original_exists = Path.exists

    def side_effect_exists(self):
        # Loose matching for cross-platform safety
        s = str(self).replace("\\", "/")
        if "custom/vault" in s or "custom/media" in s:
            return True
        return original_exists(self)

    with patch("builtins.input", side_effect=inputs):
        with patch("pathlib.Path.exists", autospec=True, side_effect=side_effect_exists):
            run_init_wizard()

    config_file = mock_home / ".config/o2a/config.toml"
    content = config_file.read_text()

    # Robust assertion: Check that our custom path fragments are in the file.
    # We avoid asserting strict full paths due to drive letter/separator variances.
    assert "custom" in content
    assert "vault" in content
    assert "media" in content
    assert 'backend = "ankiconnect"' in content


def test_wizard_overwrite_no(mock_home):
    # Create existing config
    config_dir = mock_home / ".config/o2a"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text("old config")

    # Inputs:
    # 1. Vault -> Enter (Default OK)
    # 2. Media -> /fake/media (Explicit because detect returns None)
    # 3. Backend -> Enter (Default OK)
    # 4. Overwrite? -> n
    inputs = ["", str(Path("/fake/media")), "", "n"]

    # Ensure default path exists so we don't get prompted
    (mock_home / "Obsidian Vault").mkdir(parents=True)

    with patch("builtins.input", side_effect=inputs):
        with patch("o2a.core.wizard.detect_anki_paths", return_value=(None, None)):
            original_exists = Path.exists

            def overwrite_exists_side_effect(self):
                s = str(self).replace("\\", "/")
                if "fake/media" in s:
                    return True
                return original_exists(self)

            with patch(
                "pathlib.Path.exists", autospec=True, side_effect=overwrite_exists_side_effect
            ):
                run_init_wizard()

    # Should still satisfy old config
    assert (config_dir / "config.toml").read_text() == "old config"
