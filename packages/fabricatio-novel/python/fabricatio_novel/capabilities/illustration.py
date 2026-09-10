"""Post-process novel illustration: batch-propose prompts, batch-render, then attach."""

import asyncio
from abc import ABC
from pathlib import Path
from shutil import copyfile
from typing import Unpack

from fabricatio_core import logger
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK
from fabricatio_core.utils import cfg, first_available

cfg(["comfyui"])

from fabricatio_comfyui.capabilities.comfyui import UseComfyUI
from fabricatio_comfyui.capabilities.loras import ChooseLoras
from fabricatio_comfyui.models import LoraCatalog
from fabricatio_comfyui.models.resolution import Prop
from fabricatio_comfyui.models.specs import SketchSpec
from fabricatio_judge.capabilities import RefineLoop, VisuallyJudge
from fabricatio_judge.models import Verdict
from fabricatio_judge.models.refine import RefinePlan

from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.illustration import (
    IllustratedScene,
    IllustrationPromptDecorator,
    IllustrationScopedConfig,
    RenderError,
    RenderJob,
    RenderOutcome,
)
from fabricatio_novel.models.illustration_queue import (
    PendingIllustration,
    SceneIllustrationQueue,
)
from fabricatio_novel.models.novel import Novel

__all__ = ["IllustrateScenes"]


class IllustrateScenes(IllustrationScopedConfig, NovelCompose, ChooseLoras, VisuallyJudge, RefineLoop, UseComfyUI, ABC):
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
        illustration_choose_loras: bool | None = None,
        illustration_judge: bool | None = None,
        illustration_judge_max_tries: int | None = None,
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
            illustration_choose_loras: Opt-in per-scene LLM LoRA selection from the comfyui
                catalog; wins over the scoped field and the global default (off).
            illustration_judge: Opt-in per-scene visual judgement of rendered illustrations; wins over the
                scoped field and the global default (off). Failed verdicts re-propose the prompt and re-render.
            illustration_judge_max_tries: Total generation attempts per scene when the judge is on; the last
                attempt's image is always kept. ``None`` falls back to the global
                ``[ext.novel] illustration_judge_max_tries``.
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
        choose = (
            first_available(
                (illustration_choose_loras, self.illustration_choose_loras, novel_config.illustration_choose_loras)
            )
            or False
        )
        judge = first_available((illustration_judge, self.illustration_judge, novel_config.illustration_judge)) or False
        budget = (
            illustration_judge_max_tries
            if illustration_judge_max_tries is not None
            else novel_config.illustration_judge_max_tries
        )
        illustrations = await self._propose_and_render(
            queue.entries,
            send_to=send_to,
            choose_loras=choose,
            max_tries=budget if judge else 1,
            **kwargs,
        )
        logger.info(f"Illustrated {len(illustrations)} new scene(s) for novel '{novel_ctx.title}'")
        return illustrations

    async def _propose_and_render(
        self,
        pending: tuple[PendingIllustration, ...],
        *,
        send_to: str | None,
        choose_loras: bool,
        max_tries: int,
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
        jobs: list[tuple[PendingIllustration, SketchSpec]] = []
        for p, proposal in zip(pending, proposals, strict=True):
            if isinstance(proposal, BaseException):
                logger.warn(f"Illustration prompt proposal failed for scene '{p.scene_title}': {proposal}; skipping")
                continue
            if proposal is None:
                logger.warn(f"Illustration prompt proposal failed for scene '{p.scene_title}'; skipping")
                continue
            jobs.append((p, proposal))

        # LoRA chain per job: the batch decoration rule closes every prompt with
        # always-lora triggers, picked-lora triggers, then the quality suffix.
        decorator = IllustrationPromptDecorator(
            always=tuple(novel_config.illustration_always_loras),
            catalog=LoraCatalog.from_config(),
            suffix=novel_config.illustration_prompt_suffix,
        )
        always = decorator.always_specs()
        render_jobs: list[RenderJob] = []
        for p, spec in jobs:
            if choose_loras:
                picked = tuple(await self.choose_loras(spec.prompt, catalog=decorator.catalog, send_to=send_to))
            else:
                picked = ()
            render_jobs.append(
                RenderJob(
                    key=p.key,
                    title=p.scene_title,
                    spec=spec,
                    target=p.target,
                    requirement=p.requirement,
                    prompt=decorator(spec.prompt, picked),
                    loras=(*always, *picked),
                    picked=picked,
                    decorator=decorator,
                ),
            )

        # Phase 3: render all prompts concurrently; each failure degrades its own scene.
        # Renders queue at the shared ComfyUI server, so the timeout grows linearly
        # with the batch size instead of staying fixed.
        timeout = novel_config.illustration_timeout_per_image * len(render_jobs)
        logger.info(f"Rendering {len(render_jobs)} scene illustration(s) with batch-scaled timeout {timeout:.0f}s")
        illustrations: dict[tuple[int, int], tuple[str, str]] = {}
        for entry in await asyncio.gather(
            *(
                self._render_job(job, timeout=timeout, max_tries=max_tries, send_to=send_to, **kwargs)
                for job in render_jobs
            )
        ):
            if entry is not None:
                key, value = entry
                illustrations[key] = value
        return illustrations

    async def _render_scene(self, job: RenderJob, timeout: float) -> RenderOutcome:
        """Render one job's illustration into its canonical target.

        ``timeout`` is the batch-scaled budget shared by every concurrent render of
        this batch (``illustration_timeout_per_image`` x batch size). The job carries
        the trigger-augmented, quality-suffixed prompt and its frozen lora chain.

        Raises:
            RenderError: When ComfyUI generation fails or yields no image for this scene.
        """
        prop = (
            job.spec.prop
            if job.spec.prop is not None
            else (Prop(novel_config.illustration_prop) if novel_config.illustration_prop else None)
        )
        mp = job.spec.mp if job.spec.mp is not None else novel_config.illustration_mp
        ceiling = novel_config.illustration_mp_max
        if mp is not None and mp > ceiling:
            logger.warn(f"Clamping scene '{job.title}' illustration mp {mp} to the {ceiling} ceiling")
            mp = ceiling
        try:
            path = await self.generate_image(
                job.prompt,
                download_dir=job.target.parent,
                negative_prompt=job.spec.negative_prompt or novel_config.illustration_negative_prompt or None,
                prop=prop,
                mp=mp,
                seed=novel_config.illustration_seed,
                loras=list(job.loras),
                timeout=timeout,
            )
        except Exception as e:  # converted to the per-scene degrade signal; never crashes the batch
            raise RenderError(f"generation error for scene '{job.title}': {e}") from e
        if path is None:
            raise RenderError(f"generation returned no image for scene '{job.title}'")
        copyfile(path, job.target)
        return RenderOutcome(prompt=job.prompt, image=str(job.target.resolve()))

    async def _render_job(
        self,
        job: RenderJob,
        *,
        timeout: float,
        max_tries: int,
        send_to: str | None,
        **kwargs: Unpack[LLMKwargs],
    ) -> tuple[tuple[int, int], tuple[str, str]] | None:
        """Render one scene's illustration through the judged refine loop.

        ``max_tries`` is the total render budget: ``1`` renders once and is never
        inspected (the judge-off shape); larger budgets inspect every render but the
        last with a vision LLM, archiving rejected attempts beside the canonical
        target as ``.attempt<N>`` PNGs and re-proposing the sketch with the
        accumulated feedback. The loop invariants — budget clamp, last attempt kept
        unjudged, judge-absence degrade-open — live on
        :meth:`~fabricatio_judge.capabilities.refine.RefineLoop.refine_until_accepted`.

        Returns:
            The illustrations-map entry for this scene, or ``None`` when generation fails and the scene degrades.
        """

        async def generate(spec: SketchSpec) -> RenderOutcome:
            return await self._render_scene(job.with_spec(spec), timeout)

        async def inspect(outcome: RenderOutcome) -> Verdict | None:
            return await self.visually_judge(
                job.target, issue_to_judge=f"Scene '{job.title}' must show: {outcome.prompt}"
            )

        def archive(outcome: RenderOutcome, attempt: int) -> None:
            copyfile(job.target, job.archive_path(attempt))

        try:
            outcome = await self.refine_until_accepted(
                SketchSpec,
                job.requirement,
                job.spec,
                RefinePlan[SketchSpec, RenderOutcome](
                    generate=generate,
                    judge=inspect,
                    request_of=lambda rendered: rendered.prompt,
                    on_reject=archive,
                    label=f"scene '{job.title}'",
                ),
                max_tries=max_tries,
                feedback_template=novel_config.scene_illustration_feedback_template,
                send_to=send_to,
                **kwargs,
            )
        except RenderError as e:
            logger.warn(f"{e}; skipping")
            return None
        return job.entry_of(outcome)

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
        for ci, (chapter, chapter_ctx) in enumerate(zip(novel.chapter, novel_ctx.child_contexts, strict=True), 1):
            scene_offset = 0
            for story, story_ctx in zip(chapter.story, chapter_ctx.child_contexts, strict=True):
                for index, scene_ctx in enumerate(story_ctx.child_contexts):
                    scene_idx = scene_offset + index + 1
                    if (ci, scene_idx) not in illustrations:
                        continue
                    prompt, image = illustrations[(ci, scene_idx)]
                    story.scenes[index] = IllustratedScene.from_context(
                        scene_ctx, illustration_prompt=prompt, illustration_image=image
                    )
                scene_offset += len(story_ctx.child_contexts)
        return novel

    async def post_process_novel(
        self,
        ctx: NovelContext,
        novel: Novel,
        *,
        persist_dir: str | Path | None = None,
        send_to: str | None = None,
        illustration_constraint: str | None = None,
        illustration_choose_loras: bool | None = None,
        illustration_judge: bool | None = None,
        illustration_judge_max_tries: int | None = None,
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
            illustration_choose_loras: Opt-in per-scene catalog LoRA selection forwarded to the
                phase; ``None`` falls back to the scoped config and the global default (off).
            illustration_judge: Opt-in per-scene visual judgement of rendered illustrations forwarded to
                the phase; ``None`` falls back to the scoped config and the global default (off).
            illustration_judge_max_tries: Total generation attempts per scene when the judge is on
                forwarded to the phase; ``None`` falls back to the global default.
        """
        if persist_dir is None:
            return novel
        illustrations = await self.illustrate_novel_phase(
            ctx,
            persist_dir=persist_dir,
            send_to=send_to or TASK,
            illustration_constraint=illustration_constraint,
            illustration_choose_loras=illustration_choose_loras,
            illustration_judge=illustration_judge,
            illustration_judge_max_tries=illustration_judge_max_tries,
            **kwargs,
        )
        return self.attach_illustrations(ctx, novel, illustrations)
