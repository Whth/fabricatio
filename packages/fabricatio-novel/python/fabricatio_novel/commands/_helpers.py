"""Shared helpers for the Fabricatio Novel CLI command modules."""

from pathlib import Path
from typing import Optional

import typer


def _resolve_outline(outline: Optional[str], outline_file: Optional[Path]) -> str:
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
        "❌ Provide the outline as a positional argument or via --outline-file.", fg=typer.colors.RED, bold=True
    )
    raise typer.Exit(1)
