import json
import logging
import os
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from arete.application.config import AppConfig, resolve_config


def _resolve_with_overrides(**kwargs) -> AppConfig:
    """Build config from keyword overrides, filtering out None values."""
    return resolve_config({k: v for k, v in kwargs.items() if v is not None})


app = typer.Typer(
    help="arete: Pro-grade Obsidian to Anki sync tool.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

config_app = typer.Typer(help="Manage arete configuration.")
app.add_typer(config_app, name="config")

# Configure logging to stderr so stdout remains clean for command results
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(name)s:%(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

anki_app = typer.Typer(help="Direct Anki interactions.")
app.add_typer(anki_app, name="anki")


@app.callback()
def main_callback(
    ctx: typer.Context,
    verbose: Annotated[
        int,
        typer.Option(
            "--verbose", "-v", count=True, help="Increase verbosity. Repeat for more detail."
        ),
    ] = 1,
):
    """Global settings for arete."""
    ctx.ensure_object(dict)
    ctx.obj["verbose_bonus"] = verbose


@app.command()
def sync(
    ctx: typer.Context,
    path: Annotated[
        Path | None,
        typer.Argument(
            help=(
                "Path to Obsidian vault or Markdown file. "
                "Defaults to 'vault_root' in config, or CWD."
            )
        ),
    ] = None,
    backend: Annotated[
        str | None, typer.Option(help="Anki backend: auto, ankiconnect, direct.")
    ] = None,
    prune: Annotated[
        bool, typer.Option("--prune/--no-prune", help="Prune orphaned cards from Anki.")
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Bypass confirmation for destructive actions.")
    ] = False,
    clear_cache: Annotated[
        bool, typer.Option("--clear-cache", help="Force re-sync of all files.")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Verify changes without applying.")
    ] = False,
    anki_connect_url: Annotated[
        str | None, typer.Option(help="Custom AnkiConnect endpoint.")
    ] = None,
    anki_media_dir: Annotated[
        Path | None, typer.Option(help="Custom Anki media directory.")
    ] = None,
    workers: Annotated[int | None, typer.Option(help="Parallel sync workers.")] = None,
):
    """[bold green]Sync[/bold green] your Obsidian notes to Anki."""
    config = _resolve_with_overrides(
        root_input=path,
        backend=backend,
        prune=prune,
        force=force,
        clear_cache=clear_cache,
        dry_run=dry_run,
        anki_connect_url=anki_connect_url,
        anki_media_dir=anki_media_dir,
        workers=workers,
        verbose=ctx.obj.get("verbose_bonus", 1),
    )

    import asyncio

    from arete.main import run_sync_logic

    asyncio.run(run_sync_logic(config))


@app.command()
def init():
    """Launch the interactive setup wizard."""
    from arete.application.wizard import run_init_wizard

    run_init_wizard()
    raise typer.Exit()


@config_app.command("show")
def config_show():
    """Display final resolved configuration."""
    config = resolve_config()
    # Path to str for JSON
    d = {k: str(v) if isinstance(v, Path) else v for k, v in config.model_dump().items()}
    typer.echo(json.dumps(d, indent=2))


@config_app.command("open")
def config_open():
    """Open the config file in your default editor."""
    import subprocess

    cfg_path = Path.home() / ".config/arete/config.toml"
    if not cfg_path.exists():
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.touch()

    if sys.platform == "darwin":
        subprocess.run(["open", str(cfg_path)])
    elif sys.platform == "win32":
        os.startfile(str(cfg_path))
    else:
        subprocess.run(["xdg-open", str(cfg_path)])


@app.command("server")
def server(
    port: Annotated[int, typer.Option(help="Port to bind the server to.")] = 8777,
    host: Annotated[str, typer.Option(help="Host to bind the server to.")] = "127.0.0.1",
    reload: Annotated[bool, typer.Option(help="Enable auto-reload.")] = False,
):
    """Start the persistent background server (Daemon)."""
    import uvicorn

    typer.secho(f"🚀 Starting Arete Server on http://{host}:{port}", fg="green")
    uvicorn.run("arete.server:app", host=host, port=port, reload=reload)


@app.command()
def logs():
    """Open the log directory."""
    import subprocess

    config = resolve_config()
    if not config.log_dir.exists():
        config.log_dir.mkdir(parents=True, exist_ok=True)

    if sys.platform == "darwin":
        subprocess.run(["open", str(config.log_dir)])
    elif sys.platform == "win32":
        import os

        os.startfile(str(config.log_dir))
    else:
        subprocess.run(["xdg-open", str(config.log_dir)])


def humanize_error(msg: str) -> str:
    """Translate technical PyYAML errors into user-friendly advice."""
    if "mapping values are not allowed here" in msg:
        return (
            "Indentation Error: You likely have a nested key (like 'bad_indent') "
            "at the wrong level. Check your spaces."
        )
    if "found character '\\t' that cannot start any token" in msg:
        return "Tab Character Error: YAML does not allow tabs. Please use spaces only."
    if "did not find expected key" in msg:
        return "Syntax Error: You might be missing a key name or colon."
    if "found duplicate key" in msg:
        return f"Duplicate Key Error: {msg}"
    if "scanner error" in msg:
        return f"Syntax Error: {msg}"
    if "expected <block end>, but found '?'" in msg:
        return (
            "Indentation Error: A key (like 'nid:' or 'cid:') is likely aligned "
            "with the card's dash '-'. It must be indented further to belong to that card."
        )
    return msg


def _check_arete_flags(meta: dict, result: dict[str, Any]) -> None:
    """Validate arete flag, cards presence, and deck/model requirements."""
    is_explicit_arete = meta.get("arete") is True

    if "anki_template_version" not in meta and "cards" not in meta and not is_explicit_arete:
        if "card" in meta and isinstance(meta["card"], list):
            result["ok"] = False
            result["errors"].append(
                {"line": 1, "message": "Found 'card' list but expected 'cards'. Possible typo?"}
            )
    elif is_explicit_arete and "cards" not in meta:
        result["ok"] = False
        result["errors"].append(
            {"line": 1, "message": "File marked 'arete: true' but missing 'cards' list."}
        )
        if "card" in meta:
            result["errors"].append(
                {"line": 1, "message": "Found 'card' property. Did you mean 'cards'?"}
            )

    if "deck" in meta or "model" in meta or is_explicit_arete:
        if "deck" not in meta and is_explicit_arete:
            result["ok"] = False
            result["errors"].append(
                {"line": 1, "message": "File marked 'arete: true' but missing 'deck' field."}
            )
        if "cards" not in meta:
            result["ok"] = False
            result["errors"].append(
                {
                    "line": 1,
                    "message": "Missing 'cards' list. "
                    "You defined a deck/model but provided no cards.",
                }
            )


def _check_split_cards(cards: list, result: dict[str, Any]) -> None:
    """Detect cards accidentally split into separate Front/Back list items."""
    _FRONT_KEYS = ("Front", "front", "Text", "text")
    _BACK_KEYS = ("Back", "back", "Extra", "extra")

    for i in range(len(cards) - 1):
        curr, nxt = cards[i], cards[i + 1]
        if not isinstance(curr, dict) or not isinstance(nxt, dict):
            continue

        has_front = any(k in curr for k in _FRONT_KEYS)
        has_back = any(k in curr for k in _BACK_KEYS)
        next_has_front = any(k in nxt for k in _FRONT_KEYS)
        next_has_back = any(k in nxt for k in _BACK_KEYS)

        if has_front and not has_back and next_has_back and not next_has_front:
            result["ok"] = False
            result["errors"].append(
                {
                    "line": curr.get("__line__", 0),
                    "message": (
                        f"Split Card Error (Item #{i + 1}): "
                        "It looks like 'Front' and 'Back' are separated into two list items. "
                        "Ensure they are under the same dash '-'."
                    ),
                }
            )


_PRIMARY_FIELD_NAMES = {
    "Front", "Text", "Question", "Term", "Expression",
    "front", "text", "question", "term",
}


def _check_single_card(card: Any, i: int, cards: list, result: dict[str, Any]) -> None:
    """Validate a single card entry within the cards list."""
    if not isinstance(card, dict):
        result["ok"] = False
        result["errors"].append(
            {
                "line": 1,
                "message": (
                    f"Card #{i + 1} is invalid. Expected a dictionary (key: value), "
                    f"but got {type(card).__name__}."
                ),
            }
        )
        return

    if not {k: v for k, v in card.items() if not k.startswith("__")}:
        result["ok"] = False
        result["errors"].append(
            {"line": card.get("__line__", i + 1), "message": f"Card #{i + 1} is empty."}
        )
        return

    line = card.get("__line__", i + 1)
    keys = {k for k in card.keys() if not k.startswith("__")}
    if keys.intersection(_PRIMARY_FIELD_NAMES):
        return

    # Consistency check against first card
    if i > 0 and isinstance(cards[0], dict):
        card0_keys = set(cards[0].keys())
        if "Front" in card0_keys and "Front" not in keys:
            result["ok"] = False
            result["errors"].append(
                {
                    "line": line,
                    "message": f"Card #{i + 1} is missing 'Front' field (present in first card).",
                }
            )
            return
        if "Text" in card0_keys and "Text" not in keys:
            result["ok"] = False
            result["errors"].append(
                {
                    "line": line,
                    "message": f"Card #{i + 1} is missing 'Text' field (present in first card).",
                }
            )
            return

    if len(keys) == 1 and "Back" in keys:
        result["ok"] = False
        result["errors"].append(
            {"line": line, "message": f"Card #{i + 1} has only 'Back' field. Missing 'Front'?"}
        )


def _validate_cards_list(meta: dict, result: dict[str, Any]) -> None:
    """Validate the 'cards' field: type, structure, and individual cards."""
    is_explicit_arete = meta.get("arete") is True

    if "cards" not in meta:
        return

    if not isinstance(meta["cards"], list):
        result["ok"] = False
        result["errors"].append(
            {
                "line": 1,
                "message": (
                    f"Invalid format for 'cards'. Expected a list (starting with '-'), "
                    f"but got {type(meta['cards']).__name__}."
                ),
            }
        )
        return

    cards = meta["cards"]
    result["stats"]["cards_found"] = len(cards)

    if not cards and is_explicit_arete:
        result["ok"] = False
        result["errors"].append(
            {"line": 1, "message": "File marked 'arete: true' but 'cards' list is empty."}
        )

    # Stats collection
    result["stats"]["deck"] = meta.get("deck")
    result["stats"]["model"] = meta.get("model")

    if len(cards) > 1:
        _check_split_cards(cards, result)

    # Check for missing deck if notes are present
    if is_explicit_arete or len(cards) > 0:
        if not meta.get("deck"):
            result["ok"] = False
            result["errors"].append(
                {
                    "line": meta.get("__line__", 1),
                    "message": "Missing required field: 'deck'. "
                    "Arete notes must specify a destination deck.",
                }
            )

    for i, card in enumerate(cards):
        _check_single_card(card, i, cards, result)


@app.command("check-file")
def check_file(
    path: Annotated[Path, typer.Argument(help="Path to the markdown file to check.")],
    json_output: Annotated[bool, typer.Option("--json", help="Output results as JSON.")] = False,
):
    """Validate a single file for arete compatibility.

    Check YAML syntax and required fields.
    """
    from yaml import YAMLError

    from arete.application.utils.text import validate_frontmatter

    result: dict[str, Any] = {
        "ok": True,
        "errors": [],
        "stats": {"deck": None, "model": None, "cards_found": 0},
    }

    if not path.exists():
        result["ok"] = False
        result["errors"].append({"line": 0, "message": "File not found."})
        if json_output:
            typer.echo(json.dumps(result))
        else:
            typer.secho("File not found.", fg="red")
        raise typer.Exit(1)

    content = path.read_text(encoding="utf-8")

    try:
        meta = validate_frontmatter(content)
    except YAMLError as e_raw:
        e: Any = e_raw
        result["ok"] = False
        line = e.problem_mark.line + 1 if hasattr(e, "problem_mark") else 1  # type: ignore
        col = e.problem_mark.column + 1 if hasattr(e, "problem_mark") else 1  # type: ignore
        tech_msg = f"{e.problem}"  # type: ignore
        if hasattr(e, "context") and e.context:
            tech_msg += f" ({e.context})"
        result["errors"].append(
            {
                "line": line,
                "column": col,
                "message": humanize_error(tech_msg),
                "technical": tech_msg,
            }
        )
    except Exception as e:
        result["ok"] = False
        result["errors"].append({"line": 1, "message": str(e)})
    else:
        _check_arete_flags(meta, result)
        _validate_cards_list(meta, result)
        result["stats"]["deck"] = meta.get("deck")
        result["stats"]["model"] = meta.get("model")

    if json_output:
        typer.echo(json.dumps(result))
    else:
        if result["ok"]:
            typer.secho("✅ Valid arete file!", fg="green")
            typer.echo(f"  Deck: {result['stats']['deck']}")
            typer.echo(f"  Cards: {result['stats']['cards_found']}")
        else:
            typer.secho("❌ Validation Failed:", fg="red")
            for err in result["errors"]:
                loc = f"L{err.get('line', '?')}"
                typer.echo(f"  [{loc}] {err['message']}")
            raise typer.Exit(1)


@app.command("fix-file")
def fix_file(
    path: Annotated[Path, typer.Argument(help="Path to the markdown file to fix.")],
):
    """Attempt to automatically fix common format errors in a file."""
    from arete.application.utils.text import apply_fixes, validate_frontmatter

    if not path.exists():
        typer.secho("File not found.", fg="red")
        raise typer.Exit(1)

    content = path.read_text(encoding="utf-8")
    fixed_content = apply_fixes(content)

    if fixed_content == content:
        typer.secho("✅ No fixable issues found.", fg="green")
        valid_meta = bool(validate_frontmatter(content))
        if not valid_meta:
            typer.secho(
                "  (Note: File still has validation errors that cannot be auto-fixed)", fg="yellow"
            )
    else:
        path.write_text(fixed_content, encoding="utf-8")
        typer.secho("✨ File auto-fixed!", fg="green")
        typer.echo("  - Replaced tabs with spaces")
        typer.echo("  - Added missing cards list (if applicable)")


def _merge_split_cards(cards: list[Any]) -> list[Any]:
    """Merge cards that were accidentally split into two list items.

    Recombine Front and Back into one card if possible.
    """
    if not cards or len(cards) < 2:
        return cards

    new_cards = []
    i = 0
    while i < len(cards):
        curr = cards[i]

        # Look ahead for a potential split partner
        if i + 1 < len(cards):
            nxt = cards[i + 1]
            if isinstance(curr, dict) and isinstance(nxt, dict):
                has_front = any(k in curr for k in ("Front", "front", "Text", "text"))
                has_back = any(k in curr for k in ("Back", "back", "Extra", "extra"))
                next_has_front = any(k in nxt for k in ("Front", "front", "Text", "text"))
                next_has_back = any(k in nxt for k in ("Back", "back", "Extra", "extra"))

                # Case: Current has Front, next has Back (Standard split)
                if has_front and not has_back and next_has_back and not next_has_front:
                    # Merge them!
                    merged = {**curr, **nxt}
                    new_cards.append(merged)
                    i += 2
                    continue

        new_cards.append(curr)
        i += 1

    return new_cards


_CARD_KEY_ORDER = ["id", "model", "Front", "Back", "Text", "Extra", "deps", "anki"]
_ANKI_LEGACY_KEYS = ["nid", "cid", "note_id", "card_id"]


def _ensure_deps_block(card: dict) -> None:
    """Ensure card has a complete deps block with requires and related lists."""
    if "deps" not in card:
        card["deps"] = {"requires": [], "related": []}
    elif isinstance(card.get("deps"), dict):
        card["deps"].setdefault("requires", [])
        card["deps"].setdefault("related", [])


def _restructure_anki_fields(card: dict) -> None:
    """Move legacy nid/cid keys into a nested 'anki' block."""
    anki_block = card.get("anki", {})
    if not isinstance(anki_block, dict):
        anki_block = {}

    has_anki_data = bool(anki_block)
    for k in _ANKI_LEGACY_KEYS:
        if k in card:
            anki_block[k] = card.pop(k)
            has_anki_data = True
    if has_anki_data:
        card["anki"] = anki_block


def _order_card_keys(card: dict) -> None:
    """Reorder card keys to a consistent preferred order."""
    ordered: dict = {}
    for key in _CARD_KEY_ORDER:
        if key in card:
            ordered[key] = card.pop(key)
    for key in list(card.keys()):
        if not key.startswith("__"):
            ordered[key] = card.pop(key)
    for key in list(card.keys()):
        ordered[key] = card[key]
    card.clear()
    card.update(ordered)


def _enforce_card_v2_schema(card: dict) -> None:
    """Enforce V2 schema on a single card dict (deps, anki block, key order)."""
    _ensure_deps_block(card)
    _restructure_anki_fields(card)
    _order_card_keys(card)


def _strip_redundant_frontmatter(body: str, parse_frontmatter_fn: Any) -> str:
    """Strip redundant --- blocks that appear after the real frontmatter."""
    while body.lstrip().startswith("---"):
        stripped = body.lstrip()
        _, next_body = parse_frontmatter_fn(stripped)
        if next_body == stripped:
            lines = stripped.split("\n", 1)
            body = lines[1] if len(lines) > 1 else ""
        else:
            body = next_body
    return body


def _upgrade_to_arete(meta: dict) -> bool:
    """Upgrade legacy flags and return True if this is an arete note."""
    if "anki_template_version" in meta:
        val = meta.pop("anki_template_version")
        if str(val).strip() == "1":
            meta["arete"] = True
    return meta.get("arete") is True


def _heal_cards(meta: dict) -> None:
    """Merge split cards and enforce V2 schema on all card dicts."""
    if "cards" not in meta or not isinstance(meta["cards"], list):
        return
    meta["cards"] = _merge_split_cards(meta["cards"])
    for card in meta["cards"]:
        if isinstance(card, dict):
            _enforce_card_v2_schema(card)


def _migrate_single_file(
    p: Path, config: AppConfig, ensure_card_ids: Any, text_utils: dict
) -> str | None:
    """Migrate a single file, returning new content or None to skip."""
    content = p.read_text(encoding="utf-8")
    content = text_utils["apply_fixes"](content)
    content = text_utils["fix_mathjax_escapes"](content)

    parse_fm = text_utils["parse_frontmatter"]
    meta, body = parse_fm(content)

    if not meta:
        return content

    if "__yaml_error__" in meta:
        if config.verbose >= 2:
            typer.secho(f"  [Parse Error] {p}: {meta['__yaml_error__']}", fg="yellow")
        return None

    if not _upgrade_to_arete(meta):
        if config.verbose >= 3:
            typer.echo(f"  [Skip] {p}: No 'arete: true' flag found.")
        return None

    _heal_cards(meta)

    if config.verbose >= 2:
        typer.echo(f"  [Check] {p}: Normalizing YAML...")

    new_ids = ensure_card_ids(meta)
    if new_ids > 0 and config.verbose >= 1:
        typer.secho(f"  [ID] Assigned {new_ids} new Arete IDs in {p}", fg="cyan")

    body = _strip_redundant_frontmatter(body, parse_fm)
    normalized = text_utils["rebuild_markdown_with_frontmatter"](meta, body)

    if content.startswith("\ufeff"):
        normalized = "\ufeff" + normalized
    return normalized


@app.command("migrate")
def migrate(
    ctx: typer.Context,
    path: Annotated[Path, typer.Argument(help="Path to file or directory.")] = Path("."),
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview changes without saving.")
    ] = False,
    verbose: Annotated[
        int,
        typer.Option(
            "--verbose", "-v", count=True, help="Increase verbosity. Repeat for more detail."
        ),
    ] = 0,
):
    """Migrate legacy files and normalize YAML frontmatter.

    1. Upgrades 'anki_template_version: 1' to 'arete: true'.
    2. Normalizes YAML serialization to use consistent block scalars (|-).
    """
    from arete.application.id_service import assign_arete_ids, ensure_card_ids
    from arete.application.utils.fs import iter_markdown_files
    from arete.application.utils.text import (
        apply_fixes,
        fix_mathjax_escapes,
        parse_frontmatter,
        rebuild_markdown_with_frontmatter,
    )

    text_utils = {
        "apply_fixes": apply_fixes,
        "fix_mathjax_escapes": fix_mathjax_escapes,
        "parse_frontmatter": parse_frontmatter,
        "rebuild_markdown_with_frontmatter": rebuild_markdown_with_frontmatter,
    }

    scanned = 0
    migrated = 0

    files = [path] if path.is_file() else iter_markdown_files(path)
    bonus = ctx.obj.get("verbose_bonus", 0)
    final_verbose = max(verbose, bonus) if verbose or bonus else 1
    config = _resolve_with_overrides(verbose=final_verbose)

    for p in files:
        scanned += 1
        try:
            original_content = p.read_text(encoding="utf-8")
            content = _migrate_single_file(p, config, ensure_card_ids, text_utils)
            if content is None:
                continue

            if content != original_content:
                migrated += 1
                if dry_run:
                    typer.echo(f"[DRY RUN] Would migrate/normalize: {p}")
                else:
                    p.write_text(content, encoding="utf-8")
                    typer.echo(f"Migrated: {p}")
            elif config.verbose >= 2:
                typer.echo(f"  [Equal] {p}: Already normalized.")
        except Exception as e:
            if config.verbose >= 1:
                typer.secho(f"Error reading {p}: {e}", fg="red")

    if dry_run:
        msg = f"\n[DRY RUN] Scanned {scanned} files. Found {migrated} to migrate."
        typer.secho(msg, fg="yellow")
    else:
        typer.secho(f"\nScanned {scanned} files. Migrated {migrated}.", fg="green")

    typer.echo("\n--- ID Generation (Milestone 1) ---")
    ids_assigned = assign_arete_ids(path, dry_run=dry_run)
    if dry_run:
        typer.secho(f"[DRY RUN] Would assign {ids_assigned} new Arete IDs.", fg="yellow")
    else:
        typer.secho(f"Assigned {ids_assigned} new Arete IDs.", fg="green")


@app.command()
def format(
    ctx: typer.Context,
    path: Annotated[
        Path | None,
        typer.Argument(help="Path to vault or file. Defaults to config."),
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview changes without saving.")
    ] = False,
):
    """[bold blue]Format[/bold blue] YAML frontmatter in your vault.

    Normalize serialization to use stripped block scalars (|-).
    """
    from arete.application.factory import get_vault_service

    config = _resolve_with_overrides(
        root_input=path,
        dry_run=dry_run,
        verbose=ctx.obj.get("verbose_bonus", 1),
    )
    vault = get_vault_service(config)

    typer.echo(f"✨ Formatting vault: {config.vault_root}")
    count = vault.format_vault(dry_run=dry_run)

    if dry_run:
        typer.secho(f"\n[DRY RUN] Would have formatted {count} files.", fg="yellow")
    else:
        typer.secho(f"\n✅ Formatted {count} files.", fg="green")


@app.command("mcp-server")
def mcp_server():
    """Start MCP (Model Context Protocol) server for AI agent integration.

    This exposes Arete's sync capabilities to AI agents like Claude, Gemini, etc.
    Configure in Claude Desktop's config.json:

        {
          "mcpServers": {
            "arete": {
              "command": "arete",
              "args": ["mcp-server"]
            }
          }
        }
    """
    from arete.mcp_server import main as mcp_main

    typer.echo("Starting Arete MCP Server...")
    mcp_main()


@anki_app.command("stats")
def anki_stats(
    ctx: typer.Context,
    nids: Annotated[str, typer.Option(help="Comma-separated list of Note IDs (or JSON list).")],
    json_output: Annotated[
        bool, typer.Option("--json/--no-json", help="Output results as JSON.")
    ] = True,
    backend: Annotated[
        str | None, typer.Option(help="Force backend (auto|apy|ankiconnect)")
    ] = None,
    anki_connect_url: Annotated[str | None, typer.Option(help="AnkiConnect URL Override")] = None,
    anki_base: Annotated[str | None, typer.Option(help="Anki Base Directory Override")] = None,
):
    """Fetch card statistics for the given Note IDs."""
    import asyncio
    import json
    from dataclasses import asdict

    # Parse NIDs
    nids_list = []
    if nids.startswith("["):
        try:
            nids_list = json.loads(nids)
        except json.JSONDecodeError as e:
            typer.secho("Invalid JSON for --nids", fg="red")
            raise typer.Exit(1) from e
    else:
        nids_list = [int(n.strip()) for n in nids.split(",") if n.strip().isdigit()]

    if not nids_list:
        if json_output:
            typer.echo("[]")
        else:
            typer.echo("No valid NIDs provided.")
        return

    async def run():
        verbose = 1
        if ctx.parent and ctx.parent.obj:
            verbose = ctx.parent.obj.get("verbose_bonus", 1)

        config = _resolve_with_overrides(
            verbose=verbose,
            backend=backend,
            anki_connect_url=anki_connect_url,
            anki_base=anki_base,
        )

        from arete.application.factory import get_stats_repo
        from arete.application.stats.metrics_calculator import MetricsCalculator
        from arete.application.stats.service import FsrsStatsService

        repo = get_stats_repo(config)
        service = FsrsStatsService(repo=repo, calculator=MetricsCalculator())
        return await service.get_enriched_stats(nids_list)

    stats = asyncio.run(run())
    result = [asdict(s) for s in stats]

    if json_output:
        typer.echo(json.dumps(result, indent=2))
    else:
        import rich
        from rich.table import Table

        t = Table(title="Card Stats")
        t.add_column("CID")
        t.add_column("Deck")
        t.add_column("Diff")
        for s in result:
            diff_str = f"{int(s['difficulty'] * 100)}%" if s["difficulty"] is not None else "-"
            t.add_row(str(s["card_id"]), s["deck_name"], diff_str)
        rich.print(t)


def _parse_cids(cids: str) -> list[int]:
    """Parse comma-separated or JSON list of card IDs."""
    import json as _json

    if cids.startswith("["):
        return _json.loads(cids)
    return [int(n.strip()) for n in cids.split(",") if n.strip().isdigit()]


def _run_anki_bridge_action(
    action_fn, *, result_key: str | None = "ok", **config_kwargs
) -> None:
    """Run an async AnkiBridge action with standard config/bridge setup.

    If *result_key* is given, the output is ``{result_key: value}``; when
    ``None``, the raw value is printed as JSON.
    """
    import asyncio
    import json as _json

    from arete.application.factory import get_anki_bridge

    async def _run():
        config = _resolve_with_overrides(**config_kwargs)
        anki = await get_anki_bridge(config)
        result = await action_fn(anki)
        if result_key is not None:
            print(_json.dumps({result_key: result}))
        else:
            print(_json.dumps(result))

    asyncio.run(_run())


@anki_app.command("cards-suspend")
def suspend_cards(
    ctx: typer.Context,
    cids: Annotated[str, typer.Option(help="Comma-separated list of Card IDs (or JSON list).")],
    backend: Annotated[str | None, typer.Option(help="Force backend")] = None,
    anki_connect_url: Annotated[str | None, typer.Option(help="AnkiConnect URL Override")] = None,
    anki_base: Annotated[str | None, typer.Option(help="Anki Base Directory Override")] = None,
):
    """Suspend cards by CID."""
    cids_list = _parse_cids(cids)
    _run_anki_bridge_action(
        lambda anki: anki.suspend_cards(cids_list),
        backend=backend,
        anki_connect_url=anki_connect_url,
        anki_base=anki_base,
    )


@anki_app.command("cards-unsuspend")
def unsuspend_cards(
    ctx: typer.Context,
    cids: Annotated[str, typer.Option(help="Comma-separated list of Card IDs.")],
    backend: Annotated[str | None, typer.Option(help="Force backend")] = None,
    anki_connect_url: Annotated[str | None, typer.Option(help="AnkiConnect URL Override")] = None,
    anki_base: Annotated[str | None, typer.Option(help="Anki Base Directory Override")] = None,
):
    """Unsuspend cards by CID."""
    cids_list = _parse_cids(cids)
    _run_anki_bridge_action(
        lambda anki: anki.unsuspend_cards(cids_list),
        backend=backend,
        anki_connect_url=anki_connect_url,
        anki_base=anki_base,
    )


@anki_app.command("models-styling")
def model_styling(
    ctx: typer.Context,
    model: str = typer.Argument(..., help="Model Name"),
    backend: Annotated[str | None, typer.Option(help="Force backend")] = None,
    anki_connect_url: Annotated[str | None, typer.Option(help="AnkiConnect URL Override")] = None,
    anki_base: Annotated[str | None, typer.Option(help="Anki Base Directory Override")] = None,
):
    """Get CSS styling for a model."""
    _run_anki_bridge_action(
        lambda anki: anki.get_model_styling(model),
        result_key="css",
        backend=backend,
        anki_connect_url=anki_connect_url,
        anki_base=anki_base,
    )


@anki_app.command("models-templates")
def model_templates(
    ctx: typer.Context,
    model: str = typer.Argument(..., help="Model Name"),
    backend: Annotated[str | None, typer.Option(help="Force backend")] = None,
    anki_connect_url: Annotated[str | None, typer.Option(help="AnkiConnect URL Override")] = None,
    anki_base: Annotated[str | None, typer.Option(help="Anki Base Directory Override")] = None,
):
    """Get templates for a model."""
    _run_anki_bridge_action(
        lambda anki: anki.get_model_templates(model),
        result_key=None,
        backend=backend,
        anki_connect_url=anki_connect_url,
        anki_base=anki_base,
    )


@anki_app.command("browse")
def anki_browse(
    ctx: typer.Context,
    query: Annotated[str | None, typer.Option(help="Search query (e.g. 'nid:123')")] = None,
    nid: Annotated[int | None, typer.Option(help="Jump to Note ID")] = None,
    backend: Annotated[str | None, typer.Option(help="Force backend")] = None,
    anki_connect_url: Annotated[str | None, typer.Option(help="AnkiConnect URL Override")] = None,
    anki_base: Annotated[str | None, typer.Option(help="Anki Base Directory Override")] = None,
):
    """Open Anki browser."""
    if not query and not nid:
        typer.secho("Must specify --query or --nid", fg="red")
        raise typer.Exit(1)

    final_query = query or f"nid:{nid}"
    _run_anki_bridge_action(
        lambda anki: anki.gui_browse(final_query),
        backend=backend,
        anki_connect_url=anki_connect_url,
        anki_base=anki_base,
    )


@anki_app.command("queue")
def anki_queue(
    ctx: typer.Context,
    path: Annotated[
        Path | None, typer.Argument(help="Path to Obsidian vault. Defaults to config.")
    ] = None,
    depth: Annotated[int, typer.Option(help="Prerequisite search depth.")] = 2,
    include_related: Annotated[
        bool, typer.Option("--include-related", help="Boost related cards (experimental).")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show plan without creating decks.")
    ] = False,
):
    """Build dependency-aware study queues.

    Resolves prerequisites for due cards, filters weak ones,
    and creates filtered decks in Anki.
    """
    import asyncio

    config = _resolve_with_overrides(root_input=path)
    vault_root = config.root_input

    async def run():
        # Heuristic: Scan vault, find cards with NIDs, then check which are due in Anki.
        # This is Milestone 4's core integration.
        # For the prototype, we'll inform the user it's preparing the graph.

        try:
            # Re-using logic from queue_builder.py
            # Note: build_dependency_queue needs due_card_ids (Arete IDs)
            # We need a mapper Service to go from Anki due NIDs -> Arete IDs.

            typer.secho("Dependency queue building is initialized.", fg="blue")
            typer.echo(f"Vault: {vault_root}")
            typer.echo(f"Search Depth: {depth}")

            # Placeholder for full integration
            # result = build_dependency_queue(vault_root, due_card_ids=..., depth=depth)

            typer.secho(
                "\nThis feature requires AnkiBridge to support fetching due cards.", fg="yellow"
            )
            typer.echo("Refining queue resolution logic...")

        except NotImplementedError as e:
            typer.secho(f"Error: {e}", fg="red")
        except Exception as e:
            typer.secho(f"An unexpected error occurred: {e}", fg="red")

    asyncio.run(run())
