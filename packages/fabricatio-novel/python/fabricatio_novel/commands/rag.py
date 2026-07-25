"""RAG-augmented write-novel CLI commands (lancedb-gated).

Registers onto the shared ``app`` from :mod:`fabricatio_novel.cli`:

- ``wr``  — :func:`write_novel_with_rag`
- ``wrm`` — :func:`write_novel_with_mental_rag`
"""

from pathlib import Path

import typer
from fabricatio_core import Event, Role, Task
from fabricatio_core.decorators import cfg_on

# Imported lazily inside each command body to avoid pulling lancedb at module load.
from fabricatio_novel.cli import app
from fabricatio_novel.commands._helpers import _exit_on_error, _resolve_text_or_file
from fabricatio_novel.commands._options import (
    CHAPTER_GUIDANCE,
    COVER_IMAGE,
    FONT_FILE,
    GUIDANCE_FILE,
    LANGUAGE,
    OUTLINE,
    OUTLINE_FILE,
    OUTPUT_PATH,
    PERSIST_DIR,
)

_RAG_LIMIT: typer.Option = typer.Option(
    5,
    "--rag-limit",
    "-rl",
    help="Number of writing style documents to retrieve per prompt.",
    envvar="NOVEL_RAG_LIMIT",
)
_RAG_QUERY: typer.Option = typer.Option(
    ...,
    "--rag-query",
    "-rq",
    help="Writing style query for RAG retrieval (e.g. 'Hemingway terse prose style').",
    envvar="NOVEL_RAG_QUERY",
)


@app.command(name="wr")
@cfg_on(["lancedb"])
def write_novel_with_rag(  # noqa: PLR0913
    outline: str = OUTLINE,
    outline_file: Path = OUTLINE_FILE,
    rag_query: str = _RAG_QUERY,
    output_path: Path = OUTPUT_PATH,
    font_file: Path = FONT_FILE,
    cover_image: Path = COVER_IMAGE,
    language: str = LANGUAGE,
    chapter_guidance: str = CHAPTER_GUIDANCE,
    guidance_file: Path = GUIDANCE_FILE,
    persist_dir: Path = PERSIST_DIR,
    rag_limit: int = _RAG_LIMIT,
) -> None:
    """Generate a novel with RAG writing style augmentation based on the provided outline."""
    from fabricatio_novel.models.novel_rag import WritingStyleFetchConfig
    from fabricatio_novel.workflows.novel_rag import DebugNovelWithRAGWorkflow

    rag_ns = "write_rag"
    Role.with_bio(name="rag_writer").subscribe(Event.quick_instantiate(rag_ns), DebugNovelWithRAGWorkflow).dispatch()

    outline_content = _resolve_text_or_file(outline, outline_file, flag="outline", required=True)

    guidance_content = _resolve_text_or_file(chapter_guidance, guidance_file, flag="guidance")

    typer.echo(f"Starting RAG novel generation: '{outline_content[:30]}...'")
    typer.echo(f"Writing style query: '{rag_query}'")

    task = Task(name="Write novel with RAG").update_init_context(
        novel_outline=outline_content,
        writing_style_requirement=rag_query,
        output_path=output_path,
        novel_font_file=font_file,
        cover_image=cover_image,
        novel_language=language,
        chapter_guidance=guidance_content,
        persist_dir=persist_dir,
        writing_style_fetch_config=WritingStyleFetchConfig(
            limit=rag_limit,
        ),
    )

    result = task.delegate_blocking(rag_ns)

    if result:
        typer.secho(f"✅ Novel with RAG styles successfully generated: {result}", fg=typer.colors.GREEN, bold=True)
    else:
        _exit_on_error("❌ Failed to generate novel with RAG.")


@app.command(name="wrm")
@cfg_on(["lancedb"])
def write_novel_with_mental_rag(  # noqa: PLR0913
    outline: str = OUTLINE,
    outline_file: Path = OUTLINE_FILE,
    rag_query: str = _RAG_QUERY,
    output_path: Path = OUTPUT_PATH,
    font_file: Path = FONT_FILE,
    cover_image: Path = COVER_IMAGE,
    language: str = LANGUAGE,
    chapter_guidance: str = CHAPTER_GUIDANCE,
    guidance_file: Path = GUIDANCE_FILE,
    persist_dir: Path = PERSIST_DIR,
    rag_limit: int = _RAG_LIMIT,
) -> None:
    """Generate a novel with RAG writing styles + mental state tracking."""
    from fabricatio_novel.models.novel_rag import WritingStyleFetchConfig
    from fabricatio_novel.workflows.novel_mental import DebugNovelWithMentalRAGWorkflow

    mental_rag_ns = "write_mental_rag"
    Role.with_bio(name="mental_rag_writer").subscribe(
        Event.quick_instantiate(mental_rag_ns), DebugNovelWithMentalRAGWorkflow
    ).dispatch()

    outline_content = _resolve_text_or_file(outline, outline_file, flag="outline", required=True)
    guidance_content = _resolve_text_or_file(chapter_guidance, guidance_file, flag="guidance")

    typer.echo(f"Starting RAG+Mental novel generation: '{outline_content[:30]}...'")
    typer.echo(f"Writing style query: '{rag_query}'")

    task = Task(name="Write novel with RAG+Mental").update_init_context(
        novel_outline=outline_content,
        writing_style_requirement=rag_query,
        output_path=output_path,
        novel_font_file=font_file,
        cover_image=cover_image,
        novel_language=language,
        chapter_guidance=guidance_content,
        persist_dir=persist_dir,
        writing_style_fetch_config=WritingStyleFetchConfig(
            limit=rag_limit,
        ),
    )

    result = task.delegate_blocking(mental_rag_ns)

    if result:
        typer.secho(f"✅ Novel with RAG+Mental successfully generated: {result}", fg=typer.colors.GREEN, bold=True)
    else:
        _exit_on_error("❌ Failed to generate novel with RAG+Mental.")
