from unittest.mock import patch

from arete.application.utils.fs import file_md5, iter_markdown_files


def test_fs_iter_single_file(tmp_path):
    f = tmp_path / "test.md"
    f.touch()
    files = list(iter_markdown_files(f))
    assert files == [f]


def test_fs_iter_hidden_skip(tmp_path):
    d = tmp_path / "dir"
    d.mkdir()
    hidden_dir = d / ".hidden"
    hidden_dir.mkdir()
    f = hidden_dir / "test.md"
    f.touch()

    files = list(iter_markdown_files(d))
    assert f not in files


def test_fs_iter_skip_dirs(tmp_path):
    d = tmp_path / "vault"
    d.mkdir()
    git_dir = d / ".git"
    git_dir.mkdir()
    f = git_dir / "test.md"
    f.touch()

    files = list(iter_markdown_files(d))
    assert f not in files


def test_fs_iter_value_error(tmp_path):
    with patch("pathlib.Path.relative_to", side_effect=ValueError("Mismatch")):
        d = tmp_path / "dir"
        d.mkdir()
        f = d / "test.md"
        f.touch()
        files = list(iter_markdown_files(d))
        assert files == [f]


def test_fs_file_md5(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello world")
    h1 = file_md5(f)
    assert len(h1) == 32

    f.write_text("hello world!")
    h2 = file_md5(f)
    assert h1 != h2
