from arete.text import apply_fixes


def test_fix_tabs():
    content = "---\ndeck: D\n\tbad: val\n---"
    fixed = apply_fixes(content)
    assert "\t" not in fixed
    assert "  bad: val" in fixed


def test_fix_missing_cards():
    content = "---\ndeck: D\n---"
    fixed = apply_fixes(content)
    assert "cards: []" in fixed


def test_no_change_if_valid():
    content = "---\ndeck: D\ncards: []\n---"
    assert apply_fixes(content) == content
