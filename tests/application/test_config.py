from pathlib import Path

from arete.application.config import resolve_config


def test_config_defaults(mock_home, mock_vault):
    # Setup args
    overrides = {
        "root_input": str(mock_vault),
        "verbose": 0,
    }

    cfg = resolve_config(overrides)

    assert cfg.root_input == mock_vault.resolve()
    assert cfg.verbose == 0
    assert cfg.backend == "auto"


def test_config_file_override(mock_home, mock_vault):
    # Write a config file
    config_dir = mock_home / ".config/arete"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text("verbose = 2\nrun = true", encoding="utf-8")

    overrides = {
        "root_input": str(mock_vault),
        # Note: Pydantic doesn't treat False as an override for booleans
        # So we test that config file values are loaded
    }

    cfg = resolve_config(overrides, config_file=config_dir / "config.toml")
    assert cfg.verbose == 2  # From config
    assert cfg.run_apy is True  # From config file


def test_config_default_cwd_when_no_path(mock_home):
    # Setup args with no path
    overrides = {}

    cfg = resolve_config(overrides)
    assert cfg.root_input == Path.cwd().resolve()
