"""Illustration action for enriching novels with ComfyUI-generated images."""

from pathlib import Path
from typing import Any, ClassVar, Optional

from fabricatio_core import Action, logger
from fabricatio_core.utils import ok

from fabricatio_novel.capabilities.illustration import IllustratedNovelCompose, IllustrationOptions
from fabricatio_novel.models.novel import Novel


class LoadNovelFromPersistent(Action):
    """Load a persisted Novel from disk and inject it into the workflow context.

    Used as the first step of :class:`~fabricatio_novel.workflows.illustration.IllustrateLoadedNovelWorkflow`.
    Reads ``Novel.from_persistent(load_path)`` and writes the resulting object
    into the context under ``output_key`` so downstream ``ctx_override`` actions
    (``IllustrateNovel.novel``, ``DumpNovel.novel``) pick it up.
    """

    load_path: Optional[Path] = None
    """Path to the persisted Novel JSON file."""

    output_key: str = "novel"
    """Context key under which the loaded Novel is stored."""

    ctx_override: ClassVar[bool] = True

    async def _execute(self, *_: Any, **__: Any) -> Novel:
        novel = Novel.from_persistent(ok(self.load_path, "LoadNovelFromPersistent requires `load_path`"))
        logger.info(f"Loaded novel '{novel.title}' from {self.load_path}")
        return novel


class IllustrateNovel(IllustratedNovelCompose, Action):
    """Enrich a novel with LLM-selected and ComfyUI-generated illustrations.

    Runs a two-phase pipeline:
      1. Allocate image budget across chapters (LLM-based weighting).
      2. Per chapter: select paragraphs, generate image prompts, call ComfyUI.

    Injects ``<img>`` tags directly into chapter content.  The companion
    :class:`~fabricatio_novel.actions.novel.DumpNovel` action with
    ``image_root`` set will register those images as EPUB resources.
    """

    novel: Optional[Novel] = None
    """The novel to illustrate.  Populated from workflow context via ``ctx_override``."""

    image_root: Optional[Path] = None
    """Root directory for saving generated images (e.g. ``./illustrations``)."""

    workflow_template: Optional[Path] = None
    """Path to a ComfyUI API-format JSON workflow file.  Defaults to the bundled demo workflow."""

    illustration_budget: int = 5
    """Total number of images to generate across all chapters."""

    illustration_language: str = "en"
    """Language for illustration prompt generation."""

    illustration_guideline: Optional[str] = None
    """Optional extra guideline for paragraph selection."""

    illustration_prompt_guideline: Optional[str] = None
    """Optional extra guideline for image prompt wording."""

    comfyui_timeout: Optional[float] = None
    """Absolute ComfyUI timeout in seconds. ``None`` uses budget-scaled default from config."""

    comfyui_base_url: Optional[str] = None
    """ComfyUI server base URL override. ``None`` uses config default."""

    output_key: str = "novel"
    """Overwrites the ``novel`` key in context with the illustrated version."""

    ctx_override: ClassVar[bool] = True

    async def _execute(self, *_: Any, **cxt: Any) -> Novel:
        novel = ok(self.novel, "IllustrateNovel requires a `novel`")
        image_root = ok(self.image_root, "IllustrateNovel requires `image_root`")

        template_name = self.workflow_template.name if self.workflow_template else "default (bundled)"
        logger.info(
            f"Illustrating novel '{novel.title}' with budget={self.illustration_budget}, template={template_name}"
        )
        result = await self.inject_chapter_images(
            novel,
            image_root,
            IllustrationOptions(
                workflow_template=self.workflow_template,
                budget=self.illustration_budget,
                language=self.illustration_language,
                guideline=self.illustration_guideline,
                prompt_guideline=self.illustration_prompt_guideline,
                comfyui_timeout=self.comfyui_timeout,
                comfyui_base_url=self.comfyui_base_url,
            ),
        )

        logger.info(f"Illustration complete for '{result.title}'.")
        return result
