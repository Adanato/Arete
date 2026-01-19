import yaml

from arete import __version__
from arete.application.utils.yaml import _LiteralDumper


def test_version_exists():
    assert isinstance(__version__, str)
    assert len(__version__) > 0


def test_yaml_literal_dumper_dict():
    """Test _LiteralDumper handling a dict (branch checking)."""
    data = {"key": "multi\nline\nstring"}
    out = yaml.dump(data, Dumper=_LiteralDumper)
    assert "|" in out or ">" in out  # Depending on heuristic, but verifying it runs


def test_hello():
    from arete import hello

    assert "obsidian-2-anki" in hello()
