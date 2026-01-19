"""Markdown to Anki HTML conversion logic.
Extracted from apy logic to allow direct Python usage.
"""

from __future__ import annotations

import re

import markdown
from markdown.extensions import Extension
from markdown.postprocessors import Postprocessor
from markdown.preprocessors import Preprocessor


class MathProtectExtension(Extension):
    """Extension to avoid converting markdown within math blocks"""

    def __init__(self, markdown_latex_mode: str = "mathjax") -> None:
        super().__init__()
        self.markdown_latex_mode: str = markdown_latex_mode

    def extendMarkdown(self, md: markdown.Markdown) -> None:
        math_preprocessor = MathPreprocessor(md, self.markdown_latex_mode)
        math_postprocessor = MathPostprocessor(md, math_preprocessor.placeholders)

        md.preprocessors.register(math_preprocessor, "math_block_processor", 25)
        md.postprocessors.register(math_postprocessor, "math_block_restorer", 25)


class MathPreprocessor(Preprocessor):
    def __init__(self, md: markdown.Markdown, markdown_latex_mode: str) -> None:
        super().__init__(md)
        self.counter: int = 0
        self.placeholders: dict[str, str] = {}

        # Apply latex translation based on specified latex mode
        if markdown_latex_mode == "latex":
            self.fmt_display: str = "[$$]{math}[/$$]"
            self.fmt_inline: str = "[$]{math}[/$]"
        else:
            # Default to MathJax style
            self.fmt_display = r"\[{math}\]"
            self.fmt_inline = r"\({math}\)"

    def run(self, lines: list[str]) -> list[str]:
        def replacer(match: re.Match[str]) -> str:
            placeholder = f"MATH-PLACEHOLDER-{self.counter}"
            self.counter += 1

            if matched := match.group(1):
                self.placeholders[placeholder] = self.fmt_display.format(math=matched)
            elif matched := match.group(2):
                self.placeholders[placeholder] = self.fmt_inline.format(math=matched)

            return placeholder

        pattern = re.compile(r"\$\$(.*?)\$\$|\$(.*?)\$", re.DOTALL)
        lines_joined = "\n".join(lines)
        lines_processed = pattern.sub(replacer, lines_joined)
        return lines_processed.split("\n")


class MathPostprocessor(Postprocessor):
    def __init__(self, md: markdown.Markdown, placeholders: dict[str, str]) -> None:
        super().__init__(md)
        self.placeholders: dict[str, str] = placeholders

    def run(self, text: str) -> str:
        for placeholder, math in self.placeholders.items():
            text = text.replace(placeholder, math)
        return text


_md_instance: markdown.Markdown | None = None


def markdown_to_anki_html(text: str, latex_mode: str = "mathjax") -> str:
    """Convert markdown text to Anki-compatible HTML.
    Includes special handling for MathJax protection.
    """
    global _md_instance
    if _md_instance is None:
        _md_instance = markdown.Markdown(
            extensions=[
                "fenced_code",
                "tables",
                MathProtectExtension(latex_mode),
            ]
        )
    else:
        _md_instance.reset()

    html = _md_instance.convert(text)
    # Add arete's marker comment for consistency detection if needed
    # but strictly speaking we don't need it if we trust our DB.
    # We'll add it to match apy behavior for now.
    return f"<!-- arete markdown -->\n{html}"
