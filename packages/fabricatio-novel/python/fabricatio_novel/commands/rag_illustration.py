"""RAG-augmented illustrated-novel CLI commands (comfyui + lancedb gated).

Registers onto the shared ``app`` from :mod:`fabricatio_novel.cli`:

- ``wri``  — :func:`write_rag_illustrated_novel`
- ``wrmi`` — :func:`write_rag_mental_illustrated_novel`
"""

from pathlib import Path
from typing import Optional

import typer
from fabricatio_core import Event, Role, Task
from fabricatio_core.decorators import cfg_on

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
from fabricatio_novel.commands.illustration import (
    _COMFYUI_BASE_URL,
    _COMFYUI_TIMEOUT,
    _ILLUST_BUDGET,
    _ILLUST_GUIDELINE,
    _ILLUST_GUIDELINE_FILE,
    _ILLUST_LANG,
    _ILLUST_PROMPT_GUIDELINE,
    _ILLUST_PROMPT_GUIDELINE_FILE,
    _IMAGE_ROOT,
    _WORKFLOW_TEMPLATE,
)
from fabricatio_novel.commands.rag import (
    _RAG_LIMIT,
    _RAG_QUERY,
    _REFINE_TEMPLATE,
    _REFINED_COUNT,
    _USE_REFINE,
    _USE_RERANKER,
)


@app.command(name="wri")
@cfg_on(["comfyui", "lancedb"])
def write_rag_illustrated_novel(  # noqa: PLR0913
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
    use_reranker: bool = _USE_RERANKER,
    use_refined_query: bool = _USE_REFINE,
    refined_query_count: int = _REFINED_COUNT,
    refine_query_template: str = _REFINE_TEMPLATE,
    image_root: Path = _IMAGE_ROOT,
    workflow_template: Optional[Path] = _WORKFLOW_TEMPLATE,
    illustration_budget: int = _ILLUST_BUDGET,
    illustration_language: str = _ILLUST_LANG,
    illustration_guideline: str = _ILLUST_GUIDELINE,
    illustration_guideline_file: Path = _ILLUST_GUIDELINE_FILE,
    illustration_prompt_guideline: str = _ILLUST_PROMPT_GUIDELINE,
    illustration_prompt_guideline_file: Path = _ILLUST_PROMPT_GUIDELINE_FILE,
    comfyui_timeout: float = _COMFYUI_TIMEOUT,
    comfyui_base_url: str = _COMFYUI_BASE_URL,
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
    if use_refined_query:
        typer.echo(f"Query refinement enabled: {refined_query_count} variant(s) via '{refine_query_template}'")

    task = Task(name="Write RAG illustrated novel").update_init_context(
        novel_outline=outline_content,
        writing_style_query=rag_query,
        output_path=output_path,
        novel_font_file=font_file,
        cover_image=cover_image,
        novel_language=language,
        chapter_guidance=guidance_content,
        persist_dir=persist_dir,
        image_root=image_root,
        writing_style_fetch_config=WritingStyleFetchConfig(
            limit=rag_limit,
            use_refined_query=use_refined_query,
            refined_query_count=refined_query_count,
            refine_query_template=refine_query_template,
        ),
        use_reranker=use_reranker,
        workflow_template=workflow_template,
        illustration_budget=illustration_budget,
        illustration_language=illustration_language,
        illustration_guideline=illust_guideline_content,
        illustration_prompt_guideline=illust_prompt_guideline_content,
        comfyui_timeout=comfyui_timeout,
        comfyui_base_url=comfyui_base_url,
    )

    result = task.delegate_blocking(rag_illus_ns)

    if result:
        typer.secho(f"✅ RAG illustrated novel successfully generated: {result}", fg=typer.colors.GREEN, bold=True)
    else:
        _exit_on_error("❌ Failed to generate RAG illustrated novel.")


@app.command(name="wrmi")
@cfg_on(["comfyui", "lancedb"])
def write_rag_mental_illustrated_novel(  # noqa: PLR0913
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
    use_reranker: bool = _USE_RERANKER,
    use_refined_query: bool = _USE_REFINE,
    refined_query_count: int = _REFINED_COUNT,
    refine_query_template: str = _REFINE_TEMPLATE,
    image_root: Path = _IMAGE_ROOT,
    workflow_template: Optional[Path] = _WORKFLOW_TEMPLATE,
    illustration_budget: int = _ILLUST_BUDGET,
    illustration_language: str = _ILLUST_LANG,
    illustration_guideline: str = _ILLUST_GUIDELINE,
    illustration_guideline_file: Path = _ILLUST_GUIDELINE_FILE,
    illustration_prompt_guideline: str = _ILLUST_PROMPT_GUIDELINE,
    illustration_prompt_guideline_file: Path = _ILLUST_PROMPT_GUIDELINE_FILE,
    comfyui_timeout: float = _COMFYUI_TIMEOUT,
    comfyui_base_url: str = _COMFYUI_BASE_URL,
) -> None:
    """Generate a RAG-augmented novel with mental state tracking + ComfyUI illustrations."""
    from fabricatio_novel.models.novel_rag import WritingStyleFetchConfig
    from fabricatio_novel.workflows.novel_mental import DebugMentalRAGIllustratedNovelWorkflow

    rag_mental_illus_ns = "write_rag_mental_illustrated"
    Role.with_bio(name="rag_mental_illustrator").subscribe(
        Event.quick_instantiate(rag_mental_illus_ns), DebugMentalRAGIllustratedNovelWorkflow
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

    typer.echo(f"Starting RAG+Mental+Illustrated novel generation: '{outline_content[:30]}...'")
    typer.echo(f"Writing style query: '{rag_query}'")
    if use_refined_query:
        typer.echo(f"Query refinement enabled: {refined_query_count} variant(s) via '{refine_query_template}'")

    task = Task(name="Write RAG mental illustrated novel").update_init_context(
        novel_outline=outline_content,
        writing_style_query=rag_query,
        output_path=output_path,
        novel_font_file=font_file,
        cover_image=cover_image,
        novel_language=language,
        chapter_guidance=guidance_content,
        persist_dir=persist_dir,
        image_root=image_root,
        writing_style_fetch_config=WritingStyleFetchConfig(
            limit=rag_limit,
            use_refined_query=use_refined_query,
            refined_query_count=refined_query_count,
            refine_query_template=refine_query_template,
        ),
        use_reranker=use_reranker,
        workflow_template=workflow_template,
        illustration_budget=illustration_budget,
        illustration_language=illustration_language,
        illustration_guideline=illust_guideline_content,
        illustration_prompt_guideline=illust_prompt_guideline_content,
        comfyui_timeout=comfyui_timeout,
        comfyui_base_url=comfyui_base_url,
    )

    result = task.delegate_blocking(rag_mental_illus_ns)

    if result:
        typer.secho(
            f"✅ RAG+Mental+Illustrated novel successfully generated: {result}",
            fg=typer.colors.GREEN,
            bold=True,
        )
    else:
        _exit_on_error("❌ Failed to generate RAG+Mental+Illustrated novel.")
