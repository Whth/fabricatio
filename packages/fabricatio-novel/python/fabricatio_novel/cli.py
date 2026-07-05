"""Fabricatio Novel CLI entry point.

This module wires up the shared ``app = typer.Typer(...)`` instance and the
default ``writer`` role, then imports every command submodule to register
its commands onto the app. Command implementations live in
:mod:`fabricatio_novel.commands`.

Module layout:

- :mod:`fabricatio_novel.commands.core`             — ``w``, ``wm``
- :mod:`fabricatio_novel.commands.rag`              — ``wr``, ``wrm``  (lancedb)
- :mod:`fabricatio_novel.commands.illustration`     — ``wi``, ``wmi``  (comfyui)
- :mod:`fabricatio_novel.commands.rag_illustration` — ``wri``, ``wrmi`` (comfyui + lancedb)
- :mod:`fabricatio_novel.commands.storage`          — ``store-refs``, ``enrich-refs`` (lancedb)
"""

from fabricatio_core import Event, Role
from fabricatio_core.utils import cfg

cfg(feats=["cli"])

import typer

from fabricatio_novel.workflows.novel import DebugNovelWorkflow

app = typer.Typer(help="A CLI tool to generate novels using AI-driven workflows.")

# Register the writer role and workflow
ns = "write"
writer_role = Role.with_bio(name="writer").subscribe(Event.quick_instantiate(ns), DebugNovelWorkflow).dispatch()


@app.command()
def info() -> None:
    """Show information about this CLI tool."""
    typer.echo("📘 Fabricatio Novel Generator CLI")
    typer.echo("Generate AI-assisted novels in various languages with customizable styling.")
    typer.echo("Powered by Fabricatio Core & DebugNovelWorkflow.")


# Side-effect imports: each module registers its commands onto `app` at
# module load time. Must come AFTER `app` is defined and AFTER `info`.
from fabricatio_novel.commands import (  # noqa: F401
    core,
    illustration,
    rag,
    rag_illustration,
    storage,
)

__all__ = ["app", "ns", "writer_role"]
