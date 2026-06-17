"""IllustratedNovelCompose — NovelCompose subclass for image-enriched novel generation.

Three-phase pipeline:
    Phase 1: allocate image budget across chapters → {chapter_index: image_count}
    Phase 2: per chapter, select paragraphs to illustrate → [paragraph_index, ...]
    Phase 3: per selected paragraph, generate image prompt with character context → image_prompt string

Then: ComfyUI generates images, <img> tags injected directly into raw text.
"""

from asyncio import gather
from dataclasses import dataclass, field
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


@dataclass
class IllustrationContext:
    """Shared state for the illustration pipeline, constant across all chapters."""

    novel: Novel
    image_root: Path
    base_wf: Workflow
    language: str
    guideline: Optional[str]
    prompt_guideline: Optional[str]
    base_looks: dict[str, str]
    comfyui_timeout_per_image: float
    """Per-image ComfyUI timeout in seconds. Multiply by chapter budget for total timeout."""


def _inject_images(paras: list[str], picks: dict[int, str], image_dir: Path) -> list[str]:
    """Insert <img> tags after selected paragraphs. Returns modified list."""
    result = list(paras)
    for idx, prompt in picks.items():
        if 0 <= idx < len(result):
            epub_path = (image_dir / f"scene_{idx}.png").as_posix()
            result[idx] += f'\n<img src="{epub_path}" alt="{prompt[:80]}"/>'
    return result


@dataclass
class _ChapterIllustrator:
    """Working state for illustrating a single chapter."""

    ctx: IllustrationContext
    chapter: "Chapter"
    paras: list[str]
    image_dir: Path
    save_dir: Path
    character_looks: list[dict[str, str]]
    valid_picks: dict[int, str] = field(default_factory=dict)

    def check_existing(self, valid_indices: list[int]) -> list[int]:
        """Mark cached images in valid_picks; return indices needing generation."""
        needs_gen: list[int] = []
        for idx in valid_indices:
            if (self.save_dir / f"scene_{idx}.png").is_file():
                self.valid_picks[idx] = ""
                logger.info(
                    f"Chapter {self.chapter.chapter_index} para[{idx}]: scene image exists, skipping generation"
                )
            else:
                needs_gen.append(idx)
        return needs_gen

    def render_prompts(self, needs_gen: list[int]) -> list[str]:
        """Build image prompt templates for paragraphs needing generation."""
        rendered: list[str] = []
        for idx in needs_gen:
            ctx_before = [{"offset": idx - i, "text": self.paras[i]} for i in range(max(0, idx - 2), idx)]
            ctx_after = [
                {"offset": i - idx, "text": self.paras[i]} for i in range(idx + 1, min(len(self.paras), idx + 3))
            ]
            rendered.append(
                TEMPLATE_MANAGER.render_template(
                    novel_config.generate_image_prompt_template,
                    {
                        "chapter_title": self.chapter.title,
                        "chapter_index": self.chapter.chapter_index,
                        "novel_title": self.ctx.novel.title,
                        "novel_synopsis": self.ctx.novel.synopsis,
                        "character_looks": self.character_looks,
                        "paragraph_index": idx,
                        "paragraph": self.paras[idx],
                        "before_paragraphs": ctx_before,
                        "after_paragraphs": ctx_after,
                        "prompt_guideline": self.ctx.prompt_guideline,
                        "language": self.ctx.language,
                    },
                )
            )
            logger.debug(f"Chapter {self.chapter.chapter_index} para[{idx}] stage2 prompt:\n{rendered[-1]}")
        return rendered

    def collect_workflows(
        self, needs_gen: list[int], image_prompts: list[str]
    ) -> tuple[list[Workflow], list[int], list[str]]:
        """Filter empty prompts and build ComfyUI workflows."""
        workflows: list[Workflow] = []
        gen_indices: list[int] = []
        filtered_prompts: list[str] = []
        for idx, prompt in zip(needs_gen, image_prompts, strict=True):
            logger.debug(f"Chapter {self.chapter.chapter_index} para[{idx}] aask raw response: {prompt!r}")
            if not prompt:
                logger.warn(f"Chapter {self.chapter.chapter_index} para[{idx}]: LLM returned no image prompt")
                continue
            logger.debug(f"Chapter {self.chapter.chapter_index} para[{idx}] image prompt: {prompt}")
            wf = Workflow.from_api(self.ctx.base_wf.to_api())
            wf.set_positive_prompt(prompt)
            workflows.append(wf)
            gen_indices.append(idx)
            filtered_prompts.append(prompt)
        return workflows, gen_indices, filtered_prompts

    def process_results(self, gen_indices: list[int], filtered_prompts: list[str], results: list) -> None:
        """Rename generated images and track successful picks."""
        for idx, prompt, result in zip(gen_indices, filtered_prompts, results, strict=True):
            if not result or not result.all_images:
                logger.warn(f"Image generation failed for paragraph {idx}")
                continue
            logger.debug(
                f"Chapter {self.chapter.chapter_index} para[{idx}] ComfyUI generated: {result.all_images[0].filename}"
            )
            src = self.save_dir / result.all_images[0].filename
            target = self.save_dir / f"scene_{idx}.png"
            if src != target:
                src.rename(target)
            self.valid_picks[idx] = prompt
            logger.info(f"Illustrated paragraph {idx} in chapter {self.chapter.chapter_index}")


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

    async def _generate_base_looks(self, novel: Novel, language: str) -> dict[str, str]:
        """Generate base physical appearance for each character (body + hair + eyes, no clothing)."""
        if not novel.characters:
            return {}

        prompts = [
            TEMPLATE_MANAGER.render_template(
                novel_config.character_base_look_template,
                {"name": char.name, "look": char.look, "language": language},
            )
            for char in novel.characters
        ]
        results = await self.aask(prompts)

        base_looks: dict[str, str] = {}
        for char, result in zip(novel.characters, results, strict=True):
            if result:
                base_looks[char.name] = result.strip()
                logger.debug(f"Base look for {char.name}: {result.strip()}")
            else:
                logger.warn(f"Failed to generate base look for {char.name}, using full look as fallback")
                base_looks[char.name] = char.look
        return base_looks

    async def inject_chapter_images(
        self,
        novel: Novel,
        image_root: Path,
        workflow_template: Optional[Path] = None,
        budget: int = 5,
        language: str = "en",
        guideline: Optional[str] = None,
        prompt_guideline: Optional[str] = None,
        comfyui_timeout: Optional[float] = None,
        **kwargs: Unpack[ValidateKwargs[None]],
    ) -> Novel:
        """Two-phase image injection pipeline."""
        if budget <= 0:
            logger.info("Illustration budget is 0, skipping.")
            return novel

        logger.info(f"Phase 1: Allocating budget={budget} across {len(novel.chapters)} chapters")

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

        # Generate base physical appearances for character consistency
        base_looks = await self._generate_base_looks(novel, language)

        # Phase 1: allocate budget across chapters
        budget_map = await self._allocate_budget(
            novel,
            budget,
            language,
            rendered_guideline,
            **kwargs,
        )
        if not budget_map:
            logger.warn("Budget allocation returned empty — no chapters will be illustrated. Check LLM response.")
            return novel

        # Phase 2: per-chapter illustration (parallel)
        base_wf = Workflow.from_file(workflow_template) if workflow_template else Workflow.default()
        per_image = comfyui_timeout / budget if comfyui_timeout is not None else novel_config.comfyui_timeout_per_image
        ctx = IllustrationContext(
            novel=novel,
            image_root=image_root,
            base_wf=base_wf,
            language=language,
            guideline=rendered_guideline,
            prompt_guideline=rendered_prompt_guideline,
            base_looks=base_looks,
            comfyui_timeout_per_image=per_image,
        )
        chapter_tasks = [
            self._illustrate_chapter(ctx, chapter, budget_map.get(chapter.chapter_index, 0), **kwargs)
            for chapter in novel.chapters
            if budget_map.get(chapter.chapter_index, 0) > 0
        ]
        if chapter_tasks:
            await gather(*chapter_tasks)

        return novel

    async def _allocate_budget(
        self,
        novel: Novel,
        budget: int,
        language: str,
        guideline: Optional[str],
        **kwargs: Unpack[ValidateKwargs[None]],
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
            logger.warn(f"Budget allocation LLM returned empty/None weights for '{novel.title}'")
            return {}

        # Clamp negative weights to 0
        numeric = {k: max(v, 0.0) for k, v in weights.items()}
        total = sum(numeric.values())
        if total <= 0:
            logger.warn(f"Budget allocation: all weights are zero after clamping: {weights}")
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

    async def _select_paragraphs(
        self,
        ctx: IllustrationContext,
        chapter: "Chapter",
        paras: list[str],
        chapter_budget: int,
        **kwargs: Unpack[ValidateKwargs[None]],
    ) -> Optional[list[int]]:
        """Stage 1: LLM selects paragraphs to illustrate. Returns validated sorted indices or None."""
        select_rendered = TEMPLATE_MANAGER.render_template(
            novel_config.select_paragraphs_template,
            {
                "chapter_title": chapter.title,
                "chapter_index": chapter.chapter_index,
                "novel_title": ctx.novel.title,
                "novel_synopsis": ctx.novel.synopsis,
                "paragraphs": paras,
                "budget": chapter_budget,
                "guideline": ctx.guideline,
                "language": ctx.language,
            },
        )
        logger.debug(f"Chapter {chapter.chapter_index} stage1 prompt:\n{select_rendered}")

        selected_indices: Optional[list[int]] = await self.alist_v(
            select_rendered, value_type=int, k=chapter_budget, **kwargs
        )
        if not selected_indices:
            logger.warn(f"Chapter {chapter.chapter_index}: LLM selected no paragraphs for illustration")
            return None

        valid_indices = sorted({i for i in selected_indices if 0 <= i < len(paras)})
        logger.info(f"Chapter {chapter.chapter_index}: LLM selected paragraphs: {valid_indices}")
        return valid_indices

    async def _illustrate_chapter(
        self,
        ctx: IllustrationContext,
        chapter: "Chapter",
        chapter_budget: int,
        **kwargs: Unpack[ValidateKwargs[None]],
    ) -> None:
        """Two-stage illustration: 1) select paragraphs, 2) generate image prompt per paragraph."""
        paras = split_paragraphs(chapter.content)
        if not paras:
            logger.warn(f"Chapter {chapter.chapter_index} '{chapter.title}': no paragraphs found, skipping")
            return

        logger.info(f"Chapter {chapter.chapter_index}: {len(paras)} paragraphs, budget={chapter_budget}")

        # Stage 1: Select which paragraphs to illustrate
        valid_indices = await self._select_paragraphs(ctx, chapter, paras, chapter_budget, **kwargs)
        if not valid_indices:
            return

        # Build character appearance reference using base looks for consistency
        character_looks = (
            [{"name": c.name, "look": ctx.base_looks.get(c.name, c.look)} for c in ctx.novel.characters]
            if ctx.novel.characters
            else []
        )

        image_dir = Path(f"images/ch{chapter.chapter_index}")
        save_dir = ctx.image_root / image_dir
        save_dir.mkdir(parents=True, exist_ok=True)

        work = _ChapterIllustrator(ctx, chapter, paras, image_dir, save_dir, character_looks)

        # Check existing images (resume support)
        needs_gen = work.check_existing(valid_indices)
        if not needs_gen:
            logger.info(f"Chapter {chapter.chapter_index}: all {len(work.valid_picks)} images already exist on disk")
            if work.valid_picks:
                chapter.content = "\n\n".join(_inject_images(paras, work.valid_picks, image_dir))
            return

        # Stage 2: Generate image prompts -> LLM batch -> ComfyUI
        prompt_rendereds = work.render_prompts(needs_gen)
        image_prompts = await self.aask(prompt_rendereds)

        workflows, gen_indices, filtered_prompts = work.collect_workflows(needs_gen, image_prompts)
        if not workflows:
            logger.warn(f"Chapter {chapter.chapter_index}: no valid prompts generated")
            return

        comfyui_timeout = len(workflows) * ctx.comfyui_timeout_per_image
        download_dirs = [str(save_dir)] * len(workflows)
        results = await self.acomfyui_generate(workflows, download_dirs=download_dirs, timeout=comfyui_timeout)

        work.process_results(gen_indices, filtered_prompts, results)

        # Inject <img> tags into raw text
        if work.valid_picks:
            chapter.content = "\n\n".join(_inject_images(paras, work.valid_picks, image_dir))
            logger.info(f"Chapter {chapter.chapter_index}: injected {len(work.valid_picks)} <img> tags")
        else:
            logger.warn(
                f"Chapter {chapter.chapter_index}: no images generated from {len(valid_indices)} selected paragraphs"
            )
