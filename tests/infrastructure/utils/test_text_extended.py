import pytest
import yaml
import yaml.constructor
import yaml.scanner

from arete.infrastructure.utils.text import (
    apply_fixes,
    make_editor_note,
    parse_frontmatter,
    scrub_internal_keys,
    validate_frontmatter,
)


def test_parse_frontmatter_tabs():
    """
    Test that tabs in frontmatter are replaced by spaces during parsing.
    """
    text = "---\n\tkey: value\n---\ncontent"
    meta, rest = parse_frontmatter(text)
    assert scrub_internal_keys(meta) == {"key": "value"}
    assert rest == "content"


def test_validate_frontmatter_tabs_error():
    """
    Test that validate_frontmatter strictly raises ScannerError for tabs.
    """
    text = "---\nkey:\n\tvalue\n---\n"
    with pytest.raises(yaml.scanner.ScannerError) as exc:
        validate_frontmatter(text)

    # We expect our custom error structure
    assert "found character '\\t'" in str(exc.value)


def test_duplicate_keys_error():
    """
    Verify DuplicateKeyLoader logic via validate_frontmatter.
    """
    text = "---\nkey: v1\nkey: v2\n---\n"
    with pytest.raises(yaml.constructor.ConstructorError) as exc:
        validate_frontmatter(text)
    assert "found duplicate key 'key'" in str(exc.value)


def test_apply_fixes_no_match():
    """
    If no frontmatter is present, apply_fixes should do nothing.
    """
    text = "Just some content"
    assert apply_fixes(text) == text


def test_make_editor_note_cloze():
    """
    Test Cloze model specific fields.
    """
    fields = {"Text": "cloze {{c1::test}}", "Back Extra": "extra", "Extra": "backup"}
    out = make_editor_note("Cloze", "deck", ["t1"], fields, nid="123")

    assert "nid: 123" in out
    assert "model: Cloze" in out
    assert "## Text" in out
    assert "cloze {{c1::test}}" in out
    assert "## Back Extra" in out
    assert "extra" in out


def test_make_editor_note_cid_only_no_nid():
    """
    Test generation with cid but no nid.
    """
    out = make_editor_note("Basic", "Default", [], {}, cid="999", nid=None)
    assert "cid: 999" in out
    assert "nid:" not in out


def test_make_editor_note_cloze_fallback_extra():
    """
    Test Cloze model fallback to 'Extra' if 'Back Extra' is missing.
    """
    fields = {"Text": "cloze", "Extra": "fallback_extra"}
    out = make_editor_note("Cloze", "deck", [], fields)
    assert "## Back Extra" in out
    assert "fallback_extra" in out
