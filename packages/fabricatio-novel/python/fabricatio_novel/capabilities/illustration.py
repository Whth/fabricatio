"""Post-process novel illustration: propose one image prompt per scene, render it, then attach."""

from abc import ABC
from pathlib import Path
from shutil import copyfile
from typing import Unpack

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK
from fabricatio_core.utils import cfg

cfg(["comfyui"])

from fabricatio_comfyui.capabilities.comfyui import UseComfyUI

from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.illustration import IllustratedScene, SceneIllustration
from fabricatio_novel.models.novel import Novel
from fabricatio_novel.utils import scene_image_name

__all__ = ["IllustrateScenes"]


class IllustrateScenes(NovelCompose, Propose, UseComfyUI, ABC):
    """Post-process illustration over a finished context: propose, render, then attach.

    Walks every scene of the composed context tree, proposes one image-generation
    prompt per scene, renders it via ComfyUI into the run's ``images/`` directory,
    and returns the results keyed by ``(chapter_index, scene_index)``; the attach
    step swaps those scenes in the assembled novel for
    :class:`~fabricatio_novel.models.illustration.IllustratedScene` copies.
    Failures degrade per scene (warn + skip).

    Implements the integration via :meth:`NovelCompose.post_process_novel`: when a
    role mixing this class runs ``compose_novel``, or a staged workflow ends in
    :class:`~fabricatio_novel.actions.novel.IllustrateNovelStage` (whose dump
    stage fires the same hook), illustration runs automatically — callers do not
    need to call the phase and attach methods separately. Pass ``persist_dir``
    through to enable; with no ``persist_dir`` the hook is the base identity.
    """

    async def illustrate_novel_phase(
        self,
        novel_ctx: NovelContext,
        *,
        persist_dir: str | Path,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> dict[tuple[int, int], tuple[str, str]]:
        """Illustrate every scene of the finished context and return the rendered results.

        Scene indices are chapter-scoped and run across stories, matching the
        naming used by the EPUB exporter.

        Args:
            novel_ctx: The composed novel context whose scenes get illustrated.
            persist_dir: Run directory receiving the ``images/`` output subdirectory.
            send_to: Routing group for the illustration-prompt proposals.
            **kwargs: Extra LLM knobs forwarded to the proposal call.

        Returns:
            Mapping of ``(chapter_index, scene_index)`` to the proposed prompt and the
            absolute path of the rendered PNG; only successfully rendered scenes appear.
        """
        images_dir = Path(persist_dir) / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        illustrations: dict[tuple[int, int], tuple[str, str]] = {}
        for ci, chapter in enumerate(novel_ctx.iter_prefixed_contexts(), 1):
            scene_offset = 0
            for story in chapter.iter_prefixed_contexts():
                for scene_idx, scene in enumerate(story.scene_context, scene_offset + 1):
                    target = images_dir / Path(scene_image_name(ci, scene_idx)).name
                    if novel_config.illustration_skip_existing and target.is_file():
                        continue
                    requirement = TEMPLATE_MANAGER.render_template(
                        novel_config.scene_illustration_prompt_template,
                        {
                            "novel_title": novel_ctx.title,
                            "chapter_title": chapter.title,
                            "story_title": story.title,
                            "scene_title": scene.title,
                            "scene_description": scene.description,
                            "scene_content": scene.content,
                            "cast": scene.scene_plan.cast if scene.scene_plan else [],
                        },
                    )
                    si = await self.propose(SceneIllustration, requirement, send_to=send_to, **kwargs)
                    if si is None:
                        logger.warn(f"Illustration prompt proposal failed for scene '{scene.title}'; skipping")
                        continue
                    try:
                        path = await self.generate_image(
                            si.prompt,
                            download_dir=images_dir,
                            negative_prompt=si.negative_prompt or novel_config.illustration_negative_prompt or None,
                            width=novel_config.illustration_width,
                            height=novel_config.illustration_height,
                            seed=novel_config.illustration_seed,
                        )
                    except Exception as e:  # noqa: BLE001 - per-scene degrade: one bad render must not fail the run
                        logger.warn(f"Image generation failed for scene '{scene.title}': {e}; skipping")
                        continue
                    if path is None:
                        logger.warn(f"Image generation failed for scene '{scene.title}'; skipping")
                        continue
                    copyfile(path, target)
                    illustrations[(ci, scene_idx)] = (si.prompt, str(target.resolve()))
                scene_offset += len(story.scene_context)
        logger.info(f"Illustrated {len(illustrations)} new scene(s) for novel '{novel_ctx.title}'")
        return illustrations

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
        **kwargs: Unpack[LLMKwargs],
    ) -> Novel:
        """Illustrate every scene and attach the results, returning the transformed novel.

        Identity when ``persist_dir`` is missing (the base ``compose_novel`` caller
        never sets it); performs the full render + attach when it is. Failures
        degrade per scene (warn + skip).
        """
        if persist_dir is None:
            return novel
        illustrations = await self.illustrate_novel_phase(
            ctx, persist_dir=persist_dir, send_to=send_to or TASK, **kwargs
        )
        return self.attach_illustrations(ctx, novel, illustrations)
