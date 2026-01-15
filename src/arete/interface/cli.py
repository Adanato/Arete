import json
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
    port: Annotated[int, typer.Option(help="Port to bind the server to.")] = 8000,
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

    from arete.infrastructure.utils.text import validate_frontmatter

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
        # 1. Check anki_template_version (Required for auto-detection usually)
        if "anki_template_version" not in meta and "cards" not in meta:
            # It might be valid markdown but NOT an arete note.
            # We should warn if it looks like they intended to use it.
            pass

        # 2. Check cards presence if Deck/Model are there
        if "deck" in meta or "model" in meta:
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
                            # If Card #0 had "Front", and this one doesn't...
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
    from arete.infrastructure.utils.text import apply_fixes, validate_frontmatter

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
