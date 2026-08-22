"""Setting-bible commands: create, update, and show the series bible."""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from fabricatio_core import TEMPLATE_MANAGER, Role
from fabricatio_core.rust import PLAN

from fabricatio_novel.capabilities.bible import BibleCompose
from fabricatio_novel.cli import app
from fabricatio_novel.commands._helpers import _resolve_outline
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.series_book import SeriesBible


def _load_bible(path: Path) -> SeriesBible:
    """Load a SeriesBible from its JSON file."""
    if not path.is_file():
        typer.secho(f"❌ Bible file '{path}' does not exist.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    return SeriesBible.model_validate_json(path.read_text(encoding="utf-8"))


def _render_bible_md(bible: SeriesBible) -> str:
    """Render the bible as a human-readable markdown document."""
    return TEMPLATE_MANAGER.render_template(novel_config.setting_bible_export_template, bible.model_dump())


def _save_bible(bible: SeriesBible, out: Path) -> None:
    """Write the bible JSON, a BLAKE3-hashed checkpoint, and the markdown export."""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(bible.model_dump_json(indent=1, by_alias=True), encoding="utf-8")
    bible.persist(out.parent)
    md_path = out.with_name(f"{out.stem}.md")
    md_path.write_text(_render_bible_md(bible), encoding="utf-8")
    typer.secho(
        f"✅ Setting bible saved:\n   JSON:       {out}\n   Markdown:   {md_path}\n   Checkpoint: {out.parent}",
        fg=typer.colors.GREEN,
        bold=True,
    )


@app.command(name="create")
def create_bible(
    outline: Optional[str] = typer.Argument(None, help="Novel outline text."),
    outline_file: Optional[Path] = typer.Option(
        None, "--outline-file", "-of", help="Read the outline from a file instead of the positional argument."
    ),
    language: Optional[str] = typer.Option(
        None, "--language", "--lang", "-l", help="Bible language. Auto-detected from the outline when omitted."
    ),
    sections: str = typer.Option(
        "", "--sections", "-s", help="Comma-separated sections to create: characters, background (default: all)."
    ),
    out: Path = typer.Option(
        Path("settings/bible.json"), "--out", "-o", help="Output bible JSON path (default: settings/bible.json)."
    ),
    send_to: str = typer.Option(PLAN, "--send-to", "-st", help="Routing group for LLM calls."),
) -> None:
    """Create a setting bible from an outline."""
    from fabricatio_novel.capabilities.bible import parse_sections

    class BibleRole(Role, BibleCompose):
        """Role for creating and updating setting bibles."""

    try:
        names = parse_sections(sections)
    except ValueError as e:
        typer.secho(f"❌ {e}", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1) from None
    role = BibleRole(name="bible_creator")
    bible = asyncio.run(role.create_setting_bible(_resolve_outline(outline, outline_file), language, send_to, names))
    if bible is None:
        typer.secho("❌ Failed to create setting bible.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    _save_bible(bible, out)


@app.command(name="update")
def update_bible(
    bible_path: Path = typer.Argument(..., help="Path to the bible JSON to update."),
    outline: Optional[str] = typer.Argument(None, help="Novel outline text."),
    outline_file: Optional[Path] = typer.Option(
        None, "--outline-file", "-of", help="Read the outline from a file instead of the positional argument."
    ),
    language: Optional[str] = typer.Option(
        None, "--language", "--lang", "-l", help="Bible language. Auto-detected from the outline when omitted."
    ),
    sections: str = typer.Option(
        "", "--sections", "-s", help="Comma-separated sections to re-propose: characters, background (default: all)."
    ),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Output bible JSON path (default: update in place)."),
    send_to: str = typer.Option(PLAN, "--send-to", "-st", help="Routing group for LLM calls."),
) -> None:
    """Re-propose sections of an existing setting bible from the outline."""
    from fabricatio_novel.capabilities.bible import parse_sections

    class BibleRole(Role, BibleCompose):
        """Role for creating and updating setting bibles."""

    bible = _load_bible(bible_path)
    try:
        names = parse_sections(sections)
    except ValueError as e:
        typer.secho(f"❌ {e}", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1) from None
    role = BibleRole(name="bible_updater")
    updated = asyncio.run(
        role.update_setting_bible(bible, _resolve_outline(outline, outline_file), language, send_to, names)
    )
    if updated is None:
        typer.secho("❌ Failed to update setting bible.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    _save_bible(updated, out or bible_path)


@app.command(name="show")
def show_bible(
    bible_path: Path = typer.Argument(..., help="Path to the bible JSON to display."),
) -> None:
    """Print the setting bible as rendered markdown."""
    typer.echo(_render_bible_md(_load_bible(bible_path)))
