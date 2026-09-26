"""Novel-writing commands: generate a novel, plain or with writing-style RAG."""

import asyncio
from datetime import datetime
from pathlib import Path

import typer
from fabricatio_core import Event, Role, Task
from fabricatio_core.models.action import WorkFlow

from fabricatio_novel.actions.stage import StageAction, StageName
from fabricatio_novel.benchmark import (
    TermProbes,
    compare,
    find_baseline,
    render_comparison,
    render_scorecard,
    score_run,
)
from fabricatio_novel.cli import app
from fabricatio_novel.commands._helpers import _resolve_outline, _split_skills
from fabricatio_novel.models.context.novel import RagNovelContext
from fabricatio_novel.models.novel import ExportFormat
from fabricatio_novel.resume import ResumeError, ResumePoint
from fabricatio_novel.workflows.illustration import RagIllustrationDebugNovelWorkflow
from fabricatio_novel.workflows.novel import DebugNovelWorkflow
from fabricatio_novel.workflows.rag import RagDebugNovelWorkflow


def _run_workflow(task: Task, workflow: WorkFlow, namespace: str) -> Path | None:
    """Dispatch the task through the subscribed workflow and return its output (the artifact path)."""

    async def _run() -> Path | None:
        Role.with_bio(name="writer").subscribe(Event.quick_instantiate(namespace), workflow).dispatch()
        return await task.delegate(namespace)

    return asyncio.run(_run())


def _report_generation(run_dir: Path, artifact: Path, fmt: ExportFormat) -> None:
    """Echo the run summary with the exported artifact locations, then report the run's benchmark score."""
    parts = ["✅ Novel generated", f"   JSON:  {run_dir}"]
    match fmt:
        case ExportFormat.EPUB:
            parts.append(f"   EPUB:  {artifact}")
        case ExportFormat.TXT:
            parts.append(f"   TXT:   {artifact}")
        case ExportFormat.BOTH:
            parts.append(f"   EPUB:  {artifact}")
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


def _send_to_entry(send_to: str | None) -> dict[str, str]:
    """Return the ``send_to`` init-context entry for a run, or nothing when the option is unset.

    The plan stages fall back to the ``PLAN`` variant when the context carries no ``send_to``,
    so an unset option must leave the key out instead of writing ``None``: a present-but-``None``
    key would resolve every other stage through ``[llm] send_to`` rather than the ``TASK`` group
    the run defaults to.
    """
    return {} if send_to is None else {"send_to": send_to}


def _prepare_run(
    workflow: WorkFlow,
    persist_dir: Path,
    flat: bool,
    resume: Path | None,
    stage: StageName | None,
    *,
    rag: bool,
) -> tuple[Path, ResumePoint | None]:
    """Resolve the run this invocation drives: its directory and, when resuming, the point it continues from.

    A fresh invocation writes into a stamped (or flat) directory; ``--resume`` names a previous run
    instead, whose persisted state becomes the run's starting point while the stages up to it leave
    themselves out. Every way a resume can fail exits here, before a single LLM call: a missing run
    directory, ``--stage`` without ``--resume``, a stage the run holds no state before, and a run of
    the other family, which would silently drop the retrieval it was written with.
    """
    if resume is None:
        if stage is not None:
            typer.secho("❌ --stage needs --resume.", fg=typer.colors.RED, bold=True)
            raise typer.Exit(1)
        return (persist_dir if flat else _stamped_run_dir(persist_dir)), None
    run_dir = resume if resume.is_dir() else persist_dir / resume
    if not run_dir.is_dir():
        typer.secho(f"❌ Run directory '{resume}' does not exist.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    try:
        point = ResumePoint.of(workflow, run_dir, stage)
    except ResumeError as exc:
        typer.secho(f"❌ {exc}", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1) from exc
    if isinstance(point.context, RagNovelContext) is not rag:
        family, hint = ("plain", "fanvl w") if rag else ("RAG", "fanvl wr or fanvl wri")
        typer.secho(f"❌ '{run_dir}' holds a {family} run; resume it with {hint}.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    typer.secho(f"↻ Resuming '{run_dir}' at stage {point.stage}.", fg=typer.colors.CYAN)
    return run_dir, point


def _resume_seed(point: ResumePoint | None) -> dict[str, object]:
    """Return the init-context entries a resumed run continues from: the state it holds and the stages it leaves out."""
    return {} if point is None else {"novel_ctx": point.context, StageAction.held_key: point.done}


def _resume_retrieval(point: ResumePoint | None, rag_query: str | None, retrieve_limit: int) -> tuple[str, int]:
    """Resolve the retrieval settings a RAG run searches with.

    The story-planning stage seals its stories with the settings the run's context carries, so a
    resumed run that fell back to the option defaults would retrieve with a different query than
    the run it continues; the persisted root holds the settings that run sealed with, and an
    option the user stated explicitly still wins.
    """
    if point is None or not isinstance(point.context, RagNovelContext):
        return rag_query or "", retrieve_limit or 15
    return (
        rag_query if rag_query is not None else point.context.rag.query,
        retrieve_limit or point.context.rag.limit,
    )


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
    resume: Path | None = typer.Option(
        None,
        "--resume",
        help=(
            "Continue a previous run instead of starting a new one: its directory, or a run name resolved "
            "under --persist-dir. The run restarts at the stage --stage names, or at the stage after the newest one it persisted."
        ),
    ),
    stage: StageName | None = typer.Option(
        None,
        "--stage",
        help="Stage to restart at; the stages before it are left out and it runs from the state the run persisted last.",
    ),
    skills: list[str] = typer.Option(
        [],
        "--skill",
        "-s",
        help=(
            "Skill name from the fabricatio-skill library to use for this novel; repeat the option or pass a "
            "comma-separated list. The skill texts lead every planning prompt and the running manuscript."
        ),
    ),
    send_to: str | None = typer.Option(
        None,
        "--send-to",
        "-st",
        help="Routing group for the run's LLM calls; plan stages fall back to the PLAN variant when unset.",
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
    """Generate a novel from an outline."""
    if bible is not None and not bible.is_file():
        typer.secho(f"❌ Bible file '{bible}' does not exist.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    run_dir, point = _prepare_run(DebugNovelWorkflow, persist_dir, flat, resume, stage, rag=False)
    task = Task(name="write novel").update_init_context(
        novel_outline=_resolve_outline(outline, outline_file, resumed=point is not None),
        novel_language=language,
        writing_constraint=constraint or "",
        bible_path=bible,
        persist_dir=run_dir,
        output_path=output,
        export_format=export_format,
        font=font,
        cover=cover,
        skills=_split_skills(skills),
        **_resume_seed(point),
        **_send_to_entry(send_to),
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
    resume: Path | None = typer.Option(
        None,
        "--resume",
        help=(
            "Continue a previous run instead of starting a new one: its directory, or a run name resolved "
            "under --persist-dir. The run restarts at the stage --stage names, or at the stage after the newest one it persisted."
        ),
    ),
    stage: StageName | None = typer.Option(
        None,
        "--stage",
        help="Stage to restart at; the stages before it are left out and it runs from the state the run persisted last.",
    ),
    skills: list[str] = typer.Option(
        [],
        "--skill",
        "-s",
        help=(
            "Skill name from the fabricatio-skill library to use for this novel; repeat the option or pass a "
            "comma-separated list. The skill texts lead every planning prompt and the running manuscript."
        ),
    ),
    send_to: str | None = typer.Option(
        None,
        "--send-to",
        "-st",
        help="Routing group for the run's LLM calls; plan stages fall back to the PLAN variant when unset.",
    ),
    rag_query: str | None = typer.Option(
        None,
        "--rag-query",
        "-rq",
        help=(
            "Custom query guideline appended to every RAG level's own search text (the novel's outline, "
            "a story's description); empty searches that text alone."
        ),
    ),
    retrieve_limit: int = typer.Option(
        0,
        "--retrieve-limit",
        "-rl",
        help="Reference documents kept per retrieval level (0 = default 15).",
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
    run_dir, point = _prepare_run(RagDebugNovelWorkflow, persist_dir, flat, resume, stage, rag=True)
    rag_query, retrieve_limit = _resume_retrieval(point, rag_query, retrieve_limit)
    task = Task(name="write novel with rag").update_init_context(
        novel_outline=_resolve_outline(outline, outline_file, resumed=point is not None),
        novel_language=language,
        writing_constraint=constraint or "",
        bible_path=bible,
        rag_query=rag_query,
        rag_limit=retrieve_limit,
        persist_dir=run_dir,
        output_path=output,
        export_format=export_format,
        font=font,
        cover=cover,
        skills=_split_skills(skills),
        **_resume_seed(point),
        **_send_to_entry(send_to),
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
    resume: Path | None = typer.Option(
        None,
        "--resume",
        help=(
            "Continue a previous run instead of starting a new one: its directory, or a run name resolved "
            "under --persist-dir. The run restarts at the stage --stage names, or at the stage after the newest one it persisted."
        ),
    ),
    stage: StageName | None = typer.Option(
        None,
        "--stage",
        help="Stage to restart at; the stages before it are left out and it runs from the state the run persisted last.",
    ),
    skills: list[str] = typer.Option(
        [],
        "--skill",
        "-s",
        help=(
            "Skill name from the fabricatio-skill library to use for this novel; repeat the option or pass a "
            "comma-separated list. The skill texts lead every planning prompt and the running manuscript."
        ),
    ),
    send_to: str | None = typer.Option(
        None,
        "--send-to",
        "-st",
        help="Routing group for the run's LLM calls; plan stages fall back to the PLAN variant when unset.",
    ),
    rag_query: str | None = typer.Option(
        None,
        "--rag-query",
        "-rq",
        help=(
            "Custom query guideline appended to every RAG level's own search text (the novel's outline, "
            "a story's description); empty searches that text alone."
        ),
    ),
    retrieve_limit: int = typer.Option(
        0,
        "--retrieve-limit",
        "-rl",
        help="Reference documents kept per retrieval level (0 = default 15).",
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
    run_dir, point = _prepare_run(RagIllustrationDebugNovelWorkflow, persist_dir, flat, resume, stage, rag=True)
    rag_query, retrieve_limit = _resume_retrieval(point, rag_query, retrieve_limit)
    task = Task(name="write novel with rag and illustration").update_init_context(
        novel_outline=_resolve_outline(outline, outline_file, resumed=point is not None),
        novel_language=language,
        writing_constraint=constraint or "",
        bible_path=bible,
        rag_query=rag_query,
        rag_limit=retrieve_limit,
        persist_dir=run_dir,
        output_path=output,
        export_format=export_format,
        font=font,
        cover=cover,
        skills=_split_skills(skills),
        **_resume_seed(point),
        **_send_to_entry(send_to),
        illustration_choose_loras=True if choose_loras else None,
        illustration_judge=True if judge else None,
        illustration_judge_max_tries=judge_tries or None,
    )
    artifact = _run_workflow(task, RagIllustrationDebugNovelWorkflow, "write_rag_illustration")
    if artifact is None:
        typer.secho("❌ Failed to generate novel.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)
    _report_generation(run_dir, artifact, export_format)
