import re

# ---------- Config / Regex ----------

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*", re.DOTALL)
CURRENT_TEMPLATE_VERSION = 1  # strict
VERSION = "1.3.0"

# Image patterns
WIKILINK_IMG_RE = re.compile(r"!\[\[([^\]]+)\]\]")  # ![[path|...]]
MARKDOWN_IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")  # ![](path)

# output parsing (robust to spacing)
RE_NID = re.compile(r"^\s*\*\s*nid:\s*(\d+)\b", re.IGNORECASE | re.MULTILINE)
RE_CID = re.compile(r"^\s*\*\s*cid:\s*(\d+)\b", re.IGNORECASE | re.MULTILINE)
