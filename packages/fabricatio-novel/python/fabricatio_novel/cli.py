"""
CLI Application for generating novels using Fabricatio.
"""
from pathlib import Path

from fabricatio_core.utils import cfg, ok
cfg("fabricatio_novel.workflows", "questionary", "typer", feats=["cli"])
import typer
from fabricatio_core import Event, Role, Task
from fabricatio_novel.workflows.novel import DebugNovelWorkflow


app = typer.Typer(help="A CLI tool to generate novels using AI-driven workflows.")

# Register the writer role and workflow
writer_role = Role(name="writer").register_workflow(
    Event.quick_instantiate(ns := "write"), DebugNovelWorkflow
).dispatch()


@app.command(name="w")
def write_novel(
        outline: str = typer.Option(..., "--outline", "-o", help="The novel's outline or premise."),
        output_path: Path = typer.Option("./zh_novel.epub", "--output", "-out", dir_okay=False,
                                         help="Output EPUB file path."),
        font_file: Path = typer.Option(None, "--font", "-f", exists=True, dir_okay=False,
                                       help="Path to custom font file (TTF)."),
        cover_image: Path = typer.Option(None, "--cover", "-c", exists=True, dir_okay=False,
                                         help="Path to cover image (PNG/JPG)."),
        language: str = typer.Option("English", "--lang", "-l", help="Language of the novel (e.g., 简体中文, English, jp)."),
        chapter_guidance: str = typer.Option("", "--guidance", "-g", help="Guidelines for chapter generation."),
        persist_dir: Path = typer.Option("./persist", "--persist-dir", help="Directory to save intermediate states."),
):
    """
    Generate a novel based on the provided outline and settings.
    """

    typer.echo(f"Starting novel generation: '{outline[:30]}...'")

    task = Task(name="Write novel").update_init_context(
        novel_outline=outline,
        output_path=output_path,
        novel_font_file=font_file,
        cover_image=cover_image,
        novel_language=language,
        chapter_guidance=chapter_guidance,
        persist_dir=persist_dir,
    )

    result =  task.delegate_blocking(ns)

    if result:
        typer.secho(f"✅ Novel successfully generated: {result}", fg=typer.colors.GREEN, bold=True)
    else:
        typer.secho("❌ Failed to generate novel.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)



@app.command()
def info():
    """Show information about this CLI tool."""
    typer.echo("📘 Fabricatio Novel Generator CLI")
    typer.echo("Generate AI-assisted novels in various languages with customizable styling.")
    typer.echo("Powered by Fabricatio Core & DebugNovelWorkflow.")


__all__ = ["app"]