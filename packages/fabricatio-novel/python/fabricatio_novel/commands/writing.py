"""Novel-writing commands: generate a novel, plain or with writing-style RAG."""

import asyncio
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

import typer
from fabricatio_core import Event, Role, Task
from fabricatio_core.models.action import WorkFlow
from fabricatio_core.rust import TASK

from fabricatio_novel.cli import app
from fabricatio_novel.commands._helpers import _resolve_outline
from fabricatio_novel.workflows.novel import DebugNovelWorkflow, RagDebugNovelWorkflow


def _run_workflow(task: Task, workflow: WorkFlow, namespace: str) -> Optional[Path]:
    """Dispatch the task through the subscribed workflow and return its output (the artifact path)."""

    async def _run() -> Optional[Path]:
        Role.with_bio(name="writer").subscribe(Event.quick_instantiate(namespace), workflow).dispatch()
        return await task.delegate(namespace)

    return asyncio.run(_run())


class ExportFormat(str, Enum):
    """Export formats for a generated novel."""

    EPUB = "epub"
    TXT = "txt"
    BOTH = "both"


def _report_generation(run_dir: Path, artifact: Path, fmt: ExportFormat) -> None:
    """Echo the run summary with the exported artifact locations."""
    parts = ["✅ Novel generated", f"   JSON:  {run_dir}"]
    if fmt is ExportFormat.TXT:
        parts.append(f"   TXT:   {artifact}")
    else:
        parts.append(f"   EPUB:  {artifact}")
        if fmt is ExportFormat.BOTH:
            parts.append(f"   TXT:   {run_dir / 'chapters'}")
    typer.secho("\n   ".join(parts), fg=typer.colors.GREEN, bold=True)


def _stamped_run_dir(persist_dir: Path) -> Path:
    """Return ``<persist_dir>/<YYYYmmdd-HHMMSS>`` for this run, uniquified with a -N suffix."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = persist_dir / timestamp
    n = 2
    while run_dir.exists():
        run_dir = persist_dir / f"{timestamp}-{n}"
        n += 1
    return run_dir


@app.command(name="w")
def write_novel(  # noqa: PLR0913 - flat signature required by typer option derivation
    *,
    outline: Optional[str] = typer.Argument(None, help="Novel outline text."),
    outline_file: Optional[Path] = typer.Option(
        None, "--outline-file", "-of", help="Read the outline from a file instead of the positional argument."
    ),
    language: Optional[str] = typer.Option(
        None, "--language", "--lang", "-l", help="Written language. Auto-detected from the outline when omitted."
    ),
    persist_dir: Path = typer.Option(
        Path("novels"),
        "--persist-dir",
        "-p",
        help="Root directory for run outputs; each run is written into its own timestamped subdirectory.",
    ),
    flat: bool = typer.Option(
        False, "--flat", help="Write directly into --persist-dir instead of a timestamped run subdirectory."
    ),
    send_to: str = typer.Option(TASK, "--send-to", "-st", help="Routing group for LLM calls."),
    font: Optional[Path] = typer.Option(
        None, "--font", "-f", help="Font file (.ttf) to embed in the EPUB and apply to its body text."
    ),
    cover: Optional[Path] = typer.Option(None, "--cover", help="Cover image file to embed in the EPUB."),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="EPUB output file name (relative to the run directory)."
    ),
    format: ExportFormat = typer.Option(
        ExportFormat.EPUB,
        "--format",
        help="Export format: 'epub' only, 'txt' (one plain-text file per chapter, zero-padded index names), or 'both'.",
    ),
    bible: Optional[Path] = typer.Option(
        None, "--bible", "-b", help="Setting bible JSON to constrain scene generation."
    ),
    constraint: Optional[str] = typer.Option(
        None,
        "--constraint",
        "-c",
        help="Global writing constraint to honor throughout the novel (e.g. 'first person view').",
    ),
) -> None:
    """Generate a novel from an outline."""
    if bible is not None and not bible.is_file():
        typer.secho(f"❌ Bible file '{bible}' does not exist.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    run_dir = persist_dir if flat else _stamped_run_dir(persist_dir)
    task = Task(name="write novel").update_init_context(
        novel_outline=_resolve_outline(outline, outline_file),
        novel_language=language,
        writing_constraint=constraint or "",
        bible_path=bible,
        persist_dir=run_dir,
        output_path=output,
        format=format.value,
        font=font,
        cover=cover,
        send_to=send_to,
    )
    artifact = _run_workflow(task, DebugNovelWorkflow, "write")
    if artifact is None:
        typer.secho("❌ Failed to generate novel.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    _report_generation(run_dir, artifact, format)


@app.command(name="wr")
def write_novel_with_rag(  # noqa: PLR0913 - flat signature required by typer option derivation
    *,
    outline: Optional[str] = typer.Argument(None, help="Novel outline text."),
    outline_file: Optional[Path] = typer.Option(
        None, "--outline-file", "-of", help="Read the outline from a file instead of the positional argument."
    ),
    language: Optional[str] = typer.Option(
        None, "--language", "--lang", "-l", help="Written language. Auto-detected from the outline when omitted."
    ),
    persist_dir: Path = typer.Option(
        Path("novels"),
        "--persist-dir",
        "-p",
        help="Root directory for run outputs; each run is written into its own timestamped subdirectory.",
    ),
    flat: bool = typer.Option(
        False, "--flat", help="Write directly into --persist-dir instead of a timestamped run subdirectory."
    ),
    send_to: str = typer.Option(TASK, "--send-to", "-st", help="Routing group for LLM calls."),
    rag_query: Optional[str] = typer.Option(
        None,
        "--rag-query",
        "-rq",
        help="Custom query guideline for writing style retrieval; defaults to the story description.",
    ),
    retrieve_limit: int = typer.Option(
        0, "--retrieve-limit", "-rl", help="Final reference documents kept after reranking (0 = default 15)."
    ),
    font: Optional[Path] = typer.Option(
        None, "--font", "-f", help="Font file (.ttf) to embed in the EPUB and apply to its body text."
    ),
    cover: Optional[Path] = typer.Option(None, "--cover", help="Cover image file to embed in the EPUB."),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="EPUB output file name (relative to the run directory)."
    ),
    format: ExportFormat = typer.Option(
        ExportFormat.EPUB,
        "--format",
        help="Export format: 'epub' only, 'txt' (one plain-text file per chapter, zero-padded index names), or 'both'.",
    ),
    bible: Optional[Path] = typer.Option(
        None, "--bible", "-b", help="Setting bible JSON to constrain scene generation."
    ),
    constraint: Optional[str] = typer.Option(
        None,
        "--constraint",
        "-c",
        help="Global writing constraint to honor throughout the novel (e.g. 'first person view').",
    ),
) -> None:
    """Generate a novel with writing style RAG from an outline."""
    if bible is not None and not bible.is_file():
        typer.secho(f"❌ Bible file '{bible}' does not exist.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    run_dir = persist_dir if flat else _stamped_run_dir(persist_dir)
    task = Task(name="write novel with rag").update_init_context(
        novel_outline=_resolve_outline(outline, outline_file),
        novel_language=language,
        writing_constraint=constraint or "",
        bible_path=bible,
        rag_query=rag_query or "",
        rag_limit=retrieve_limit or 15,
        persist_dir=run_dir,
        output_path=output,
        format=format.value,
        font=font,
        cover=cover,
        send_to=send_to,
    )
    artifact = _run_workflow(task, RagDebugNovelWorkflow, "write_rag")
    if artifact is None:
        typer.secho("❌ Failed to generate novel.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    _report_generation(run_dir, artifact, format)
