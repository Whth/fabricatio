"""Fabricatio Novel CLI.

This module provides a command-line interface to generate novels using AI-driven workflows.
It utilizes the Fabricatio Core library and includes functionality for generating novels
with customizable outlines, chapter guidance, language options, styling, and more.
"""

from fabricatio_core.utils import cfg

cfg(feats=["cli"])
from pathlib import Path
from typing import NoReturn

import typer
from fabricatio_core import Event, Role, Task

from fabricatio_novel.workflows.novel import DebugNovelWorkflow

app = typer.Typer(help="A CLI tool to generate novels using AI-driven workflows.")

# Register the writer role and workflow
writer_role = (
    Role(name="writer").register_workflow(Event.quick_instantiate(ns := "write"), DebugNovelWorkflow).dispatch()
)


def _exit_on_error(message: str) -> NoReturn:
    """Helper to display error and exit."""
    typer.secho(message, fg=typer.colors.RED, bold=True)
    raise typer.Exit(code=1) from None


@app.command(name="w")
def write_novel(  # noqa: PLR0913
    outline: str = typer.Option(
        None, "--outline", "-o", help="The novel's outline or premise.", envvar="NOVEL_OUTLINE"
    ),
    outline_file: Path = typer.Option(
        None,
        "--outline-file",
        "-of",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        help="Path to a text file containing the novel outline.",
        envvar="NOVEL_OUTLINE_FILE",
    ),
    output_path: Path = typer.Option(
        "./novel.epub", "--output", "-out", dir_okay=False, help="Output EPUB file path.", envvar="NOVEL_OUTPUT_PATH"
    ),
    font_file: Path = typer.Option(
        None,
        "--font",
        "-f",
        exists=True,
        dir_okay=False,
        help="Path to custom font file (TTF).",
        envvar="NOVEL_FONT_FILE",
    ),
    cover_image: Path = typer.Option(
        None,
        "--cover",
        "-c",
        exists=True,
        dir_okay=False,
        help="Path to cover image (PNG/JPG/WEBP).",
        envvar="NOVEL_COVER_IMAGE",
    ),
    language: str = typer.Option(
        "English", "--lang", "-l", help="Language of the novel (e.g., 简体中文, English, jp).", envvar="NOVEL_LANGUAGE"
    ),
    chapter_guidance: str = typer.Option(
        None, "--guidance", "-g", help="Guidelines for chapter generation.", envvar="NOVEL_CHAPTER_GUIDANCE"
    ),
    guidance_file: Path = typer.Option(
        None,
        "--guidance-file",
        "-gf",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        help="Path to a text file containing chapter generation guidelines.",
        envvar="NOVEL_GUIDANCE_FILE",
    ),
    persist_dir: Path = typer.Option(
        "./persist", "--persist-dir", help="Directory to save intermediate states.", envvar="NOVEL_PERSIST_DIR"
    ),
) -> None:
    """Generate a novel based on the provided outline and settings."""
    # Check mutual exclusivity for outline
    if outline is not None and outline_file is not None:
        _exit_on_error("❌ Cannot use both --outline and --outline-file. Please use only one.")

    if outline is None and outline_file is None:
        _exit_on_error("❌ Either --outline or --outline-file must be provided.")

    # Read outline
    try:
        outline_content = outline_file.read_text(encoding="utf-8").strip() if outline_file else outline.strip()
    except (OSError, IOError) as e:
        _exit_on_error(f"❌ Failed to read outline file: {e}")

    # Check mutual exclusivity for guidance
    if chapter_guidance is not None and guidance_file is not None:
        _exit_on_error("❌ Cannot use both --guidance and --guidance-file. Please use only one.")

    # Read guidance
    try:
        if guidance_file:
            guidance_content = guidance_file.read_text(encoding="utf-8").strip()
        elif chapter_guidance is not None:
            guidance_content = chapter_guidance.strip()
        else:
            guidance_content = ""
    except (OSError, IOError) as e:
        _exit_on_error(f"❌ Failed to read guidance file: {e}")

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


@app.command()
def info() -> None:
    """Show information about this CLI tool."""
    typer.echo("📘 Fabricatio Novel Generator CLI")
    typer.echo("Generate AI-assisted novels in various languages with customizable styling.")
    typer.echo("Powered by Fabricatio Core & DebugNovelWorkflow.")


__all__ = ["app"]
