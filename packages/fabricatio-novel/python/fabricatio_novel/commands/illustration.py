"""Illustrated-novel CLI commands (comfyui-gated).

Registers onto the shared ``app`` from :mod:`fabricatio_novel.cli`:

- ``wi``  — :func:`write_illustrated_novel`
- ``wmi`` — :func:`write_mental_illustrated_novel` (mental tracking + illustrations)
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

_IMAGE_ROOT: typer.Option = typer.Option(
    "./illustrations",
    "--image-root",
    "-ir",
    help="Root directory for saving generated illustration images.",
    envvar="NOVEL_IMAGE_ROOT",
)
_WORKFLOW_TEMPLATE: typer.Option = typer.Option(
    None,
    "--workflow-template",
    "-wt",
    exists=True,
    file_okay=True,
    dir_okay=False,
    resolve_path=True,
    help="Path to ComfyUI API-format JSON workflow file (defaults to bundled demo).",
    envvar="NOVEL_WORKFLOW_TEMPLATE",
)
_ILLUST_BUDGET: typer.Option = typer.Option(
    5,
    "--budget",
    "-b",
    help="Total number of illustrations to generate across all chapters.",
    envvar="NOVEL_ILLUSTRATION_BUDGET",
)
_ILLUST_LANG: typer.Option = typer.Option(
    "en",
    "--illust-lang",
    help="Language for illustration prompt generation.",
    envvar="NOVEL_ILLUSTRATION_LANGUAGE",
)
_ILLUST_GUIDELINE: typer.Option = typer.Option(
    None,
    "--illust-guideline",
    "-ig",
    help="Guideline for illustration paragraph selection (e.g. 'focus on action scenes').",
    envvar="NOVEL_ILLUSTRATION_GUIDELINE",
)
_ILLUST_GUIDELINE_FILE: typer.Option = typer.Option(
    None,
    "--illust-guideline-file",
    "-igf",
    exists=True,
    file_okay=True,
    dir_okay=False,
    resolve_path=True,
    help="Path to a text file containing illustration selection guidelines.",
    envvar="NOVEL_ILLUSTRATION_GUIDELINE_FILE",
)
_ILLUST_PROMPT_GUIDELINE: typer.Option = typer.Option(
    None,
    "--illust-prompt-guideline",
    "-ipg",
    help="Guideline for image prompt wording (e.g. 'anime style, detailed background').",
    envvar="NOVEL_ILLUSTRATION_PROMPT_GUIDELINE",
)
_ILLUST_PROMPT_GUIDELINE_FILE: typer.Option = typer.Option(
    None,
    "--illust-prompt-guideline-file",
    "-ipgf",
    exists=True,
    file_okay=True,
    dir_okay=False,
    resolve_path=True,
    help="Path to a text file containing image prompt wording guidelines.",
    envvar="NOVEL_ILLUSTRATION_PROMPT_GUIDELINE_FILE",
)
_COMFYUI_TIMEOUT: typer.Option = typer.Option(
    None,
    "--comfyui-timeout",
    "-ct",
    help="Absolute ComfyUI timeout in seconds (default: budget * 120s per image from config).",
    envvar="NOVEL_COMFYUI_TIMEOUT",
)
_COMFYUI_BASE_URL: typer.Option = typer.Option(
    None,
    "--comfyui-base-url",
    "-cb",
    help="ComfyUI server base URL (default: http://localhost:8188).",
    envvar="NOVEL_COMFYUI_BASE_URL",
)


@app.command(name="wi")
@cfg_on(["comfyui"])
def write_illustrated_novel(  # noqa: PLR0913
    outline: str = OUTLINE,
    outline_file: Path = OUTLINE_FILE,
    output_path: Path = OUTPUT_PATH,
    font_file: Path = FONT_FILE,
    cover_image: Path = COVER_IMAGE,
    language: str = LANGUAGE,
    chapter_guidance: str = CHAPTER_GUIDANCE,
    guidance_file: Path = GUIDANCE_FILE,
    persist_dir: Path = PERSIST_DIR,
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
        comfyui_base_url=comfyui_base_url,
    )

    result = task.delegate_blocking(illus_ns)

    if result:
        typer.secho(f"✅ Illustrated novel successfully generated: {result}", fg=typer.colors.GREEN, bold=True)
    else:
        _exit_on_error("❌ Failed to generate illustrated novel.")


@app.command(name="wmi")
@cfg_on(["comfyui"])
def write_mental_illustrated_novel(  # noqa: PLR0913
    outline: str = OUTLINE,
    outline_file: Path = OUTLINE_FILE,
    output_path: Path = OUTPUT_PATH,
    font_file: Path = FONT_FILE,
    cover_image: Path = COVER_IMAGE,
    language: str = LANGUAGE,
    chapter_guidance: str = CHAPTER_GUIDANCE,
    guidance_file: Path = GUIDANCE_FILE,
    persist_dir: Path = PERSIST_DIR,
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
    """Generate a novel with mental state tracking + ComfyUI illustrations."""
    from fabricatio_novel.workflows.novel_mental import DebugMentalIllustratedNovelWorkflow

    mental_illus_ns = "write_mental_illustrated"
    Role.with_bio(name="mental_illustrator").subscribe(
        Event.quick_instantiate(mental_illus_ns), DebugMentalIllustratedNovelWorkflow
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

    typer.echo(f"Starting Mental+Illustrated novel generation: '{outline_content[:30]}...'")

    task = Task(name="Write mental illustrated novel").update_init_context(
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
        comfyui_base_url=comfyui_base_url,
    )

    result = task.delegate_blocking(mental_illus_ns)

    if result:
        typer.secho(f"✅ Mental illustrated novel successfully generated: {result}", fg=typer.colors.GREEN, bold=True)
    else:
        _exit_on_error("❌ Failed to generate mental illustrated novel.")
