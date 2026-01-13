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
    m = FRONTMATTER_RE.match(md_text)
    if not m:
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
    """
    m = FRONTMATTER_RE.match(md_text)
    if not m:
        return md_text

    original_fm = m.group(1)
    new_fm = original_fm

    # 1. Fix Tabs
    if "\t" in new_fm:
        new_fm = new_fm.replace("\t", "  ")

    # 2. Fix Missing Cards
    # Basic heuristic: if 'deck' or 'model' exists but 'cards' does not.
    # checking for "cards:" substring is simple but effective for now.
    has_deck_or_model = "deck:" in new_fm or "model:" in new_fm
    has_cards = "cards:" in new_fm

    if has_deck_or_model and not has_cards:
        # Append cards list at the end of frontmatter
        if not new_fm.endswith("\n"):
            new_fm += "\n"
        new_fm += "cards: []\n"

    # Reconstruct
    if new_fm != original_fm:
        # Replace only the captured group content
        # We need to preserve the surrounding --- markers which are in group 0 but not 1
        # Actually FRONTMATTER_RE includes the markers in the full match, group 1 is just content.
        # So we replace the range of group 1.
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
