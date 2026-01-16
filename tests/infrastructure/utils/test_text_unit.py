import pytest
from yaml.scanner import ScannerError

from arete.infrastructure.utils.common import sanitize
from arete.infrastructure.utils.text import (
    apply_fixes,
    convert_math_to_tex_delimiters,
    fix_mathjax_escapes,
    rebuild_markdown_with_frontmatter,
    validate_frontmatter,
)


def test_convert_math():
    # Block $$ -> \[ \]
    assert convert_math_to_tex_delimiters("$$x^2$$") == r"\[x^2\]"
    # Inline $ -> \( \)
    assert convert_math_to_tex_delimiters("$x$") == r"\(x\)"
    # Combined
    text = "The value is $x$ which is $$x^2$$."
    assert convert_math_to_tex_delimiters(text) == r"The value is \(x\) which is \[x^2\]."


def test_validate_frontmatter_valid():
    content = "---\nfoo: bar\n---\nbody"
    meta = validate_frontmatter(content)
    assert meta["foo"] == "bar"


def test_validate_frontmatter_tabs():
    content = "---\nfoo:\tbar\n---\nbody"
    with pytest.raises(ScannerError) as exc:
        validate_frontmatter(content)
    assert "cannot start any token" in str(exc.value)


def test_validate_frontmatter_unclosed():
    content = "---\nfoo: bar\nbody"
    with pytest.raises(ScannerError) as exc:
        validate_frontmatter(content)
    assert "Unclosed YAML" in str(exc.value)


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
    # Logic: 0-3 spaces before \ -> 10 spaces
    fixed = apply_fixes(raw)
    assert "          \\begin{equation}" in fixed


def test_fix_mathjax_escapes():
    raw = '---\nkey: "Some \\in set"\n---\n'
    fixed = fix_mathjax_escapes(raw)
    assert 'key: "Some \\\\in set"' in fixed


def test_apply_fixes_multiline_quotes():
    # Test the logic that converts broken/multiline quotes to block scalars
    # Case 1: Unclosed quote on same line, continues next line
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
    # Complex LaTeX that typically breaks generic YAML parsers if quoted
    raw = """---
math: "\\begin{equation}
   E=mc^2
\\end{equation}"
---
"""
    fixed = apply_fixes(raw)
    assert "math: |-" in fixed
    assert "    \\begin{equation}" in fixed


def test_rebuild_markdown():
    meta = {"foo": "bar"}
    body = "Content"
    full_text = rebuild_markdown_with_frontmatter(meta, body)
    assert full_text.startswith("---\n")
    assert "foo: bar" in full_text
    assert "Content" in full_text


def test_sanitize():
    assert sanitize("<b>Bold</b>") == "<b>Bold</b>"  # does not strip tags, just str().rstrip()
    assert sanitize("Line<br>Break") == "Line<br>Break"
    assert sanitize("Div    ") == "Div"
    assert sanitize(None) == ""
