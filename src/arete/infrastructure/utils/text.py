import re
from typing import Any

import yaml  # type: ignore
import yaml.constructor
import yaml.error
import yaml.scanner  # type: ignore

from .common import sanitize
from .consts import FRONTMATTER_RE
from .yaml import _LiteralDumper

# ---------- Math: Normalize to \( \) and \[ \] delimiters ----------


def convert_math_to_tex_delimiters(text: str) -> str:
    # 1) Blocks first
    block_dollars = re.compile(r"(?<!\\)\$\$(.*?)(?<!\\)\$\$", re.DOTALL)
    block_brackets = re.compile(r"\\\[\s*(.*?)\s*\\\]", re.DOTALL)
    block_bbcode = re.compile(r"\[\$\$\]\s*(.*?)\s*\[/\$\$\]", re.DOTALL)

    def to_block(m: re.Match) -> str:
        return r"\[" + m.group(1) + r"\]"

    out = text
    out = block_dollars.sub(to_block, out)
    out = block_bbcode.sub(to_block, out)
    out = block_brackets.sub(to_block, out)

    # 2) Inline next
    inline_dollar = re.compile(r"(?<!\\)\$(?!\$)(.*?)(?<!\\)\$", re.DOTALL)
    inline_paren = re.compile(r"\\\(\s*(.*?)\s*\\\)", re.DOTALL)
    inline_bbcode = re.compile(r"\[\$\]\s*(.*?)\s*\[/\$\]", re.DOTALL)

    def to_inline(m: re.Match) -> str:
        return r"\(" + m.group(1) + r"\)"

    out = inline_dollar.sub(to_inline, out)
    out = inline_bbcode.sub(to_inline, out)
    out = inline_paren.sub(to_inline, out)

    return out


# ---------- Frontmatter helpers ----------


def parse_frontmatter(md_text: str) -> tuple[dict[str, Any], str]:
    # Handle potential BOM (Byte Order Mark)
    md_text = md_text.lstrip("\ufeff")
    m = FRONTMATTER_RE.match(md_text)
    if not m:
        return {}, md_text
    raw = m.group(1)
    if "\t" in raw:
        raw = raw.replace("\t", "  ")
    try:
        # Use our custom loader to get line numbers and handle duplicates
        meta = yaml.load(raw, Loader=UniqueKeyLoader) or {}

        # Add offset to __line__ to make it absolute
        # m.start(1) is the beginning of the captured YAML content.
        offset = md_text[: m.start(1)].count("\n")

        def _add_offset(d):
            if isinstance(d, dict):
                if "__line__" in d:
                    d["__line__"] += offset
                for v in d.values():
                    _add_offset(v)
            elif isinstance(d, list):
                for v in d:
                    _add_offset(v)

        _add_offset(meta)

    except Exception as e:
        return {"__yaml_error__": str(e)}, md_text
    rest = md_text[m.end() :]
    return meta, rest


class UniqueKeyLoader(yaml.SafeLoader):
    """
    Custom YAML loader that forbids duplicate keys.
    """

    def construct_mapping(self, node, deep=False):
        mapping = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in mapping:
                raise yaml.constructor.ConstructorError(
                    None, None, f"found duplicate key '{key}'", key_node.start_mark
                )
            mapping.add(key)

        result = super().construct_mapping(node, deep)
        if isinstance(result, dict):
            # Inject line number (1-based)
            result["__line__"] = node.start_mark.line + 1
        return result


def validate_frontmatter(md_text: str) -> dict[str, Any]:
    """
    Parses frontmatter but raises detailed exceptions on failure.
    Returns the metadata dict if successful.
    """
    # Handle potential BOM (Byte Order Mark)
    md_text = md_text.lstrip("\ufeff")
    m = FRONTMATTER_RE.match(md_text)
    if not m:
        # Detect unclosed frontmatter
        if md_text.startswith("---"):
            err = yaml.scanner.ScannerError(
                problem="Unclosed YAML frontmatter. Found starting '---' but no closing '---'.",
                problem_mark=yaml.error.Mark("name", 0, 1, -1, "", 0),
            )
            raise err
        return {}

    # Calculate offset lines (how many newlines before the content starts)
    # m.start(1) is the index where the capture group begins.
    pre_content = md_text[: m.start(1)]
    offset = pre_content.count("\n")

    raw = m.group(1)

    # Strict validation: Explicitly forbid tabs anywhere in frontmatter
    # Obsidian strictly forbids them, and PyYAML is too permissive sometimes.
    if "\t" in raw:
        # Create a mock error to pass to our exception handler
        # We find the line number of the first tab
        tab_index = raw.find("\t")
        lines_before_tab = raw[:tab_index].count("\n")
        line = lines_before_tab + 1

        # We raise a generic YAMLError which cli.py catches
        # We manually construct a problem mark
        err = yaml.scanner.ScannerError(
            problem="found character '\\t' that cannot start any token",
            problem_mark=yaml.error.Mark("name", 0, line, -1, "", 0),
        )
        # Adjust line offset immediately
        if offset:
            err.problem_mark.line += offset  # type: ignore
        raise err

    try:
        return yaml.load(raw, Loader=UniqueKeyLoader) or {}
    except yaml.YAMLError as e:
        # Adjust the line number in the exception to match the file
        if hasattr(e, "problem_mark"):
            e.problem_mark.line += offset  # type: ignore
        raise e


def scrub_internal_keys(d: Any) -> Any:
    """Recursively remove keys starting with __"""
    if isinstance(d, dict):
        return {k: scrub_internal_keys(v) for k, v in d.items() if not k.startswith("__")}
    elif isinstance(d, list):
        return [scrub_internal_keys(v) for v in d]
    return d


def rebuild_markdown_with_frontmatter(meta: dict[str, Any], body: str) -> str:
    clean_meta = scrub_internal_keys(meta)
    yaml_text = yaml.dump(
        clean_meta,
        Dumper=_LiteralDumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=10**9,
    )
    return f"---\n{yaml_text}---\n{body}"


# ---------- Build apy editor-note text ----------
def apply_fixes(md_text: str) -> str:
    """
    Attempts to fix common frontmatter issues safely.
    1. Tabs -> Spaces
    2. Missing 'cards' list
    3. Skip leading empty blocks (requested: 'skip empty --- bruh')
    4. Indentation for nid/cid (ensure not at 0)
    5. Template tags ({{title}} -> "{{title}}")
    6. LaTeX lines under-indented (starts with \\)
    7. Quoted backslashes (double quotes -> single quotes)
    8. nid/cid on same line as field
    9. Unclosed quotes on mapping fields
    """
    # a. Robust empty dashes skip at the VERY START
    md_text = md_text.lstrip()
    while re.match(r"^---\s*\n(\s*\n)*---\s*\n", md_text):
        md_text = re.sub(r"^---\s*\n(\s*\n)*---\s*\n", "", md_text, count=1)
        md_text = md_text.lstrip()

    m = FRONTMATTER_RE.match(md_text)
    if not m:
        return md_text

    original_fm = m.group(1)
    new_fm = original_fm

    # 1. Fix Tabs
    if "\t" in new_fm:
        new_fm = new_fm.replace("\t", "  ")

    # 2. Fix Missing Cards
    has_deck_or_model = "deck:" in new_fm or "model:" in new_fm
    has_cards = "cards:" in new_fm

    if has_deck_or_model and not has_cards:
        if not new_fm.endswith("\n"):
            new_fm += "\n"
        new_fm += "cards: []\n"

    # 3. Fix Template Tags ({{title}} -> "{{title}}")
    new_fm = re.sub(r"(:\s*)\{\{(.*?)\}\}", r'\1"{{\2}}"', new_fm)

    # 4. Same-line metadata (Active Recall case)
    # If we see "content  nid: '123'", split it.
    new_fm = re.sub(r"([^\n])\s+(nid|cid):", r"\1\n  \2:", new_fm)

    # 5. Modernize Quoted Fields (Groups.md case)
    # If a field starts with a quote but doesn't end with one on the same line,
    # or if it contains multiple lines, convert to a block scalar |- for safety.
    lines = new_fm.split("\n")
    fixed_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Match Key: 'content or - Key: 'content
        m_q = re.match(r'^(\s*(?:-\s*)?[A-Za-z]+:\s*([\'"]))(.*)$', line)
        if m_q and i < len(lines):
            prefix, quote, content = m_q.groups()
            # If the quote is unclosed OR it's a known problematic LaTeX field
            # and it doesn't end neatly on this line...
            if not content.strip().endswith(quote) or ("\\" in content and len(content) > 50):
                # We have a multiline/problematic quoted field! Convert to |-
                key_prefix = prefix[: prefix.find(":") + 1]
                fixed_lines.append(f"{key_prefix} |-")

                # Push the first line's content (strip the opening quote)
                first_content = content.strip().lstrip(quote)
                if first_content:
                    # If it ends with the quote, strip it and stop here
                    if first_content.endswith(quote):
                        fixed_lines.append(f"    {first_content[:-1]}")
                        i += 1
                        continue
                    fixed_lines.append(f"    {first_content}")

                # Consume subsequent lines
                i += 1
                while i < len(lines):
                    next_line = lines[i]
                    # SAFETY: If we hit metadata (nid/cid), stop consuming!
                    if re.match(r"^\s*(nid|cid):", next_line):
                        # Don't increment i, let the outer loop handle it
                        break

                    # If this line ends with the closing quote, strip it and stop
                    if next_line.strip().endswith(quote):
                        last_content = next_line.strip()[:-1]
                        if last_content:
                            fixed_lines.append(f"    {last_content}")
                        i += 1  # Successfully consumed the closing quote line
                        break

                    fixed_lines.append(f"    {next_line.strip()}")
                    i += 1
                continue

        fixed_lines.append(line)
        i += 1
    new_fm = "\n".join([line for line in fixed_lines if line is not None])

    # 6. Fix nid/cid indentation
    new_fm = re.sub(r"^[ ]{0,1}(nid|cid):", r"  \1:", new_fm, flags=re.MULTILINE)

    # 7. LaTeX lines under-indented (Groups.md case)
    new_fm = re.sub(r"^[ ]{0,3}(\\)", r"          \1", new_fm, flags=re.MULTILINE)

    # 8. Convert double quotes to single quotes for strings with backslashes (ura-02 case)
    # This identifies "..." strings that treat \ as escape, which breaks LaTeX/WikiLinks.
    # We use a robust regex that handles escaped quotes: "(?:[^"\\]|\\.)*"
    def quote_fix(match):
        prefix, content = match.groups()
        # If the content has backslashes (like LaTeX) but NO unescaped double-quotes
        # conversion to single quotes is safer as it treats \ literally.
        # But if it HAS double quotes (likely escaped), we must leave it as is or fix differently.
        # Check for unescaped double quotes inside content
        if "\\" in content and '"' not in content:
            return f"{prefix}'{content}'"
        return match.group(0)

    new_fm = re.sub(r'(\s*-\s*|\s*[A-Za-z]+:\s*)"((?:[^"\\]|\\.)*)"', quote_fix, new_fm)

    # 9. Fix invalid block scalar start (common math error: Back: | '...)
    new_fm = re.sub(r'(\|[-+]?)\s*([\'"])', r"\2", new_fm)

    if new_fm != original_fm:
        start, end = m.span(1)
        md_text = md_text[:start] + new_fm + md_text[end:]

    return md_text


def fix_mathjax_escapes(md_text: str) -> str:
    """
    Finds double-quoted strings in frontmatter that contain common MathJax
    escapes like \\in or \\mathbb and ensures they are double-escaped so
    PyYAML can parse them. This allows us to migrate broken files to |- blocks.
    """
    m = FRONTMATTER_RE.match(md_text)
    if not m:
        return md_text

    original_fm = m.group(1)
    # Simple heuristic for YAML 1.2 double-quote escapes: 0 abt nr vf e " / \ L P _
    valid_escapes = '0abtnrvfe"/\\ '

    def fix_line(line: str) -> str:
        # Match lines that look like key: "..." or - key: "..."
        # We use a regex to find the content between the first and last quote.
        import re

        match = re.search(r'^(\s*(?:-\s*)?[^:]+:\s*)"(.*)"\s*$', line)
        if match:
            prefix, val = match.groups()
            new_val = ""
            i = 0
            while i < len(val):
                if val[i] == "\\":
                    # Check if it's a valid escape sequence (like \n or \\)
                    if i + 1 < len(val) and val[i + 1] in valid_escapes:
                        new_val += "\\" + val[i + 1]
                        i += 2
                    else:
                        # Broken escape (like \i or \{). Escape the backslash.
                        new_val += "\\\\"
                        i += 1
                else:
                    new_val += val[i]
                    i += 1
            return f'{prefix}"{new_val}"'
        return line

    lines = original_fm.split("\n")
    fixed_lines = [fix_line(line) for line in lines]
    new_fm = "\n".join(fixed_lines)

    if new_fm != original_fm:
        start, end = m.span(1)
        return md_text[:start] + new_fm + md_text[end:]

    return md_text


def make_editor_note(
    model: str,
    deck: str,
    tags: list[str],
    fields: dict[str, str],
    nid: str | None = None,
    cid: str | None = None,
    markdown: bool = True,
) -> str:
    lines = []
    if nid:
        lines.append(f"nid: {nid}")
    if cid and not nid:
        lines.append(f"cid: {cid}")
    lines += [f"model: {model}", f"deck: {deck}"]
    if tags:
        lines.append(f"tags: {' '.join(tags)}")
    lines += [f"markdown: {'true' if markdown else 'false'}", "", "# Note", ""]
    mlow = model.lower()
    if mlow == "basic":
        f_list = ["Front", "Back"]
    elif mlow == "cloze":
        f_list = ["Text", "Back Extra"]
    else:
        f_list = sorted(fields.keys())

    # Always ensure _obsidian_source is included if present
    if "_obsidian_source" in fields and "_obsidian_source" not in f_list:
        f_list.append("_obsidian_source")

    for k in f_list:
        v = fields.get(k, "")
        if k == "Back Extra" and not v:
            v = fields.get("Extra", "")
        lines += [f"## {k}", sanitize(v), ""]
    return "\n".join(lines)
