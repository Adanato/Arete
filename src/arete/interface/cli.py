import json
import logging
import os
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from arete.application.config import resolve_config

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


def version_callback(value: bool):
    if value:
        import importlib.metadata

        try:
            version = importlib.metadata.version("arete")
            typer.echo(f"arete {version}")
        except importlib.metadata.PackageNotFoundError:
            typer.echo("arete (version unknown)")
        raise typer.Exit()


@app.callback()
def main_callback(
    ctx: typer.Context,
    verbose: Annotated[
        int,
        typer.Option(
            "--verbose", "-v", count=True, help="Increase verbosity. Repeat for more detail."
        ),
    ] = 1,
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            callback=version_callback,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = None,
):
    """
    Global settings for arete.
    """
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
    """
    [bold green]Sync[/bold green] your Obsidian notes to Anki.
    """
    # Clean up None values so Pydantic defaults/config take over
    overrides = {
        "root_input": path,
        "backend": backend,
        "prune": prune,
        "force": force,
        "clear_cache": clear_cache,
        "dry_run": dry_run,
        "anki_connect_url": anki_connect_url,
        "anki_media_dir": anki_media_dir,
        "workers": workers,
    }
    overrides = {k: v for k, v in overrides.items() if v is not None}

    # Merge global verbosity
    overrides["verbose"] = ctx.obj.get("verbose_bonus", 1)

    config = resolve_config(overrides)

    import asyncio

    from arete.main import run_sync_logic

    asyncio.run(run_sync_logic(config))


@app.command()
def init():
    """
    Launch the interactive setup wizard.
    """
    from arete.application.wizard import run_init_wizard

    run_init_wizard()
    raise typer.Exit()


@config_app.command("show")
def config_show():
    """
    Display final resolved configuration.
    """

    config = resolve_config()
    # Path to str for JSON
    d = {k: str(v) if isinstance(v, Path) else v for k, v in config.model_dump().items()}
    typer.echo(json.dumps(d, indent=2))


@config_app.command("open")
def config_open():
    """
    Open the config file in your default editor.
    """
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
    """
    Start the persistent background server (Daemon).
    """
    import uvicorn

    typer.secho(f"🚀 Starting Arete Server on http://{host}:{port}", fg="green")
    uvicorn.run("arete.server:app", host=host, port=port, reload=reload)


@app.command()
def logs():
    """
    Open the log directory.
    """
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
    """Translates technical PyYAML errors into user-friendly advice."""
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


@app.command("check-file")
def check_file(
    path: Annotated[Path, typer.Argument(help="Path to the markdown file to check.")],
    json_output: Annotated[bool, typer.Option("--json", help="Output results as JSON.")] = False,
):
    """
    Validate a single file for arete compatibility.
    Checks YAML syntax and required fields.
    """

    from yaml import YAMLError

    from arete.application.utils.text import validate_frontmatter

    # Type hint the result dictionary
    result: dict[str, Any] = {
        "ok": True,
        "errors": [],
        "stats": {
            "deck": None,
            "model": None,
            "cards_found": 0,
        },
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
        # problem_mark.line is now 0-indexed relative to FILE (thanks to text.py fix)
        # So we just add 1 to get 1-based line number.
        line = e.problem_mark.line + 1 if hasattr(e, "problem_mark") else 1  # type: ignore
        col = e.problem_mark.column + 1 if hasattr(e, "problem_mark") else 1  # type: ignore

        # Original technical message
        tech_msg = f"{e.problem}"  # type: ignore
        if hasattr(e, "context") and e.context:
            tech_msg += f" ({e.context})"

        friendly_msg = humanize_error(tech_msg)

        result["errors"].append(
            {"line": line, "column": col, "message": friendly_msg, "technical": tech_msg}
        )
    except Exception as e:
        result["ok"] = False
        result["errors"].append({"line": 1, "message": str(e)})
    else:
        # Schema Validation
        is_explicit_arete = meta.get("arete") is True

        # 1. Check anki_template_version OR explicit flag
        if "anki_template_version" not in meta and "cards" not in meta and not is_explicit_arete:
            # It might be valid markdown but NOT an arete note.
            # Check for typos
            if "card" in meta and isinstance(meta["card"], list):
                result["ok"] = False
                result["errors"].append(
                    {
                        "line": 1,
                        "message": "Found 'card' list but expected 'cards'. Possible typo?",
                    }
                )
            pass
        elif is_explicit_arete and "cards" not in meta:
            # Strict Mode: Explicitly marked but missing cards
            result["ok"] = False
            result["errors"].append(
                {
                    "line": 1,
                    "message": "File marked 'arete: true' but missing 'cards' list.",
                }
            )
            # Check for typos
            if "card" in meta:
                result["errors"].append(
                    {
                        "line": 1,
                        "message": "Found 'card' property. Did you mean 'cards'?",
                    }
                )

        # 2. Check cards presence if Deck/Model are there
        if "deck" in meta or "model" in meta or is_explicit_arete:
            if "deck" not in meta and is_explicit_arete:
                result["ok"] = False
                result["errors"].append(
                    {
                        "line": 1,
                        "message": "File marked 'arete: true' but missing 'deck' field.",
                    }
                )

            if "cards" not in meta:
                result["ok"] = False
                result["errors"].append(
                    {
                        "line": 1,
                        "message": "Missing 'cards' list. You defined a deck/model "
                        "but provided no cards.",
                    }
                )

        # 3. Type Check: 'cards' must be a list
        if "cards" in meta:
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
            else:
                cards = meta["cards"]
                result["stats"]["cards_found"] = len(cards)

                if not cards and is_explicit_arete:
                    result["ok"] = False
                    result["errors"].append(
                        {
                            "line": 1,
                            "message": "File marked 'arete: true' but 'cards' list is empty.",
                        }
                    )

                if meta:
                    # Stats collection
                    result["stats"]["deck"] = meta.get("deck")
                    result["stats"]["model"] = meta.get("model")
                    cards = meta.get("cards", [])
                    result["stats"]["cards_found"] = len(cards)

                    # --- Structural Heuristics ---
                    if isinstance(cards, list) and len(cards) > 1:
                        for i in range(len(cards) - 1):
                            curr = cards[i]
                            nxt = cards[i + 1]
                            if not isinstance(curr, dict) or not isinstance(nxt, dict):
                                continue

                            # 1. Detect "Split Cards" (Front and Back in separate items)
                            has_front = any(k in curr for k in ("Front", "front", "Text", "text"))
                            has_back = any(k in curr for k in ("Back", "back", "Extra", "extra"))
                            next_has_front = any(
                                k in nxt for k in ("Front", "front", "Text", "text")
                            )
                            next_has_back = any(
                                k in nxt for k in ("Back", "back", "Extra", "extra")
                            )

                            if has_front and not has_back and next_has_back and not next_has_front:
                                result["ok"] = False
                                line = curr.get("__line__", 0)
                                result["errors"].append(
                                    {
                                        "line": line,
                                        "message": (
                                            f"Split Card Error (Item #{i + 1}): "
                                            "It looks like 'Front' and 'Back' "
                                            "are separated into two list items. "
                                            "Ensure they are under the same dash '-'."
                                        ),
                                    }
                                )

                    # Check for missing deck if notes are present
                    if meta.get("arete") is True or (isinstance(cards, list) and len(cards) > 0):
                        if not meta.get("deck"):
                            result["ok"] = False
                            result["errors"].append(
                                {
                                    "line": meta.get("__line__", 1),
                                    "message": (
                                        "Missing required field: 'deck'. "
                                        "Arete notes must specify a destination deck."
                                    ),
                                }
                            )

                # Check individual cards
                for i, card in enumerate(cards):
                    if not isinstance(card, dict):
                        # Calculate approximate line number?
                        # Hard to know exactly without parsing, but we can say "Item X"
                        result["ok"] = False
                        result["errors"].append(
                            {
                                "line": 1,
                                # note: e.problem_mark.line is not available for individual
                                # list items in the parsed structure, effectively limiting
                                # us to line 1 or a broad "somewhere in the list" pointer.
                                "message": (
                                    f"Card #{i + 1} is invalid. "
                                    f"Expected a dictionary (key: value), "
                                    f"but got {type(card).__name__}."
                                ),
                            }
                        )
                    elif not {k: v for k, v in card.items() if not k.startswith("__")}:
                        line = card.get("__line__", i + 1)
                        result["ok"] = False
                        result["errors"].append(
                            {"line": line, "message": f"Card #{i + 1} is empty."}
                        )
                    else:
                        # Heuristic: Check for common primary keys
                        # Most Anki notes need a 'Front', 'Text' (Cloze), 'Question', or 'Term'
                        line = card.get("__line__", i + 1)
                        keys = {k for k in card.keys() if not k.startswith("__")}
                        # We look for at least one "Primary" looking key.
                        # We also check if the user is using a custom model?
                        # If the user defines explicit fields in Card 1,
                        # maybe we expect them in Card 2?
                        # For now, let's strictly enforce that a card isn't JUST "Back" or "Extra".

                        primary_candidates = {
                            "Front",
                            "Text",
                            "Question",
                            "Term",
                            "Expression",
                            "front",
                            "text",
                            "question",
                            "term",
                        }
                        if not keys.intersection(primary_candidates):
                            # If we found NONE of the common primary keys, we flag it.
                            # But we should be careful.
                            # Let's check consistency:
                            # If Card #0 had "Front", and this one doesn't.
                            if i > 0 and isinstance(cards[0], dict):
                                card0_keys = set(cards[0].keys())
                                # If Card 0 has "Front", and we don't.
                                if "Front" in card0_keys and "Front" not in keys:
                                    result["ok"] = False
                                    result["errors"].append(
                                        {
                                            "line": line,
                                            "message": f"Card #{i + 1} is missing 'Front' field "
                                            "(present in first card).",
                                        }
                                    )
                                    continue
                                if "Text" in card0_keys and "Text" not in keys:
                                    result["ok"] = False
                                    result["errors"].append(
                                        {
                                            "line": line,
                                            "message": f"Card #{i + 1} is missing 'Text' field "
                                            "(present in first card).",
                                        }
                                    )
                                    continue

                            # Fallback generic warning if we can't do consistency check
                            if len(keys) == 1 and "Back" in keys:
                                result["ok"] = False
                                result["errors"].append(
                                    {
                                        "line": line,
                                        "message": f"Card #{i + 1} has only 'Back' field. "
                                        "Missing 'Front'?",
                                    }
                                )

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
    """
    Attempts to automatically fix common format errors in a file.
    """
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
    """
    Heuristic to merge cards that were accidentally split into two list items.
    Ensures that Front and Back are recombined into one card if possible.
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
    """
    Migrate legacy files and normalize YAML frontmatter.

    1. Upgrades 'anki_template_version: 1' to 'arete: true'.
    2. Normalizes YAML serialization to use consistent block scalars (|-).
    """
    import re

    from arete.application.utils.fs import iter_markdown_files
    from arete.application.utils.text import (
        apply_fixes,
        fix_mathjax_escapes,
        parse_frontmatter,
        rebuild_markdown_with_frontmatter,
    )

    # Upgrade patterns
    p1 = re.compile(r"^\s*[\"\']?anki_template_version[\"\']?:\s*1\s*$", re.MULTILINE)
    p2 = re.compile(r"^\s*[\"\']?anki_template_version[\"\']?:\s*['\"]1['\"]\s*$", re.MULTILINE)

    scanned = 0
    migrated = 0

    files = [path] if path.is_file() else iter_markdown_files(path)
    # Resolve config to get verbosity
    # Merge global (-v before command) and local (-v after command)
    bonus = ctx.obj.get("verbose_bonus", 0)
    final_verbose = max(verbose, bonus) if verbose or bonus else 1
    config = resolve_config({"verbose": final_verbose})

    for p in files:
        scanned += 1
        try:
            content = p.read_text(encoding="utf-8")
            original_content = content

            # 1. Pre-process: fix common YAML syntax errors & indentation
            content = apply_fixes(content)
            content = fix_mathjax_escapes(content)

            # 2. Upgrade Legacy Flags
            if "anki_template_version" in content:
                content = p1.sub("arete: true", content)
                content = p2.sub("arete: true", content)

            # 3. Normalize YAML (Round-trip)
            meta, body = parse_frontmatter(content)

            if meta:
                # Check for parsing errors
                if "__yaml_error__" in meta:
                    if config.verbose >= 2:
                        typer.secho(f"  [Parse Error] {p}: {meta['__yaml_error__']}", fg="yellow")
                    continue

                # Strict filter: Only migrate if it's an arete note
                # PyYAML handles true/True/TRUE as boolean True
                if meta.get("arete") is not True:
                    if config.verbose >= 3:
                        typer.echo(f"  [Skip] {p}: No 'arete: true' flag found.")
                    continue

                # AUTO-HEALING: Merge split cards
                if "cards" in meta and isinstance(meta["cards"], list):
                    meta["cards"] = _merge_split_cards(meta["cards"])

                if config.verbose >= 2:
                    typer.echo(f"  [Check] {p}: Normalizing YAML...")

                # AUTO-HEALING: Strip redundant blocks from body (--- blocks after frontmatter)
                # Re-match body in case apply_fixes changed things or there are trailing dashes
                while body.lstrip().startswith("---"):
                    stripped = body.lstrip()
                    _, next_body = parse_frontmatter(stripped)
                    if next_body == stripped:
                        # Could not parse as frontmatter block, maybe just a
                        # horizontal rule or single ---
                        # Consume one line to avoid infinite loop
                        lines = stripped.split("\n", 1)
                        body = lines[1] if len(lines) > 1 else ""
                    else:
                        body = next_body

                normalized = rebuild_markdown_with_frontmatter(meta, body)

                # Preserve original BOM if present
                if content.startswith("\ufeff"):
                    normalized = "\ufeff" + normalized
                content = normalized

            if content != original_content:
                migrated += 1
                if dry_run:
                    typer.echo(f"[DRY RUN] Would migrate/normalize: {p}")
                else:
                    p.write_text(content, encoding="utf-8")
                    typer.echo(f"Migrated: {p}")
            elif config.verbose >= 2 and meta.get("arete") is True:
                typer.echo(f"  [Equal] {p}: Already normalized.")
        except Exception as e:
            if config.verbose >= 1:
                typer.secho(f"Error reading {p}: {e}", fg="red")

    if dry_run:
        msg = f"\n[DRY RUN] Scanned {scanned} files. Found {migrated} to migrate."
        typer.secho(msg, fg="yellow")
    else:
        typer.secho(f"\nScanned {scanned} files. Migrated {migrated}.", fg="green")


@app.command("mcp-server")
def mcp_server():
    """
    Start MCP (Model Context Protocol) server for AI agent integration.

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
    """
    Fetch card statistics for the given Note IDs.
    """
    import asyncio
    import json
    from dataclasses import asdict

    from arete.application.config import resolve_config
    from arete.application.factory import get_anki_bridge

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

        overrides = {
            "verbose": verbose,
            "backend": backend,
            "anki_connect_url": anki_connect_url,
            "anki_base": anki_base,
        }
        config = resolve_config({k: v for k, v in overrides.items() if v is not None})
        anki = await get_anki_bridge(config)
        return await anki.get_card_stats(nids_list)

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


@anki_app.command("cards-suspend")
def suspend_cards(
    ctx: typer.Context,
    cids: Annotated[str, typer.Option(help="Comma-separated list of Card IDs (or JSON list).")],
    backend: Annotated[str | None, typer.Option(help="Force backend")] = None,
    anki_connect_url: Annotated[str | None, typer.Option(help="AnkiConnect URL Override")] = None,
    anki_base: Annotated[str | None, typer.Option(help="Anki Base Directory Override")] = None,
):
    """Suspend cards by CID."""
    import asyncio
    import json

    from arete.application.config import resolve_config
    from arete.application.factory import get_anki_bridge

    cids_list = []
    if cids.startswith("["):
        cids_list = json.loads(cids)
    else:
        cids_list = [int(n.strip()) for n in cids.split(",") if n.strip().isdigit()]

    async def run():
        overrides = {
            "backend": backend,
            "anki_connect_url": anki_connect_url,
            "anki_base": anki_base,
        }
        config = resolve_config({k: v for k, v in overrides.items() if v is not None})
        anki = await get_anki_bridge(config)
        success = await anki.suspend_cards(cids_list)
        print(json.dumps({"ok": success}))

    asyncio.run(run())


@anki_app.command("cards-unsuspend")
def unsuspend_cards(
    ctx: typer.Context,
    cids: Annotated[str, typer.Option(help="Comma-separated list of Card IDs.")],
    backend: Annotated[str | None, typer.Option(help="Force backend")] = None,
    anki_connect_url: Annotated[str | None, typer.Option(help="AnkiConnect URL Override")] = None,
    anki_base: Annotated[str | None, typer.Option(help="Anki Base Directory Override")] = None,
):
    """Unsuspend cards by CID."""
    import asyncio
    import json

    from arete.application.config import resolve_config
    from arete.application.factory import get_anki_bridge

    cids_list = []
    if cids.startswith("["):
        cids_list = json.loads(cids)
    else:
        cids_list = [int(n.strip()) for n in cids.split(",") if n.strip().isdigit()]

    async def run():
        overrides = {
            "backend": backend,
            "anki_connect_url": anki_connect_url,
            "anki_base": anki_base,
        }
        config = resolve_config({k: v for k, v in overrides.items() if v is not None})
        anki = await get_anki_bridge(config)
        success = await anki.unsuspend_cards(cids_list)
        print(json.dumps({"ok": success}))

    asyncio.run(run())


@anki_app.command("models-styling")
def model_styling(
    ctx: typer.Context,
    model: str = typer.Argument(..., help="Model Name"),
    backend: Annotated[str | None, typer.Option(help="Force backend")] = None,
    anki_connect_url: Annotated[str | None, typer.Option(help="AnkiConnect URL Override")] = None,
    anki_base: Annotated[str | None, typer.Option(help="Anki Base Directory Override")] = None,
):
    """Get CSS styling for a model."""
    import asyncio
    import json

    from arete.application.config import resolve_config
    from arete.application.factory import get_anki_bridge

    async def run():
        overrides = {
            "backend": backend,
            "anki_connect_url": anki_connect_url,
            "anki_base": anki_base,
        }
        config = resolve_config({k: v for k, v in overrides.items() if v is not None})
        anki = await get_anki_bridge(config)
        css = await anki.get_model_styling(model)
        print(json.dumps({"css": css}))

    asyncio.run(run())


@anki_app.command("models-templates")
def model_templates(
    ctx: typer.Context,
    model: str = typer.Argument(..., help="Model Name"),
    backend: Annotated[str | None, typer.Option(help="Force backend")] = None,
    anki_connect_url: Annotated[str | None, typer.Option(help="AnkiConnect URL Override")] = None,
    anki_base: Annotated[str | None, typer.Option(help="Anki Base Directory Override")] = None,
):
    """Get templates for a model."""
    import asyncio
    import json

    from arete.application.config import resolve_config
    from arete.application.factory import get_anki_bridge

    async def run():
        overrides = {
            "backend": backend,
            "anki_connect_url": anki_connect_url,
            "anki_base": anki_base,
        }
        config = resolve_config({k: v for k, v in overrides.items() if v is not None})
        anki = await get_anki_bridge(config)
        temps = await anki.get_model_templates(model)
        print(json.dumps(temps))

    asyncio.run(run())


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
    import asyncio
    import json

    from arete.application.config import resolve_config
    from arete.application.factory import get_anki_bridge

    if not query and not nid:
        typer.secho("Must specify --query or --nid", fg="red")
        raise typer.Exit(1)

    final_query = query or f"nid:{nid}"

    async def run():
        overrides = {
            "backend": backend,
            "anki_connect_url": anki_connect_url,
            "anki_base": anki_base,
        }
        config = resolve_config({k: v for k, v in overrides.items() if v is not None})
        anki = await get_anki_bridge(config)
        success = await anki.gui_browse(final_query)
        print(json.dumps({"ok": success}))

    asyncio.run(run())
