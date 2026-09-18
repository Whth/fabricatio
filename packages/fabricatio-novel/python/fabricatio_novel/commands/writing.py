"""Novel-writing commands: generate a novel, plain or with writing-style RAG."""

import asyncio
from datetime import datetime
from enum import StrEnum
from pathlib import Path

import typer
from fabricatio_core import Event, Role, Task
from fabricatio_core.models.action import WorkFlow
from fabricatio_core.rust import TASK

from fabricatio_novel.benchmark import (
    TermProbes,
    compare,
    find_baseline,
    render_comparison,
    render_scorecard,
    score_run,
)
from fabricatio_novel.cli import app
from fabricatio_novel.commands._helpers import _resolve_outline
from fabricatio_novel.workflows.novel import (
    DebugNovelWorkflow,
    RagDebugNovelWorkflow,
    RagIllustrationDebugNovelWorkflow,
)


def _run_workflow(task: Task, workflow: WorkFlow, namespace: str) -> Path | None:
    """Dispatch the task through the subscribed workflow and return its output (the artifact path)."""

    async def _run() -> Path | None:
        Role.with_bio(name="writer").subscribe(Event.quick_instantiate(namespace), workflow).dispatch()
        return await task.delegate(namespace)

    return asyncio.run(_run())


class ExportFormat(StrEnum):
    """Export formats for a generated novel."""

    EPUB = "epub"
    TXT = "txt"
    BOTH = "both"


def _report_generation(run_dir: Path, artifact: Path, fmt: ExportFormat) -> None:
    """Echo the run summary with the exported artifact locations, then report the run's benchmark score."""
    parts = ["✅ Novel generated", f"   JSON:  {run_dir}"]
    if fmt is ExportFormat.TXT:
        parts.append(f"   TXT:   {artifact}")
    else:
        parts.append(f"   EPUB:  {artifact}")
        if fmt is ExportFormat.BOTH:
            parts.append(f"   TXT:   {run_dir / 'chapters'}")
    typer.secho("\n   ".join(parts), fg=typer.colors.GREEN, bold=True)
    _report_benchmark(run_dir)


def _report_benchmark(run_dir: Path) -> None:
    """Print the finished run's quality scorecard and its delta against the newest comparable run.

    Scoring reads the artifacts the run just persisted, so it costs no LLM calls.
    A scoring failure is reported as a warning instead of an error: by this point the
    novel is written, assembled and exported, and a broken scorecard must not turn a
    successful run into a failed one.
    """
    try:
        probes = TermProbes.resolve()
    except (OSError, ValueError) as exc:
        typer.secho(f"benchmark probes ignored: {exc}", fg=typer.colors.YELLOW)
        probes = None
    try:
        card = score_run(run_dir, probes=probes)
        baseline = find_baseline(card, probes=probes)
    except (OSError, ValueError) as exc:
        typer.secho(f"benchmark skipped: {exc}", fg=typer.colors.YELLOW, bold=True)
        return
    typer.echo(render_scorecard(card))
    if baseline is not None:
        typer.echo(render_comparison(compare(baseline, card)))


def _stamped_run_dir(persist_dir: Path) -> Path:
    """Return ``<persist_dir>/<YYYYmmdd-HHMMSS>`` for this run, uniquified with a -N suffix."""
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    run_dir = persist_dir / timestamp
    n = 2
    while run_dir.exists():
        run_dir = persist_dir / f"{timestamp}-{n}"
        n += 1
    return run_dir


@app.command(name="w")
def write_novel(  # noqa: PLR0913 - flat signature required by typer option derivation
    *,
    outline: str | None = typer.Argument(None, help="Novel outline text."),
    outline_file: Path | None = typer.Option(
        None,
        "--outline-file",
        "-of",
        help="Read the outline from a file instead of the positional argument.",
    ),
    language: str | None = typer.Option(
        None,
        "--language",
        "--lang",
        "-l",
        help="Written language. Auto-detected from the outline when omitted.",
    ),
    persist_dir: Path = typer.Option(
        Path("novels"),
        "--persist-dir",
        "-p",
        help="Root directory for run outputs; each run is written into its own timestamped subdirectory.",
    ),
    flat: bool = typer.Option(
        False,
        "--flat",
        help="Write directly into --persist-dir instead of a timestamped run subdirectory.",
    ),
    send_to: str = typer.Option(TASK, "--send-to", "-st", help="Routing group for LLM calls."),
    font: Path | None = typer.Option(
        None,
        "--font",
        "-f",
        help="Font file (.ttf) to embed in the EPUB and apply to its body text.",
    ),
    cover: Path | None = typer.Option(None, "--cover", help="Cover image file to embed in the EPUB."),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="EPUB output file name (relative to the run directory).",
    ),
    export_format: ExportFormat = typer.Option(
        ExportFormat.EPUB,
        "--format",
        help="Export format: 'epub' only, 'txt' (one plain-text file per chapter, zero-padded index names), or 'both'.",
    ),
    bible: Path | None = typer.Option(None, "--bible", "-b", help="Setting bible JSON to constrain scene generation."),
    constraint: str | None = typer.Option(
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
        format=export_format.value,
        font=font,
        cover=cover,
        send_to=send_to,
    )
    artifact = _run_workflow(task, DebugNovelWorkflow, "write")
    if artifact is None:
        typer.secho("❌ Failed to generate novel.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    _report_generation(run_dir, artifact, export_format)


@app.command(name="wr")
def write_novel_with_rag(  # noqa: PLR0913 - flat signature required by typer option derivation
    *,
    outline: str | None = typer.Argument(None, help="Novel outline text."),
    outline_file: Path | None = typer.Option(
        None,
        "--outline-file",
        "-of",
        help="Read the outline from a file instead of the positional argument.",
    ),
    language: str | None = typer.Option(
        None,
        "--language",
        "--lang",
        "-l",
        help="Written language. Auto-detected from the outline when omitted.",
    ),
    persist_dir: Path = typer.Option(
        Path("novels"),
        "--persist-dir",
        "-p",
        help="Root directory for run outputs; each run is written into its own timestamped subdirectory.",
    ),
    flat: bool = typer.Option(
        False,
        "--flat",
        help="Write directly into --persist-dir instead of a timestamped run subdirectory.",
    ),
    send_to: str = typer.Option(TASK, "--send-to", "-st", help="Routing group for LLM calls."),
    rag_query: str | None = typer.Option(
        None,
        "--rag-query",
        "-rq",
        help="Custom query guideline for writing style retrieval; defaults to the story description.",
    ),
    retrieve_limit: int = typer.Option(
        0,
        "--retrieve-limit",
        "-rl",
        help="Reference documents kept per story (0 = default 15).",
    ),
    font: Path | None = typer.Option(
        None,
        "--font",
        "-f",
        help="Font file (.ttf) to embed in the EPUB and apply to its body text.",
    ),
    cover: Path | None = typer.Option(None, "--cover", help="Cover image file to embed in the EPUB."),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="EPUB output file name (relative to the run directory).",
    ),
    export_format: ExportFormat = typer.Option(
        ExportFormat.EPUB,
        "--format",
        help="Export format: 'epub' only, 'txt' (one plain-text file per chapter, zero-padded index names), or 'both'.",
    ),
    bible: Path | None = typer.Option(None, "--bible", "-b", help="Setting bible JSON to constrain scene generation."),
    constraint: str | None = typer.Option(
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
        format=export_format.value,
        font=font,
        cover=cover,
        send_to=send_to,
    )
    artifact = _run_workflow(task, RagDebugNovelWorkflow, "write_rag")
    if artifact is None:
        typer.secho("❌ Failed to generate novel.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    _report_generation(run_dir, artifact, export_format)


@app.command(name="wri")
def write_novel_with_rag_and_illustration(  # noqa: PLR0913 - flat signature required by typer option derivation
    *,
    outline: str | None = typer.Argument(None, help="Novel outline text."),
    outline_file: Path | None = typer.Option(
        None,
        "--outline-file",
        "-of",
        help="Read the outline from a file instead of the positional argument.",
    ),
    language: str | None = typer.Option(
        None,
        "--language",
        "--lang",
        "-l",
        help="Written language. Auto-detected from the outline when omitted.",
    ),
    persist_dir: Path = typer.Option(
        Path("novels"),
        "--persist-dir",
        "-p",
        help="Root directory for run outputs; each run is written into its own timestamped subdirectory.",
    ),
    flat: bool = typer.Option(
        False,
        "--flat",
        help="Write directly into --persist-dir instead of a timestamped run subdirectory.",
    ),
    send_to: str = typer.Option(TASK, "--send-to", "-st", help="Routing group for LLM calls."),
    rag_query: str | None = typer.Option(
        None,
        "--rag-query",
        "-rq",
        help="Custom query guideline for writing style retrieval; defaults to the story description.",
    ),
    retrieve_limit: int = typer.Option(
        0,
        "--retrieve-limit",
        "-rl",
        help="Reference documents kept per story (0 = default 15).",
    ),
    font: Path | None = typer.Option(
        None,
        "--font",
        "-f",
        help="Font file (.ttf) to embed in the EPUB and apply to its body text.",
    ),
    cover: Path | None = typer.Option(None, "--cover", help="Cover image file to embed in the EPUB."),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="EPUB output file name (relative to the run directory).",
    ),
    export_format: ExportFormat = typer.Option(
        ExportFormat.EPUB,
        "--format",
        help="Export format: 'epub' only, 'txt' (one plain-text file per chapter, zero-padded index names), or 'both'.",
    ),
    bible: Path | None = typer.Option(None, "--bible", "-b", help="Setting bible JSON to constrain scene generation."),
    constraint: str | None = typer.Option(
        None,
        "--constraint",
        "-c",
        help="Global writing constraint to honor throughout the novel (e.g. 'first person view').",
    ),
    choose_loras: bool = typer.Option(
        False,
        "--choose-loras",
        help="Let the LLM pick LoRAs from the \\[ext.comfyui] loras catalog for each scene illustration (config default: off).",
    ),
    judge: bool = typer.Option(
        False,
        "--judge",
        help="Visually judge each scene illustration with a vision LLM and re-render with a revised prompt until it passes (config default: off).",
    ),
    judge_tries: int = typer.Option(
        0,
        "--judge-tries",
        help="Total generation attempts per scene when --judge is on (0 = config default 3).",
    ),
) -> None:
    """Generate a novel with writing style RAG and per-scene ComfyUI illustrations from an outline."""
    if bible is not None and not bible.is_file():
        typer.secho(f"❌ Bible file '{bible}' does not exist.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    run_dir = persist_dir if flat else _stamped_run_dir(persist_dir)
    task = Task(name="write novel with rag and illustration").update_init_context(
        novel_outline=_resolve_outline(outline, outline_file),
        novel_language=language,
        writing_constraint=constraint or "",
        bible_path=bible,
        rag_query=rag_query or "",
        rag_limit=retrieve_limit or 15,
        persist_dir=run_dir,
        output_path=output,
        format=export_format.value,
        font=font,
        cover=cover,
        send_to=send_to,
        illustration_choose_loras=True if choose_loras else None,
        illustration_judge=True if judge else None,
        illustration_judge_max_tries=judge_tries or None,
    )
    artifact = _run_workflow(task, RagIllustrationDebugNovelWorkflow, "write_rag_illustration")
    if artifact is None:
        typer.secho("❌ Failed to generate novel.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    _report_generation(run_dir, artifact, export_format)
