"""IllustratedNovelCompose — NovelCompose subclass for image-enriched novel generation.

Two-phase pipeline using UseLLM.amapping_kv with typed key/value:
    Phase 1: allocate image budget across chapters → {chapter_index: image_count} (Int→Float)
    Phase 2: per chapter, select paragraphs + generate prompts → {paragraph_index: image_prompt} (Int→String)

Then: ComfyUI generates images, <img> tags injected directly into raw text.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Optional, Unpack

from fabricatio_comfyui.capabilities.comfyui import Comfyui
from fabricatio_comfyui.models.workflow import Workflow
from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.kwargs_types import ValidateKwargs

from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.novel import Novel
from fabricatio_novel.rust import split_paragraphs

if TYPE_CHECKING:
    from fabricatio_novel.models.novel import Chapter


def _inject_images(paras: list[str], picks: dict[int, str], image_dir: str) -> list[str]:
    """Insert <img> tags after selected paragraphs. Returns modified list."""
    result = list(paras)
    for idx, prompt in picks.items():
        if 0 <= idx < len(result):
            epub_path = f"{image_dir}/scene_{idx}.png"
            result[idx] += f'\n<img src="{epub_path}" alt="{prompt[:80]}"/>'
    return result


class IllustratedNovelCompose(NovelCompose, Comfyui):
    """NovelCompose subclass that enriches chapters with LLM-selected illustrations.

    Usage:
        novel = await self.compose_novel(outline, language)
        novel = await self.inject_chapter_images(
            novel, image_root, workflow_template,
            budget=5,
            guideline="High tension moments.",
            prompt_guideline="Cinematic lighting, painterly style.",
        )
        DumpNovel(novel=novel, output_path=..., image_root=image_root).execute()
    """

    async def inject_chapter_images(
        self,
        novel: Novel,
        image_root: Path,
        workflow_template: Path,
        budget: int = 5,
        language: str = "en",
        guideline: Optional[str] = None,
        prompt_guideline: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[None]],
    ) -> Novel:
        """Two-phase image injection pipeline."""
        if budget <= 0:
            return novel

        # Render guidelines from templates
        rendered_guideline = (
            TEMPLATE_MANAGER.render_template(
                novel_config.illustration_selection_guideline_template,
                {"guideline": guideline, "language": language},
            )
            if guideline
            else None
        )
        rendered_prompt_guideline = (
            TEMPLATE_MANAGER.render_template(
                novel_config.image_prompt_guideline_template,
                {"prompt_guideline": prompt_guideline, "language": language},
            )
            if prompt_guideline
            else None
        )

        # Phase 1: allocate budget across chapters
        budget_map = await self._allocate_budget(
            novel,
            budget,
            language,
            rendered_guideline,
            **kwargs,
        )
        if not budget_map:
            return novel

        # Phase 2: per-chapter illustration
        base_wf = Workflow.from_file(workflow_template)
        for chapter in novel.chapters:
            chapter_budget = budget_map.get(chapter.chapter_index, 0)
            if chapter_budget > 0:
                await self._illustrate_chapter(
                    chapter,
                    novel,
                    image_root,
                    base_wf,
                    chapter_budget,
                    language,
                    rendered_guideline,
                    rendered_prompt_guideline,
                    **kwargs,
                )

        return novel

    # TODO typing of kwargs
    async def _allocate_budget(
        self,
        novel: Novel,
        budget: int,
        language: str,
        guideline: Optional[str],
        **kwargs,
    ) -> dict[int, int]:
        """Phase 1: LLM assigns relative weights per chapter, code computes actual counts."""
        rendered = TEMPLATE_MANAGER.render_template(
            novel_config.allocate_image_budget_template,
            {
                "novel_title": novel.title,
                "chapters": [
                    {
                        "index": ch.chapter_index,
                        "title": ch.title,
                        "paragraph_count": len(split_paragraphs(ch.content)),
                    }
                    for ch in novel.chapters
                ],
                "guideline": guideline,
                "language": language,
            },
        )
        weights: Optional[dict[int, float]] = await self.amapping_kv(
            rendered,
            key_type=int,
            value_type=float,
            k=len(novel.chapters),
            **kwargs,
        )
        if not weights:
            return {}

        # Clamp negative weights to 0
        numeric = {k: max(v, 0.0) for k, v in weights.items()}
        total = sum(numeric.values())
        if total <= 0:
            return {}

        # Proportional allocation with largest-remainder rounding
        raw = {k: budget * v / total for k, v in numeric.items()}
        counts = {k: int(v) for k, v in raw.items()}
        remainder = budget - sum(counts.values())
        # Distribute remainder to chapters with largest fractional parts
        for k, _ in sorted(raw.items(), key=lambda kv: kv[1] - int(kv[1]), reverse=True):
            if remainder <= 0:
                break
            counts[k] += 1
            remainder -= 1

        logger.info(f"Image budget allocation (weights→counts): {weights} → {counts}")
        return counts

    async def _illustrate_chapter(
        self,
        chapter: "Chapter",
        novel: Novel,
        image_root: Path,
        base_wf: Workflow,
        chapter_budget: int,
        language: str,
        guideline: Optional[str],
        prompt_guideline: Optional[str],
        **kwargs: Unpack[ValidateKwargs[None]],
    ) -> None:
        """Phase 2: LLM selects paragraphs + generates prompts via amapping_kv."""
        paras = split_paragraphs(chapter.content)
        if not paras:
            return

        rendered = TEMPLATE_MANAGER.render_template(
            novel_config.select_illustrations_template,
            {
                "chapter_title": chapter.title,
                "chapter_index": chapter.chapter_index,
                "novel_title": novel.title,
                "paragraphs": paras,
                "budget": chapter_budget,
                "guideline": guideline,
                "prompt_guideline": prompt_guideline,
                "language": language,
            },
        )
        picks = await self.amapping_kv(
            rendered,
            key_type=int,
            value_type=str,
            k=chapter_budget,
        )
        if not picks:
            return

        # Generate images via ComfyUI
        image_dir = f"images/ch{chapter.chapter_index}"
        valid_picks: dict[int, str] = {}

        for idx, prompt in picks.items():
            if not (0 <= idx < len(paras)):
                logger.warn(f"Invalid paragraph index {idx} (max {len(paras) - 1})")
                continue

            save_dir = image_root / image_dir
            save_dir.mkdir(parents=True, exist_ok=True)

            wf = Workflow.from_api(base_wf.to_api())
            wf.set_positive_prompt(prompt)

            result = await self.comfyui_generate(wf, download_dir=str(save_dir))
            if not result.all_images:
                logger.warn(f"Image generation failed for paragraph {idx}")
                continue

            src = save_dir / result.all_images[0].filename
            target = save_dir / f"scene_{idx}.png"
            if src != target:
                src.rename(target)

            valid_picks[idx] = prompt
            logger.info(f"Illustrated paragraph {idx} in chapter {chapter.chapter_index}")

        # Inject <img> tags into raw text
        if valid_picks:
            chapter.content = "\n\n".join(_inject_images(paras, valid_picks, image_dir))
