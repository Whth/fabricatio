"""Fabricatio Novel CLI.

This module provides a command-line interface to generate novels using AI-driven workflows.
It utilizes the Fabricatio Core library and includes functionality for generating novels
with customizable outlines, chapter guidance, language options, styling, and more.
"""

from fabricatio_core.decorators import cfg_on
from fabricatio_core.utils import cfg

cfg(feats=["cli"])

from pathlib import Path
from typing import NoReturn, Optional

import typer
from fabricatio_core import Event, Role, Task

from fabricatio_novel.workflows.novel import DebugNovelWorkflow

app = typer.Typer(help="A CLI tool to generate novels using AI-driven workflows.")

# Register the writer role and workflow
ns = "write"
writer_role = Role.with_bio(name="writer").subscribe(Event.quick_instantiate(ns), DebugNovelWorkflow).dispatch()


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


def _resolve_text_or_file(
    text: str | None,
    file: Path | None,
    *,
    flag: str,
    file_desc: str | None = None,
    default: str | None = "",
    required: bool = False,
) -> str | None:
    """Resolve mutually exclusive text/file argument pair into a single value.

    Args:
        text: Direct text value from CLI option.
        file: Path to text file from CLI option.
        flag: CLI flag name without leading dashes (e.g. "outline", "illust-guideline").
        file_desc: Human-readable description for error messages. Defaults to ``flag``.
        default: Value when neither text nor file is provided. Use ``None`` for optional fields.
        required: If True, error when neither text nor file is provided.

    Returns:
        Resolved and stripped text, or default/None.
    """
    if file_desc is None:
        file_desc = flag
    if text is not None and file is not None:
        _exit_on_error(f"❌ Cannot use both --{flag} and --{flag}-file. Please use only one.")
    if text is None and file is None:
        if required:
            _exit_on_error(f"❌ Either --{flag} or --{flag}-file must be provided.")
        return default
    try:
        if file:
            return file.read_text(encoding="utf-8").strip()
        return text.strip()  # type: ignore[union-attr]
    except (OSError, IOError) as e:
        _exit_on_error(f"❌ Failed to read {file_desc} file: {e}")


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


@app.command(name="wr")
@cfg_on(["lancedb"])
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
    rag_limit: int = typer.Option(
        5,
        "--rag-limit",
        "-rl",
        help="Number of writing style documents to retrieve per prompt.",
        envvar="NOVEL_RAG_LIMIT",
    ),
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
        writing_style_query=rag_query,
        output_path=output_path,
        novel_font_file=font_file,
        cover_image=cover_image,
        novel_language=language,
        chapter_guidance=guidance_content,
        persist_dir=persist_dir,
        writing_style_fetch_config=WritingStyleFetchConfig(limit=rag_limit),
    )

    result = task.delegate_blocking(rag_ns)

    if result:
        typer.secho(f"✅ Novel with RAG styles successfully generated: {result}", fg=typer.colors.GREEN, bold=True)
    else:
        _exit_on_error("❌ Failed to generate novel with RAG.")


@app.command(name="wi")
@cfg_on(["comfyui"])
def write_illustrated_novel(  # noqa: PLR0913
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
        "./novel.epub",
        "--output",
        "-out",
        dir_okay=False,
        help="Output EPUB file path.",
        envvar="NOVEL_OUTPUT_PATH",
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
        "English",
        "--lang",
        "-l",
        help="Language of the novel (e.g., 简体中文, English, jp).",
        envvar="NOVEL_LANGUAGE",
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
    image_root: Path = typer.Option(
        "./illustrations",
        "--image-root",
        "-ir",
        help="Root directory for saving generated illustration images.",
        envvar="NOVEL_IMAGE_ROOT",
    ),
    workflow_template: Optional[Path] = typer.Option(
        None,
        "--workflow-template",
        "-wt",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        help="Path to ComfyUI API-format JSON workflow file (defaults to bundled demo).",
        envvar="NOVEL_WORKFLOW_TEMPLATE",
    ),
    illustration_budget: int = typer.Option(
        5,
        "--budget",
        "-b",
        help="Total number of illustrations to generate across all chapters.",
        envvar="NOVEL_ILLUSTRATION_BUDGET",
    ),
    illustration_language: str = typer.Option(
        "en",
        "--illust-lang",
        help="Language for illustration prompt generation.",
        envvar="NOVEL_ILLUSTRATION_LANGUAGE",
    ),
    illustration_guideline: str = typer.Option(
        None,
        "--illust-guideline",
        "-ig",
        help="Guideline for illustration paragraph selection (e.g. 'focus on action scenes').",
        envvar="NOVEL_ILLUSTRATION_GUIDELINE",
    ),
    illustration_guideline_file: Path = typer.Option(
        None,
        "--illust-guideline-file",
        "-igf",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        help="Path to a text file containing illustration selection guidelines.",
        envvar="NOVEL_ILLUSTRATION_GUIDELINE_FILE",
    ),
    illustration_prompt_guideline: str = typer.Option(
        None,
        "--illust-prompt-guideline",
        "-ipg",
        help="Guideline for image prompt wording (e.g. 'anime style, detailed background').",
        envvar="NOVEL_ILLUSTRATION_PROMPT_GUIDELINE",
    ),
    illustration_prompt_guideline_file: Path = typer.Option(
        None,
        "--illust-prompt-guideline-file",
        "-ipgf",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        help="Path to a text file containing image prompt wording guidelines.",
        envvar="NOVEL_ILLUSTRATION_PROMPT_GUIDELINE_FILE",
    ),
    comfyui_timeout: float = typer.Option(
        None,
        "--comfyui-timeout",
        "-ct",
        help="Absolute ComfyUI timeout in seconds (default: budget * 120s per image from config).",
        envvar="NOVEL_COMFYUI_TIMEOUT",
    ),
) -> None:
    """Generate an illustrated novel with ComfyUI-generated images embedded in the EPUB."""
    from fabricatio_novel.workflows.illustration import DebugIllustratedNovelWorkflow

    illus_ns = "write_illustrated"
    Role.with_bio(name="illustrator").subscribe(
        Event.quick_instantiate(illus_ns), DebugIllustratedNovelWorkflow
    ).dispatch()

    outline_content = _resolve_text_or_file(outline, outline_file, flag="outline", required=True)
    guidance_content = _resolve_text_or_file(chapter_guidance, guidance_file, flag="guidance")

    illust_guideline_content = _resolve_text_or_file(
        illustration_guideline,
        illustration_guideline_file,
        flag="illust-guideline",
        file_desc="illustration guideline",
        default=None,
    )

    illust_prompt_guideline_content = _resolve_text_or_file(
        illustration_prompt_guideline,
        illustration_prompt_guideline_file,
        flag="illust-prompt-guideline",
        file_desc="illustration prompt guideline",
        default=None,
    )

    typer.echo(f"Starting illustrated novel generation: '{outline_content[:30]}...'")

    task = Task(name="Write illustrated novel").update_init_context(
        novel_outline=outline_content,
        output_path=output_path,
        novel_font_file=font_file,
        cover_image=cover_image,
        novel_language=language,
        chapter_guidance=guidance_content,
        persist_dir=persist_dir,
        image_root=image_root,
        workflow_template=workflow_template,
        illustration_budget=illustration_budget,
        illustration_language=illustration_language,
        illustration_guideline=illust_guideline_content,
        illustration_prompt_guideline=illust_prompt_guideline_content,
        comfyui_timeout=comfyui_timeout,
    )

    result = task.delegate_blocking(illus_ns)

    if result:
        typer.secho(f"✅ Illustrated novel successfully generated: {result}", fg=typer.colors.GREEN, bold=True)
    else:
        _exit_on_error("❌ Failed to generate illustrated novel.")


@app.command(name="wri")
@cfg_on(["comfyui", "lancedb"])
def write_rag_illustrated_novel(  # noqa: PLR0913
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
        "./novel.epub",
        "--output",
        "-out",
        dir_okay=False,
        help="Output EPUB file path.",
        envvar="NOVEL_OUTPUT_PATH",
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
        "English",
        "--lang",
        "-l",
        help="Language of the novel (e.g., 简体中文, English, jp).",
        envvar="NOVEL_LANGUAGE",
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
    rag_limit: int = typer.Option(
        5,
        "--rag-limit",
        "-rl",
        help="Number of writing style documents to retrieve per prompt.",
        envvar="NOVEL_RAG_LIMIT",
    ),
    image_root: Path = typer.Option(
        "./illustrations",
        "--image-root",
        "-ir",
        help="Root directory for saving generated illustration images.",
        envvar="NOVEL_IMAGE_ROOT",
    ),
    workflow_template: Optional[Path] = typer.Option(
        None,
        "--workflow-template",
        "-wt",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        help="Path to ComfyUI API-format JSON workflow file (defaults to bundled demo).",
        envvar="NOVEL_WORKFLOW_TEMPLATE",
    ),
    illustration_budget: int = typer.Option(
        5,
        "--budget",
        "-b",
        help="Total number of illustrations to generate across all chapters.",
        envvar="NOVEL_ILLUSTRATION_BUDGET",
    ),
    illustration_language: str = typer.Option(
        "en",
        "--illust-lang",
        help="Language for illustration prompt generation.",
        envvar="NOVEL_ILLUSTRATION_LANGUAGE",
    ),
    illustration_guideline: str = typer.Option(
        None,
        "--illust-guideline",
        "-ig",
        help="Guideline for illustration paragraph selection (e.g. 'focus on action scenes').",
        envvar="NOVEL_ILLUSTRATION_GUIDELINE",
    ),
    illustration_guideline_file: Path = typer.Option(
        None,
        "--illust-guideline-file",
        "-igf",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        help="Path to a text file containing illustration selection guidelines.",
        envvar="NOVEL_ILLUSTRATION_GUIDELINE_FILE",
    ),
    illustration_prompt_guideline: str = typer.Option(
        None,
        "--illust-prompt-guideline",
        "-ipg",
        help="Guideline for image prompt wording (e.g. 'anime style, detailed background').",
        envvar="NOVEL_ILLUSTRATION_PROMPT_GUIDELINE",
    ),
    illustration_prompt_guideline_file: Path = typer.Option(
        None,
        "--illust-prompt-guideline-file",
        "-ipgf",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        help="Path to a text file containing image prompt wording guidelines.",
        envvar="NOVEL_ILLUSTRATION_PROMPT_GUIDELINE_FILE",
    ),
    comfyui_timeout: float = typer.Option(
        None,
        "--comfyui-timeout",
        "-ct",
        help="Absolute ComfyUI timeout in seconds (default: budget * 120s per image from config).",
        envvar="NOVEL_COMFYUI_TIMEOUT",
    ),
) -> None:
    """Generate a RAG-augmented novel with ComfyUI illustrations embedded in the EPUB."""
    from fabricatio_novel.models.novel_rag import WritingStyleFetchConfig
    from fabricatio_novel.workflows.illustration import DebugRAGIllustratedNovelWorkflow

    rag_illus_ns = "write_rag_illustrated"
    Role.with_bio(name="rag_illustrator").subscribe(
        Event.quick_instantiate(rag_illus_ns), DebugRAGIllustratedNovelWorkflow
    ).dispatch()

    outline_content = _resolve_text_or_file(outline, outline_file, flag="outline", required=True)
    guidance_content = _resolve_text_or_file(chapter_guidance, guidance_file, flag="guidance")

    illust_guideline_content = _resolve_text_or_file(
        illustration_guideline,
        illustration_guideline_file,
        flag="illust-guideline",
        file_desc="illustration guideline",
        default=None,
    )

    illust_prompt_guideline_content = _resolve_text_or_file(
        illustration_prompt_guideline,
        illustration_prompt_guideline_file,
        flag="illust-prompt-guideline",
        file_desc="illustration prompt guideline",
        default=None,
    )

    typer.echo(f"Starting RAG + illustrated novel generation: '{outline_content[:30]}...'")
    typer.echo(f"Writing style query: '{rag_query}'")

    task = Task(name="Write RAG illustrated novel").update_init_context(
        novel_outline=outline_content,
        writing_style_query=rag_query,
        output_path=output_path,
        novel_font_file=font_file,
        cover_image=cover_image,
        novel_language=language,
        chapter_guidance=guidance_content,
        persist_dir=persist_dir,
        writing_style_fetch_config=WritingStyleFetchConfig(limit=rag_limit),
        image_root=image_root,
        workflow_template=workflow_template,
        illustration_budget=illustration_budget,
        illustration_language=illustration_language,
        illustration_guideline=illust_guideline_content,
        illustration_prompt_guideline=illust_prompt_guideline_content,
        comfyui_timeout=comfyui_timeout,
    )

    result = task.delegate_blocking(rag_illus_ns)

    if result:
        typer.secho(f"✅ RAG illustrated novel successfully generated: {result}", fg=typer.colors.GREEN, bold=True)
    else:
        _exit_on_error("❌ Failed to generate RAG illustrated novel.")


@app.command()
def info() -> None:
    """Show information about this CLI tool."""
    typer.echo("📘 Fabricatio Novel Generator CLI")
    typer.echo("Generate AI-assisted novels in various languages with customizable styling.")
    typer.echo("Powered by Fabricatio Core & DebugNovelWorkflow.")


@app.command(name="store-refs")
@cfg_on(["lancedb"])
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
    parallel_size: int = typer.Option(
        10, "--parallel-size", "-ps", help="Number of worker sending embedding reqs.", envvar="NOVEL_PARALLEL_SIZE"
    ),
) -> None:
    """Ingest text files as writing style references into the LanceDB vector store.

    Accepts literal file paths and glob patterns. All matching files are
    collected, deduplicated, and indexed. This is a standalone operation —
    it does not trigger novel generation.
    """
    from fabricatio_lancedb.capabilities.lancedb import LancedbAddRAGConfig

    from fabricatio_novel.workflows.novel_rag import StoreWritingStyleTextsWorkflow

    store_refs_ns = "store_refs"
    Role.with_bio(name="ref_ingester").subscribe(
        Event.quick_instantiate(store_refs_ns), StoreWritingStyleTextsWorkflow
    ).dispatch()

    files = _collect_files(patterns)

    typer.echo(f"Ingesting {len(files)} file(s) as writing style references...")
    for f in files:
        typer.echo(f"  • {f}")

    conf = LancedbAddRAGConfig.default()
    conf.embedding_batch_size = batch_size
    conf.embedding_parallel_size = parallel_size
    task = Task(name="Store writing style references").update_init_context(
        text_files=files,
        chunk_size=chunks_size,
        chunk_overlap_ratio=overlap,
        store_config=conf,
        embedding_ndim=ndim,
        embedding_send_to=embedding_send_to,
    )

    result = task.delegate_blocking(store_refs_ns)

    if result is not None:
        typer.secho(
            f"✅ Successfully ingested {result} file(s) as writing style references.", fg=typer.colors.GREEN, bold=True
        )
    else:
        _exit_on_error("❌ Failed to store writing style reference texts.")


__all__ = ["app"]
