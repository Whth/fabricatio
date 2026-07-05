"""Core write-novel CLI commands (no RAG, no illustration).

Registers onto the shared ``app`` from :mod:`fabricatio_novel.cli`:

- ``w``  — :func:`write_novel`
- ``wm`` — :func:`write_novel_with_mental` (character psychology tracking)
"""

from pathlib import Path

import typer
from fabricatio_core import Event, Role, Task

from fabricatio_novel.cli import app, ns
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


@app.command(name="w")
def write_novel(  # noqa: PLR0913
    outline: str = OUTLINE,
    outline_file: Path = OUTLINE_FILE,
    output_path: Path = OUTPUT_PATH,
    font_file: Path = FONT_FILE,
    cover_image: Path = COVER_IMAGE,
    language: str = LANGUAGE,
    chapter_guidance: str = CHAPTER_GUIDANCE,
    guidance_file: Path = GUIDANCE_FILE,
    persist_dir: Path = PERSIST_DIR,
) -> None:
    """Generate a novel based on the provided outline and settings."""
    outline_content = _resolve_text_or_file(outline, outline_file, flag="outline", required=True)

    guidance_content = _resolve_text_or_file(chapter_guidance, guidance_file, flag="guidance")

    typer.echo(f"Starting novel generation: '{outline_content[:30]}...'")

    task = Task(name="Write novel").update_init_context(
        novel_outline=outline_content,
        output_path=output_path,
        novel_font_file=font_file,
        cover_image=cover_image,
        novel_language=language,
        chapter_guidance=guidance_content,
        persist_dir=persist_dir,
    )

    result = task.delegate_blocking(ns)

    if result:
        typer.secho(f"✅ Novel successfully generated: {result}", fg=typer.colors.GREEN, bold=True)
    else:
        _exit_on_error("❌ Failed to generate novel.")


@app.command(name="wm")
def write_novel_with_mental(  # noqa: PLR0913
    outline: str = OUTLINE,
    outline_file: Path = OUTLINE_FILE,
    output_path: Path = OUTPUT_PATH,
    font_file: Path = FONT_FILE,
    cover_image: Path = COVER_IMAGE,
    language: str = LANGUAGE,
    chapter_guidance: str = CHAPTER_GUIDANCE,
    guidance_file: Path = GUIDANCE_FILE,
    persist_dir: Path = PERSIST_DIR,
) -> None:
    """Generate a novel with mental state tracking for character psychology."""
    from fabricatio_novel.workflows.novel_mental import DebugNovelWithMentalWorkflow

    mental_ns = "write_mental"
    Role.with_bio(name="mental_writer").subscribe(
        Event.quick_instantiate(mental_ns), DebugNovelWithMentalWorkflow
    ).dispatch()

    outline_content = _resolve_text_or_file(outline, outline_file, flag="outline", required=True)

    guidance_content = _resolve_text_or_file(chapter_guidance, guidance_file, flag="guidance")

    typer.echo(f"Starting mental novel generation: '{outline_content[:30]}...'")

    task = Task(name="Write novel with mental states").update_init_context(
        novel_outline=outline_content,
        output_path=output_path,
        novel_font_file=font_file,
        cover_image=cover_image,
        novel_language=language,
        chapter_guidance=guidance_content,
        persist_dir=persist_dir,
    )

    result = task.delegate_blocking(mental_ns)

    if result:
        typer.secho(
            f"✅ Novel with mental states successfully generated: {result}",
            fg=typer.colors.GREEN,
            bold=True,
        )
    else:
        _exit_on_error("❌ Failed to generate novel with mental states.")
