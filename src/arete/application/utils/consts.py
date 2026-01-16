import re

# ---------- Config / Regex ----------

# Matches frontmatter with optional leading BOM/whitespace and handles \r\n
FRONTMATTER_RE = re.compile(r"^\s*---\s*\r?\n(.*?)\r?\n---\s*", re.DOTALL)
CURRENT_TEMPLATE_VERSION = 1  # strict

# Image patterns
WIKILINK_IMG_RE = re.compile(r"!\[\[([^\]]+)\]\]")  # ![[path|...]]
MARKDOWN_IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")  # ![](path)

# apy output parsing (robust to spacing)
RE_NID = re.compile(r"^\s*\*\s*nid:\s*(\d+)\b", re.IGNORECASE | re.MULTILINE)
RE_CID = re.compile(r"^\s*\*\s*cid:\s*(\d+)\b", re.IGNORECASE | re.MULTILINE)
