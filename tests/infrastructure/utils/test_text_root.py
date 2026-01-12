from arete.infrastructure.utils.text import (
    convert_math_to_tex_delimiters,
    make_editor_note,
    parse_frontmatter,
    rebuild_markdown_with_frontmatter,
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
    # NOTE: The implementation Pipeline is: $$ -> \[ \] THEN \[ \] -> \[ \].
    # The second step (handling existing \[ \]) happens to strip leading/trailing whitespace
    # due to \s* in its regex. So the final output consumes the newlines inside the block.
    expected = "BLOCK:\n" r"\[" "content" r"\]"
    actual = convert_math_to_tex_delimiters(text)
    assert actual == expected


def test_math_mixed():
    text = r"Inline $a^2$ followed by block $$\int f(x)dx$$"
    # Note: Logic does blocks FIRST, then inline.
    assert r"\(a^2\)" in convert_math_to_tex_delimiters(text)
    assert r"\[\int f(x)dx\]" in convert_math_to_tex_delimiters(text)


def test_escaped_dollars():
    # Should NOT convert \$
    text = r"Cost is \$50."
    assert convert_math_to_tex_delimiters(text) == text


# ---------- Frontmatter Tests ----------


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
    assert body == md  # Should return original text as "body" if parse fails?
    # Viewing text.py: "return {"__yaml_error__": ...}, md_text" -> YES.


def test_rebuild_markdown():
    meta = {"nid": "123", "cards": []}
    body = "Original Body"
    rebuilt = rebuild_markdown_with_frontmatter(meta, body)

    # Should have --- ... --- ... Body
    parsed_meta, parsed_body = parse_frontmatter(rebuilt)
    assert parsed_meta["nid"] == "123"
    assert parsed_body.strip() == "Original Body"


# ---------- Editor Note Tests ----------


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


def test_math_in_code_block():
    # Currently, our regex is "naive" regarding code blocks.
    # It converts $...$ anywhere unless escaped.
    # This test documents that behavior.
    text = "Code: `x = $y$`"
    # We expect it TO convert, because we don't parse markdown structure deeply.
    expected = r"Code: `x = \(y\)`"
    assert convert_math_to_tex_delimiters(text) == expected
