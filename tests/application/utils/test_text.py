"""Consolidated tests for arete.application.utils.text and arete.application.utils.common."""

import pytest
import yaml
import yaml.constructor
import yaml.scanner

from arete.application.utils.common import sanitize
from arete.application.utils.text import (
    apply_fixes,
    convert_math_to_tex_delimiters,
    fix_mathjax_escapes,
    make_editor_note,
    parse_frontmatter,
    rebuild_markdown_with_frontmatter,
    scrub_internal_keys,
    validate_frontmatter,
)


# ---------- Math Conversion Tests ----------


def test_math_inline_dollar():
    text = "Let $x=1$ and $y=2$."
    expected = r"Let \(x=1\) and \(y=2\)."
    assert convert_math_to_tex_delimiters(text) == expected


def test_math_block_dollar_simple():
    assert convert_math_to_tex_delimiters("$$abc$$") == r"\[abc\]"


def test_math_block_dollar_multiline():
    text = "BLOCK:\n$$\ncontent\n$$"
    expected = "BLOCK:\n" r"\[" "content" r"\]"
    actual = convert_math_to_tex_delimiters(text)
    assert actual == expected


def test_math_mixed():
    text = r"Inline $a^2$ followed by block $$\int f(x)dx$$"
    assert r"\(a^2\)" in convert_math_to_tex_delimiters(text)
    assert r"\[\int f(x)dx\]" in convert_math_to_tex_delimiters(text)


def test_escaped_dollars():
    text = r"Cost is \$50."
    assert convert_math_to_tex_delimiters(text) == text


def test_math_combined():
    text = "The value is $x$ which is $$x^2$$."
    assert convert_math_to_tex_delimiters(text) == r"The value is \(x\) which is \[x^2\]."


def test_math_in_code_block():
    text = "Code: `x = $y$`"
    expected = r"Code: `x = \(y\)`"
    assert convert_math_to_tex_delimiters(text) == expected


# ---------- Frontmatter Parsing Tests ----------


def test_parse_frontmatter_valid():
    md = "---\ntitle: Hello\ncards:\n  - Front: A\n---\nBody content"
    meta, body = parse_frontmatter(md)
    assert meta["title"] == "Hello"
    assert len(meta["cards"]) == 1
    assert body.strip() == "Body content"


def test_parse_frontmatter_empty():
    md = "Just text, no YAML."
    meta, body = parse_frontmatter(md)
    assert meta == {}
    assert body == md


def test_parse_frontmatter_invalid_yaml():
    md = "---\n: broken yaml\n---\nBody"
    meta, body = parse_frontmatter(md)
    assert "__yaml_error__" in meta
    assert body == md


def test_parse_frontmatter_tabs():
    """Tabs in frontmatter are replaced by spaces during parsing."""
    text = "---\n\tkey: value\n---\ncontent"
    meta, rest = parse_frontmatter(text)
    assert scrub_internal_keys(meta) == {"key": "value"}
    assert rest == "content"


# ---------- Frontmatter Validation Tests ----------


def test_validate_frontmatter_valid():
    content = "---\nfoo: bar\n---\nbody"
    meta = validate_frontmatter(content)
    assert meta["foo"] == "bar"


def test_validate_frontmatter_tabs():
    content = "---\nfoo:\tbar\n---\nbody"
    with pytest.raises(yaml.scanner.ScannerError) as exc:
        validate_frontmatter(content)
    assert "cannot start any token" in str(exc.value)


def test_validate_frontmatter_unclosed():
    content = "---\nfoo: bar\nbody"
    with pytest.raises(yaml.scanner.ScannerError) as exc:
        validate_frontmatter(content)
    assert "Unclosed YAML" in str(exc.value)


def test_validate_frontmatter_tabs_error():
    """Validate_frontmatter strictly raises ScannerError for tabs."""
    text = "---\nkey:\n\tvalue\n---\n"
    with pytest.raises(yaml.scanner.ScannerError) as exc:
        validate_frontmatter(text)
    assert "found character '\\t'" in str(exc.value)


def test_duplicate_keys_error():
    """Verify DuplicateKeyLoader logic via validate_frontmatter."""
    text = "---\nkey: v1\nkey: v2\n---\n"
    with pytest.raises(yaml.constructor.ConstructorError) as exc:
        validate_frontmatter(text)
    assert "found duplicate key 'key'" in str(exc.value)


# ---------- apply_fixes Tests ----------


def test_apply_fixes_tabs():
    raw = "---\nfoo:\tbar\n---\n"
    fixed = apply_fixes(raw)
    assert "foo:  bar" in fixed


def test_apply_fixes_missing_cards():
    raw = "---\ndeck: Default\n---\n"
    fixed = apply_fixes(raw)
    assert "cards: []" in fixed


def test_apply_fixes_template_tags():
    raw = "---\ntitle: {{title}}\n---\n"
    fixed = apply_fixes(raw)
    assert 'title: "{{title}}"' in fixed


def test_apply_fixes_indentation_nid():
    raw = "---\ncards:\n- Front: Q\nnid: 123\n---\n"
    fixed = apply_fixes(raw)
    assert "  nid: 123" in fixed


def test_apply_fixes_latex_indent():
    raw = "---\nKey:\n  \\begin{equation}\n---\n"
    fixed = apply_fixes(raw)
    assert "          \\begin{equation}" in fixed


def test_apply_fixes_multiline_quotes():
    raw = """---
key: "Line 1
  Line 2"
---
"""
    fixed = apply_fixes(raw)
    assert "key: |-" in fixed
    assert "    Line 1" in fixed
    assert "    Line 2" in fixed


def test_apply_fixes_latex_quote_safety():
    raw = """---
math: "\\begin{equation}
   E=mc^2
\\end{equation}"
---
"""
    fixed = apply_fixes(raw)
    assert "math: |-" in fixed
    assert "    \\begin{equation}" in fixed


def test_apply_fixes_no_match():
    """If no frontmatter is present, apply_fixes should do nothing."""
    text = "Just some content"
    assert apply_fixes(text) == text


def test_apply_fixes_no_change_if_valid():
    content = "---\ndeck: D\ncards: []\n---"
    assert apply_fixes(content) == content


# ---------- Other Utils ----------


def test_fix_mathjax_escapes():
    raw = '---\nkey: "Some \\in set"\n---\n'
    fixed = fix_mathjax_escapes(raw)
    assert 'key: "Some \\\\in set"' in fixed


def test_rebuild_markdown_roundtrip():
    meta = {"nid": "123", "cards": []}
    body = "Original Body"
    rebuilt = rebuild_markdown_with_frontmatter(meta, body)

    parsed_meta, parsed_body = parse_frontmatter(rebuilt)
    assert parsed_meta["nid"] == "123"
    assert parsed_body.strip() == "Original Body"


def test_rebuild_markdown_format():
    meta = {"foo": "bar"}
    body = "Content"
    full_text = rebuild_markdown_with_frontmatter(meta, body)
    assert full_text.startswith("---\n")
    assert "foo: bar" in full_text
    assert "Content" in full_text


def test_sanitize():
    assert sanitize("<b>Bold</b>") == "<b>Bold</b>"
    assert sanitize("Line<br>Break") == "Line<br>Break"
    assert sanitize("Div    ") == "Div"
    assert sanitize(None) == ""


# ---------- make_editor_note Tests ----------


def test_make_editor_note_basic():
    note = make_editor_note(
        model="Basic",
        deck="MyDeck",
        tags=["t1", "t2"],
        fields={"Front": "Q", "Back": "A"},
        nid="999",
    )
    assert "nid: 999" in note
    assert "model: Basic" in note
    assert "deck: MyDeck" in note
    assert "tags: t1 t2" in note
    assert "## Front" in note
    assert "## Back" in note
    assert "Q" in note
    assert "A" in note


def test_make_editor_note_cloze():
    fields = {"Text": "cloze {{c1::test}}", "Back Extra": "extra", "Extra": "backup"}
    out = make_editor_note("Cloze", "deck", ["t1"], fields, nid="123")

    assert "nid: 123" in out
    assert "model: Cloze" in out
    assert "## Text" in out
    assert "cloze {{c1::test}}" in out
    assert "## Back Extra" in out
    assert "extra" in out


def test_make_editor_note_cid_only_no_nid():
    out = make_editor_note("Basic", "Default", [], {}, cid="999", nid=None)
    assert "cid: 999" in out
    assert "nid:" not in out


def test_make_editor_note_cloze_fallback_extra():
    """Test Cloze model fallback to 'Extra' if 'Back Extra' is missing."""
    fields = {"Text": "cloze", "Extra": "fallback_extra"}
    out = make_editor_note("Cloze", "deck", [], fields)
    assert "## Back Extra" in out
    assert "fallback_extra" in out
