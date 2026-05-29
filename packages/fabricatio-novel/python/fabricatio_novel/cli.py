"""Fabricatio Novel CLI.

This module provides a command-line interface to generate novels using AI-driven workflows.
It utilizes the Fabricatio Core library and includes functionality for generating novels
with customizable outlines, chapter guidance, language options, styling, and more.
"""

from fabricatio_core.utils import cfg

cfg(feats=["cli"])
from pathlib import Path
from typing import NoReturn, Optional

import typer
from fabricatio_core import Event, Role, Task

from fabricatio_novel.workflows.novel import DebugNovelWorkflow
from fabricatio_novel.workflows.novel_rag import DebugNovelWithRAGWorkflow, StoreWritingStyleTextsWorkflow

app = typer.Typer(help="A CLI tool to generate novels using AI-driven workflows.")

# Register the writer role and workflow
ns = "write"
writer_role = Role.with_bio(name="writer").subscribe(Event.quick_instantiate(ns), DebugNovelWorkflow).dispatch()
rag_ns = "write_rag"
rag_writer_role = (
    Role.with_bio(name="rag_writer").subscribe(Event.quick_instantiate(rag_ns), DebugNovelWithRAGWorkflow).dispatch()
)
store_refs_ns = "store_refs"
store_refs_role = (
    Role.with_bio(name="ref_ingester")
    .subscribe(Event.quick_instantiate(store_refs_ns), StoreWritingStyleTextsWorkflow)
    .dispatch()
)


def _exit_on_error(message: str) -> NoReturn:
    """Helper to display error and exit."""
    typer.secho(message, fg=typer.colors.RED, bold=True)
    raise typer.Exit(code=1) from None


def _collect_files(patterns: list[str]) -> list[Path]:
    """Expand glob patterns and literal file paths into a deduplicated, sorted file list.

    Raises typer.Exit if no valid files are found.
    """
    seen: set[Path] = set()
    for pat in patterns:
        matched = list(Path().glob(pat))
        if matched:
            for p in matched:
                resolved = p.resolve()
                if resolved.is_file():
                    seen.add(resolved)
        else:
            p = Path(pat).resolve()
            if not p.is_file():
                _exit_on_error(f"❌ No files matched pattern and not a file: {pat}")
            seen.add(p)
    files = sorted(seen)
    if not files:
        _exit_on_error("❌ No valid files found from provided patterns.")
    return files


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


@app.command(name="wr")
def write_novel_with_rag(  # noqa: PLR0913
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
    rag_query: str = typer.Option(
        ...,
        "--rag-query",
        "-rq",
        help="Writing style query for RAG retrieval (e.g. 'Hemingway terse prose style').",
        envvar="NOVEL_RAG_QUERY",
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
    """Generate a novel with RAG writing style augmentation based on the provided outline."""
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

    typer.echo(f"Starting RAG novel generation: '{outline_content[:30]}...'")
    typer.echo(f"Writing style query: '{rag_query}'")

    task = Task(name="Write novel with RAG").update_init_context(
        novel_outline=outline_content,
        writing_style_query=rag_query,
        output_path=output_path,
        novel_font_file=font_file,
        cover_image=cover_image,
        novel_language=language,
        chapter_guidance=guidance_content,
        persist_dir=persist_dir,
    )

    result = task.delegate_blocking(rag_ns)

    if result:
        typer.secho(f"✅ Novel with RAG styles successfully generated: {result}", fg=typer.colors.GREEN, bold=True)
    else:
        _exit_on_error("❌ Failed to generate novel with RAG.")


@app.command()
def info() -> None:
    """Show information about this CLI tool."""
    typer.echo("📘 Fabricatio Novel Generator CLI")
    typer.echo("Generate AI-assisted novels in various languages with customizable styling.")
    typer.echo("Powered by Fabricatio Core & DebugNovelWorkflow.")


@app.command(name="store-refs")
def store_reference_texts(
    patterns: list[str] = typer.Argument(
        ...,
        help="File paths and/or glob patterns to ingest (e.g. 'refs/*.txt').",
    ),
    chunks_size: int = typer.Option(
        512, "--chunks-size", "-cs", help="Maximum words per chunk when splitting files.", envvar="NOVEL_CHUNKS_SIZE"
    ),
    overlap: float = typer.Option(
        0.3, "--overlap", "-ov", help="Overlap ratio between consecutive chunks (0.0–1.0).", envvar="NOVEL_OVERLAP"
    ),
    ndim: Optional[int] = typer.Option(
        None,
        "--ndim",
        "-nd",
        help="Embedding vector dimensionality. Must match the embedding model's output dimension.",
        envvar="FABRICATIO_EMBEDDING__NDIM",
    ),
    embedding_send_to: Optional[str] = typer.Option(
        None,
        "--send-to",
        "-st",
        help="Routing group for embedding requests.",
        envvar="FABRICATIO_EMBEDDING__SEND_TO",
    ),
    batch_size: int = typer.Option(
        10, "--batch-size", "-bs", help="Number of chunks per storage batch.", envvar="NOVEL_BATCH_SIZE"
    ),
) -> None:
    """Ingest text files as writing style references into the LanceDB vector store.

    Accepts literal file paths and glob patterns. All matching files are
    collected, deduplicated, and indexed. This is a standalone operation —
    it does not trigger novel generation.
    """
    files = _collect_files(patterns)

    typer.echo(f"Ingesting {len(files)} file(s) as writing style references...")
    for f in files:
        typer.echo(f"  • {f}")

    task = Task(name="Store writing style references").update_init_context(
        text_files=files,
        chunk_size=chunks_size,
        chunk_overlap_ratio=overlap,
        embedding_ndim=ndim,
        embedding_send_to=embedding_send_to,
        store_batch_size=batch_size,
    )

    result = task.delegate_blocking(store_refs_ns)

    if result is not None:
        typer.secho(
            f"✅ Successfully ingested {result} file(s) as writing style references.", fg=typer.colors.GREEN, bold=True
        )
    else:
        _exit_on_error("❌ Failed to store writing style reference texts.")


__all__ = ["app"]
