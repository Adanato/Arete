#!/usr/bin/env python3
import argparse
import logging
import os
import re
import subprocess
import sys
import tempfile
import uuid
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("Missing dependency: pyyaml\n  pip install pyyaml", file=sys.stderr)
    sys.exit(1)

# ---------- Config / Regex ----------

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*", re.DOTALL)

# Template version (strict)
CURRENT_TEMPLATE_VERSION = 1

# ---------- Logging ----------


def setup_logging(log_dir: Path) -> tuple[logging.Logger, Path, str]:
    log_dir.mkdir(parents=True, exist_ok=True)
    run_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{uuid.uuid4().hex[:8]}"
    log_path = log_dir / f"run_{run_id}.log"

    logger = logging.getLogger("obsidian2apy")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    # Console
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    # File
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

    logger.addHandler(sh)
    logger.addHandler(fh)

    return logger, log_path, run_id


# ---------- Helpers ----------


def parse_frontmatter(md_text: str) -> tuple[dict[str, Any], str]:
    m = FRONTMATTER_RE.match(md_text)
    if not m:
        return {}, md_text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except Exception as e:
        # YAML parse error
        return {"__yaml_error__": str(e)}, md_text
    rest = md_text[m.end() :]
    return meta, rest


def to_list(x) -> list[str]:
    if x is None:
        return []
    if isinstance(x, list):
        return [str(i) for i in x]
    return [str(x)]


def sanitize(v) -> str:
    return "" if v is None else str(v).rstrip()


def make_editor_note(model: str, deck: str, tags: list[str], fields: dict[str, str]) -> str:
    tag_line = " ".join(tags) if tags else ""
    lines = [
        f"model: {model}",
        f"deck: {deck}",
        f"tags: {tag_line}",
        "markdown: true",
        "",
        "# Note",
        "",
    ]
    mlow = model.lower()
    if mlow == "basic":
        lines += [
            "## Front",
            sanitize(fields.get("Front", "")),
            "",
            "## Back",
            sanitize(fields.get("Back", "")),
            "",
        ]
    elif mlow == "cloze":
        lines += [
            "## Text",
            sanitize(fields.get("Text", "")),
            "",
            "## Back Extra",
            sanitize(fields.get("Back Extra", "")) or sanitize(fields.get("Extra", "")),
            "",
        ]
    else:
        # Custom model -> output all fields as sections
        for k, v in fields.items():
            lines += [f"## {k}", sanitize(v), ""]
    return "\n".join(lines)


def write_temp(content: str, model: str, base_hint: str = "") -> Path:
    # temp file name hint helps when scanning /tmp
    hint = f"_{model.replace(' ', '_')}"
    if base_hint:
        hint += f"_{base_hint}"
    fd, path = tempfile.mkstemp(prefix=f"apy{hint}_", suffix=".md")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return Path(path)


def run_apy_add_from_file(apy_bin: str, path: Path, logger: logging.Logger) -> int:
    logger.info(f"[apy] {apy_bin} add-from-file {path}")
    proc = subprocess.run(
        [apy_bin, "add-from-file", str(path)],
        capture_output=True,
        text=True,
    )
    if proc.stdout.strip():
        logger.info(proc.stdout.rstrip())
    if proc.stderr.strip():
        logger.warning(proc.stderr.rstrip())
    return proc.returncode


def iter_markdown_files(root: Path) -> Iterable[Path]:
    """Yield *.md in root (file or directory). Skips hidden dirs and .obsidian."""
    if root.is_file() and root.suffix.lower() == ".md":
        yield root
        return
    # Directory mode
    skip_dirs = {".git", ".obsidian", ".trash", ".venv", "node_modules"}
    for p in root.rglob("*.md"):
        parts = set(p.parts)
        if parts & skip_dirs:
            continue
        if any(part.startswith(".") for part in p.parts[:-1]):  # skip hidden dirs
            continue
        yield p


def get_declared_template_version(meta: dict[str, Any]) -> int | None:
    v = meta.get("anki_template_version")
    if v is None:
        return None
    try:
        return int(str(v).strip().strip('"').strip("'"))
    except Exception:
        return None


# ---- UUID helpers ----


def is_valid_uuid(s: str) -> bool:
    try:
        uuid.UUID(str(s))
        return True
    except Exception:
        return False


def get_card_uuid(card: dict[str, Any], logger: logging.Logger, md_path: Path, idx: int) -> str:
    """
    Ensure each card has a UUID in 'id'.
    - If 'id' exists and is a valid UUID, use it.
    - Otherwise generate a new uuid4 hex and use that.
    """
    raw = sanitize(card.get("id", "")).strip()
    if raw and is_valid_uuid(raw):
        return raw
    new_id = uuid.uuid4().hex  # 32 hex chars
    if raw and not is_valid_uuid(raw):
        logger.info(f"[fix] {md_path} card#{idx}: replacing non-UUID id '{raw}' with '{new_id}'")
    else:
        logger.info(f"[gen] {md_path} card#{idx}: generated id '{new_id}'")
    # Note: we don't write back to file; 'card' is transient here.
    return new_id


# ---------- Core ----------


def process_markdown_file(
    md_path: Path,
    apy_bin: str,
    do_run: bool,
    keep_going: bool,
    logger: logging.Logger,
    seen_ids: set,  # track UUIDs across the run
) -> tuple[int, int, int, int]:
    """
    Returns (generated_files, imported_ok, skipped, errors)
    """
    generated = imported = skipped = errors = 0
    try:
        text = md_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"[skip] {md_path}: cannot read file ({e})")
        return (0, 0, 1, 0)

    meta, _ = parse_frontmatter(text)
    if not meta:
        logger.info(f"[skip] {md_path}: no YAML frontmatter found")
        return (0, 0, 1, 0)

    if "__yaml_error__" in meta:
        logger.warning(f"[skip] {md_path}: YAML parse error: {meta['__yaml_error__']}")
        return (0, 0, 1, 0)

    # ---- STRICT TEMPLATE VERSION CHECK ----
    declared_version = get_declared_template_version(meta)
    if declared_version is None:
        logger.info(f"[skip] {md_path}: missing required key 'anki_template_version'")
        return (0, 0, 1, 0)
    if declared_version != CURRENT_TEMPLATE_VERSION:
        logger.info(
            f"[skip] {md_path}: unsupported anki_template_version={declared_version} "
            f"(required: {CURRENT_TEMPLATE_VERSION})"
        )
        return (0, 0, 1, 0)
    # ---------------------------------------

    deck = meta.get("deck")
    if not deck:
        logger.info(f"[skip] {md_path}: missing required key 'deck'")
        return (0, 0, 1, 0)

    default_model = sanitize(meta.get("model", "Basic"))
    base_tags = [t.strip() for t in to_list(meta.get("tags", [])) if t and t.strip()]
    cards = meta.get("cards", [])
    if not isinstance(cards, list) or not cards:
        logger.info(f"[skip] {md_path}: no 'cards:' list to process")
        return (0, 0, 1, 0)

    logger.info(
        f"[scan] {md_path}: deck='{deck}', "
        f"default_model='{default_model}', "
        f"tags={base_tags or '[]'}, "
        f"cards={len(cards)}"
    )

    for idx, card in enumerate(cards, start=1):
        try:
            # --- ensure a UUID id and add src:<uuid> tag ---
            cid = get_card_uuid(card, logger, md_path, idx)
            if cid in seen_ids:
                logger.warning(
                    f"[skip] {md_path} card#{idx}: duplicate UUID id '{cid}' in this run"
                )
                skipped += 1
                continue
            seen_ids.add(cid)

            card_tags = list(base_tags)
            card_tags.append(f"src:{cid}")

            model = sanitize(card.get("model", default_model))
            mlow = model.lower()
            if mlow == "basic":
                fields = {
                    "Front": sanitize(card.get("Front", "")),
                    "Back": sanitize(card.get("Back", "")),
                }
                if not fields["Front"] or not fields["Back"]:
                    logger.info(f"[skip] {md_path} card#{idx}: Basic requires Front & Back")
                    skipped += 1
                    continue
            elif mlow == "cloze":
                fields = {
                    "Text": sanitize(card.get("Text", "")),
                    "Back Extra": sanitize(card.get("Back Extra", ""))
                    or sanitize(card.get("Extra", "")),
                }
                if not fields["Text"]:
                    logger.info(f"[skip] {md_path} card#{idx}: Cloze requires Text")
                    skipped += 1
                    continue
            else:
                # custom model: include all non-meta keys
                fields = {k: v for k, v in card.items() if k not in {"id", "model"}}
                if not fields:
                    logger.info(
                        f"[skip] {md_path} card#{idx}: custom model '{model}' has no fields"
                    )
                    skipped += 1
                    continue

            content = make_editor_note(model, deck, card_tags, fields)
            base_hint = f"{md_path.stem}_c{idx}"
            tmp_path = write_temp(content, model=model, base_hint=base_hint)
            generated += 1
            logger.info(f"[gen]  {md_path} card#{idx}: wrote {tmp_path}")

            if do_run:
                rc = run_apy_add_from_file(apy_bin, tmp_path, logger)
                if rc == 0:
                    imported += 1
                else:
                    errors += 1
                    logger.error(f"[error] apy add-from-file failed (rc={rc}) for {tmp_path}")
                    if not keep_going:
                        return (generated, imported, skipped, errors)

        except Exception as e:
            errors += 1
            logger.error(f"[error] {md_path} card#{idx}: {e}")
            if not keep_going:
                return (generated, imported, skipped, errors)

    return (generated, imported, skipped, errors)


# ---------- CLI ----------


def main():
    ap = argparse.ArgumentParser(
        description=(
            "Scan Obsidian vault or file, generate apy editor-style notes, "
            "and (optionally) import via apy."
        )
    )
    ap.add_argument("path", help="Path to an Obsidian vault directory or a single Markdown file")
    ap.add_argument(
        "--run",
        action="store_true",
        help="Call `apy add-from-file` for each generated temp file",
    )
    ap.add_argument(
        "--keep-going",
        action="store_true",
        help="Continue on errors instead of stopping",
    )
    ap.add_argument(
        "--apy-bin",
        default="apy",
        help="Path/name of the apy executable (default: apy)",
    )
    ap.add_argument("--log-dir", default="./logs", help="Directory for run logs (default: ./logs)")
    args = ap.parse_args()

    logger, log_path, run_id = setup_logging(Path(args.log_dir))
    logger.info(f"=== obsidian → apy run_id={run_id} ===")
    logger.info(
        f"path={args.path}  run={args.run}  keep_going={args.keep_going}  apy_bin={args.apy_bin}"
    )
    logger.info(f"log file: {log_path}")

    root = Path(args.path)
    if not root.exists():
        logger.error(f"Path not found: {root}")
        sys.exit(2)

    total_generated = total_imported = total_skipped = total_errors = 0
    files_processed = 0
    seen_ids: set = set()  # ensure UUID uniqueness across the whole run

    for md_file in iter_markdown_files(root):
        files_processed += 1
        g, i, s, e = process_markdown_file(
            md_file, args.apy_bin, args.run, args.keep_going, logger, seen_ids
        )
        total_generated += g
        total_imported += i
        total_skipped += s
        total_errors += e

    if files_processed == 0:
        logger.info("No markdown files found to process.")

    logger.info(
        f"=== summary run_id={run_id} === files={files_processed}  "
        f"generated={total_generated}  imported={total_imported}  "
        f"skipped={total_skipped}  errors={total_errors}"
    )

    if total_errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
