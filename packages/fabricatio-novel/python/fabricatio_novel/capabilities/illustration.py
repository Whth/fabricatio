"""Post-process novel illustration: batch-propose prompts, batch-render, then attach."""

import asyncio
from abc import ABC
from pathlib import Path
from shutil import copyfile
from typing import Unpack

from fabricatio_core import logger
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK
from fabricatio_core.utils import cfg, first_available

cfg(["comfyui"])

from fabricatio_comfyui.capabilities.comfyui import UseComfyUI
from fabricatio_comfyui.capabilities.loras import ChooseLoras
from fabricatio_comfyui.models import LoraCatalog, LoraSpec
from fabricatio_comfyui.models.resolution import Prop
from fabricatio_comfyui.models.specs import SketchSpec

from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.illustration import (
    IllustratedScene,
    IllustrationScopedConfig,
)
from fabricatio_novel.models.illustration_queue import (
    PendingIllustration,
    SceneIllustrationQueue,
)
from fabricatio_novel.models.novel import Novel

__all__ = ["IllustrateScenes"]


class IllustrateScenes(IllustrationScopedConfig, NovelCompose, ChooseLoras, Propose, UseComfyUI, ABC):
    """Post-process illustration over a finished context: propose, render, then attach.

    Collects every pending scene of the composed context tree, proposes all
    image-generation prompts concurrently, renders them concurrently via
    ComfyUI into the run's ``images/`` directory, and returns the results
    keyed by ``(chapter_index, scene_index)``; the attach step swaps those
    scenes in the assembled novel for
    :class:`~fabricatio_novel.models.illustration.IllustratedScene` copies.
    Failures degrade per scene (warn + skip).

    Prompt proposals honor a global constraint (style etc.) resolved through
    the scoped-config chain: the per-call ``illustration_constraint`` wins,
    then this instance's
    :attr:`~fabricatio_novel.models.illustration.IllustrationScopedConfig.illustration_constraint`,
    then the global ``[ext.novel] illustration_constraint``.
    """

    async def illustrate_novel_phase(
        self,
        novel_ctx: NovelContext,
        *,
        persist_dir: str | Path,
        send_to: str | None = TASK,
        illustration_constraint: str | None = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> dict[tuple[int, int], tuple[str, str]]:
        """Illustrate every scene of the finished context and return the rendered results.

        Runs in three phases: collect the pending scenes (skip-existing
        filter applied), propose all prompts concurrently, then render all
        prompts concurrently. Scene indices are chapter-scoped and run
        across stories, matching the naming used by the EPUB exporter.

        Args:
            novel_ctx: The composed novel context whose scenes get illustrated.
            persist_dir: Run directory receiving the ``images/`` output subdirectory.
            send_to: Routing group for the illustration-prompt proposals.
            illustration_constraint: Global constraint (style etc.) merged into every
                proposal requirement; wins over the scoped
                :attr:`~fabricatio_novel.models.illustration.IllustrationScopedConfig.illustration_constraint`
                and the global ``[ext.novel] illustration_constraint``.
            **kwargs: Extra LLM knobs forwarded to the proposal call.

        Returns:
            Mapping of ``(chapter_index, scene_index)`` to the proposed prompt and the
            absolute path of the rendered PNG; only successfully rendered scenes appear.
        """
        queue = SceneIllustrationQueue.from_context(
            novel_ctx,
            persist_dir=persist_dir,
            constraint=(
                first_available(
                    (illustration_constraint, self.illustration_constraint, novel_config.illustration_constraint)
                )
                or ""
            ),
        )
        if not queue.entries:
            return {}
        illustrations = await self._propose_and_render(queue.entries, send_to=send_to, **kwargs)
        logger.info(f"Illustrated {len(illustrations)} new scene(s) for novel '{novel_ctx.title}'")
        return illustrations

    async def _propose_and_render(
        self,
        pending: tuple[PendingIllustration, ...],
        *,
        send_to: str | None,
        **kwargs: Unpack[LLMKwargs],
    ) -> dict[tuple[int, int], tuple[str, str]]:
        """Propose every pending prompt concurrently, then render all prompts concurrently.

        One failed proposal or render skips only its own scene (warn + skip).

        Every render shares the ComfyUI server's queue, so the per-render timeout
        scales linearly with the batch size:
        ``illustration_timeout_per_image`` x pending renders — instead of staying
        fixed, which spuriously times out images queued behind their batch mates.
        """
        # Phase 2: propose all image prompts concurrently; one failure skips only its scene.
        proposals = await asyncio.gather(
            *(self.propose(SketchSpec, p.requirement, send_to=send_to, **kwargs) for p in pending),
            return_exceptions=True,
        )
        jobs: list[tuple[tuple[int, int], str, SketchSpec, Path]] = []
        for p, proposal in zip(pending, proposals, strict=True):
            if isinstance(proposal, BaseException):
                logger.warn(f"Illustration prompt proposal failed for scene '{p.scene_title}': {proposal}; skipping")
                continue
            if proposal is None:
                logger.warn(f"Illustration prompt proposal failed for scene '{p.scene_title}'; skipping")
                continue
            jobs.append((p.key, p.scene_title, proposal, p.target))

        # LoRA chain per job: ``illustration_always_loras`` entries ride
        # every render and their trigger words activate them; the comfyui
        # catalog stays the selectable pool — the LLM picks per scene on
        # top, with picked words resolved from the catalog entries.
        always_entries = novel_config.illustration_always_loras
        always_specs = [LoraSpec(lora_name=e.lora_name, strength=e.strength) for e in always_entries]
        catalog = LoraCatalog.from_config()
        render_jobs: list[tuple[tuple[int, int], str, SketchSpec, Path, str, list[LoraSpec]]] = []
        for key, title, si, target in jobs:
            picked = await self.choose_loras(si.prompt, catalog=catalog)
            prompt = si.prompt
            for entry in always_entries:
                prompt = entry.augmented_prompt(prompt)
            render_jobs.append((key, title, si, target, catalog.augment(prompt, picked), [*always_specs, *picked]))

        # Phase 3: render all prompts concurrently; each failure degrades its own scene.
        # Renders queue at the shared ComfyUI server, so the timeout grows linearly
        # with the batch size instead of staying fixed.
        timeout = novel_config.illustration_timeout_per_image * len(jobs)
        logger.info(f"Rendering {len(jobs)} scene illustration(s) with batch-scaled timeout {timeout:.0f}s")
        illustrations: dict[tuple[int, int], tuple[str, str]] = {}
        for entry in await asyncio.gather(
            *(
                self._render_scene(key, title, si, target, timeout, prompt, loras)
                for key, title, si, target, prompt, loras in render_jobs
            )
        ):
            if entry is not None:
                key, value = entry
                illustrations[key] = value
        return illustrations

    async def _render_scene(
        self,
        key: tuple[int, int],
        title: str,
        si: SketchSpec,
        target: Path,
        timeout: float,
        prompt: str,
        loras: list[LoraSpec],
    ) -> tuple[tuple[int, int], tuple[str, str]] | None:
        """Render one scene's illustration into ``target``; ``None`` when the render fails.

        ``timeout`` is the batch-scaled budget shared by every concurrent render of
        this batch (``illustration_timeout_per_image`` x batch size).  ``prompt``
        and ``loras`` are the resolved render prompt (possibly trigger-augmented)
        and LoRA chain handed down from the proposal phase.
        """
        prop = (
            si.prop
            if si.prop is not None
            else (Prop(novel_config.illustration_prop) if novel_config.illustration_prop else None)
        )
        mp = si.mp if si.mp is not None else novel_config.illustration_mp
        ceiling = novel_config.illustration_mp_max
        if mp is not None and mp > ceiling:
            logger.warn(f"Clamping scene '{title}' illustration mp {mp} to the {ceiling} ceiling")
            mp = ceiling
        try:
            path = await self.generate_image(
                prompt,
                download_dir=target.parent,
                negative_prompt=si.negative_prompt or novel_config.illustration_negative_prompt or None,
                prop=prop,
                mp=mp,
                seed=novel_config.illustration_seed,
                loras=loras,
                timeout=timeout,
            )
        except Exception as e:  # noqa: BLE001 - per-scene degrade: one bad render must not fail the run
            logger.warn(f"Image generation failed for scene '{title}': {e}; skipping")
            return None
        if path is None:
            logger.warn(f"Image generation failed for scene '{title}'; skipping")
            return None
        copyfile(path, target)
        return key, (prompt, str(target.resolve()))

    def attach_illustrations(
        self,
        novel_ctx: NovelContext,
        novel: Novel,
        illustrations: dict[tuple[int, int], tuple[str, str]],
    ) -> Novel:
        """Swap every rendered scene in the assembled novel for its illustrated output.

        Walks the context tree and the materialized novel in strict lockstep (both
        are built in the same prefix order) and replaces each scene whose
        ``(chapter_index, scene_index)`` key was rendered with an
        :class:`~fabricatio_novel.models.illustration.IllustratedScene` copy; the
        remaining scenes pass through untouched.
        """
        for ci, (chapter, chapter_ctx) in enumerate(zip(novel.chapter, novel_ctx.chapter_context, strict=True), 1):
            scene_offset = 0
            for story, story_ctx in zip(chapter.story, chapter_ctx.story_context, strict=True):
                for index, scene_ctx in enumerate(story_ctx.scene_context):
                    scene_idx = scene_offset + index + 1
                    if (ci, scene_idx) not in illustrations:
                        continue
                    prompt, image = illustrations[(ci, scene_idx)]
                    story.scenes[index] = IllustratedScene.from_context(
                        scene_ctx, illustration_prompt=prompt, illustration_image=image
                    )
                scene_offset += len(story_ctx.scene_context)
        return novel

    async def post_process_novel(
        self,
        ctx: NovelContext,
        novel: Novel,
        *,
        persist_dir: str | Path | None = None,
        send_to: str | None = None,
        illustration_constraint: str | None = None,
        **kwargs: Unpack[LLMKwargs],
    ) -> Novel:
        """Illustrate every scene and attach the results, returning the transformed novel.

        Identity when ``persist_dir`` is missing (the base ``compose_novel`` caller
        never sets it); performs the batched render + attach when it is. Failures
        degrade per scene (warn + skip).

        Args:
            ctx: The composed novel context whose scenes get illustrated.
            novel: The assembled novel to attach rendered scenes onto.
            persist_dir: Run directory receiving the ``images/`` output subdirectory.
            send_to: Routing group for the illustration-prompt proposals.
            illustration_constraint: Global constraint (style etc.) forwarded to the
                phase; ``None`` falls back to the scoped config and the global default.
        """
        if persist_dir is None:
            return novel
        illustrations = await self.illustrate_novel_phase(
            ctx,
            persist_dir=persist_dir,
            send_to=send_to or TASK,
            illustration_constraint=illustration_constraint,
            **kwargs,
        )
        return self.attach_illustrations(ctx, novel, illustrations)
