from unittest.mock import patch

from o2a.core.wizard import run_init_wizard


def test_wizard_successful_flow(tmp_path):
    new_home = tmp_path / "home"
    new_home.mkdir()
    v = tmp_path / "v"
    v.mkdir()
    m = tmp_path / "m"
    m.mkdir()
    with patch("pathlib.Path.home", return_value=new_home):
        with patch("o2a.core.wizard.detect_anki_paths", return_value=(None, None)):
            with patch("builtins.input", side_effect=[str(v), str(m), "1"]):
                run_init_wizard()
    assert (new_home / ".config/o2a/config.toml").exists()


def test_wizard_path_validation_and_reprompt(tmp_path):
    new_home = tmp_path / "home"
    new_home.mkdir()
    v_good = tmp_path / "good_v"
    v_good.mkdir()
    m = tmp_path / "m"
    m.mkdir()

    with patch("pathlib.Path.home", return_value=new_home):
        with patch("o2a.core.wizard.detect_anki_paths", return_value=(None, None)):
            with patch(
                "builtins.input",
                side_effect=[
                    str(v_good),
                    "",  # empty for media (no default) -> "Value required"
                    str(m),
                    "1",
                ],
            ):
                run_init_wizard()
    assert (new_home / ".config/o2a/config.toml").exists()


def test_wizard_nonexistent_confirm(tmp_path):
    new_home = tmp_path / "home"
    new_home.mkdir()
    v_bad = tmp_path / "bad_v"
    m_bad = tmp_path / "bad_m"
    with patch("pathlib.Path.home", return_value=new_home):
        with patch("o2a.core.wizard.detect_anki_paths", return_value=(None, None)):
            with patch("builtins.input", side_effect=[str(v_bad), "y", str(m_bad), "y", "1"]):
                run_init_wizard()
    assert (new_home / ".config/o2a/config.toml").exists()


def test_wizard_overwrite_abort(tmp_path):
    new_home = tmp_path / "home"
    new_home.mkdir()
    config_dir = new_home / ".config/o2a"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.toml"
    config_file.write_text("old")
    v = tmp_path / "v"
    v.mkdir()
    m = tmp_path / "m"
    m.mkdir()
    with patch("pathlib.Path.home", return_value=new_home):
        with patch("o2a.core.wizard.detect_anki_paths", return_value=(None, None)):
            with patch("builtins.input", side_effect=[str(v), str(m), "1", "n"]):
                run_init_wizard()
    assert config_file.read_text() == "old"


def test_wizard_backend_choices(tmp_path):
    new_home = tmp_path / "home"
    new_home.mkdir()
    v = tmp_path / "v"
    v.mkdir()
    m = tmp_path / "m"
    m.mkdir()
    with patch("pathlib.Path.home", return_value=new_home):
        with patch("o2a.core.wizard.detect_anki_paths", return_value=(None, None)):
            with patch("builtins.input", side_effect=[str(v), str(m), "2"]):
                run_init_wizard()
    assert 'backend = "ankiconnect"' in (new_home / ".config/o2a/config.toml").read_text()


def test_wizard_write_error(tmp_path):
    new_home = tmp_path / "home"
    new_home.mkdir()
    v = tmp_path / "v"
    v.mkdir()
    m = tmp_path / "m"
    m.mkdir()
    with patch("pathlib.Path.home", return_value=new_home):
        with patch("o2a.core.wizard.detect_anki_paths", return_value=(None, None)):
            with patch("builtins.input", side_effect=[str(v), str(m), "1", "y"]):
                with patch("builtins.open", side_effect=OSError("Permission denied")):
                    run_init_wizard()
