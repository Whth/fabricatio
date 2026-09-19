"""Shared helpers for the Fabricatio Novel CLI command modules."""

from pathlib import Path

import typer


def _split_skills(names: list[str]) -> list[str]:
    """Split the ``--skill`` specs into a de-duplicated, order-preserving name list.

    Names may be repeated across options and comma-separated; the skill library
    resolves them when the run starts and logs any name that resolves nowhere, so
    this only normalizes what the user typed.
    """
    return list(dict.fromkeys(name.strip() for spec in names for name in spec.split(",") if name.strip()))


def _resolve_outline(outline: str | None, outline_file: Path | None) -> str:
    """Resolve the outline from a positional argument or ``--outline-file``, exiting on failure."""
    if outline_file is not None:
        text = outline_file.read_text(encoding="utf-8").strip()
        if not text:
            typer.secho(f"❌ Outline file '{outline_file}' is empty.", fg=typer.colors.RED, bold=True)
            raise typer.Exit(1)
        return text
    if outline:
        return outline
    typer.secho(
        "❌ Provide the outline as a positional argument or via --outline-file.",
        fg=typer.colors.RED,
        bold=True,
    )
    raise typer.Exit(1)
