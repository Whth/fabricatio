"""Per-scene ComfyUI illustration: propose one image prompt per scene and render it to a PNG."""

from abc import ABC
from pathlib import Path
from typing import Unpack

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK
from fabricatio_core.utils import cfg

cfg(["comfyui"])

from fabricatio_comfyui.capabilities.comfyui import UseComfyUI

from fabricatio_novel.config import novel_config
from fabricatio_novel.models.context.illustration import IllustratedSceneContext
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.illustration import IllustratedScene, SceneIllustration
from fabricatio_novel.models.novel import Novel

__all__ = ["IllustrateScenes"]


class IllustrateScenes(Propose, UseComfyUI, ABC):
    """Per-scene illustration: propose an image-generation prompt, then render it via ComfyUI.

    The channel is sealed to :class:`~fabricatio_novel.models.context.illustration.IllustratedSceneContext`:
    only scenes whose context is that subclass get illustrated, so pipelines composed of
    plain scene contexts run unchanged and the illustrated/plain choice is made by whichever
    stages materialize the channel. Failures degrade per scene (warn + skip); the returned
    count reports the successfully illustrated scenes.
    """

    async def illustrate_scenes_phase(
        self,
        novel_ctx: NovelContext,
        *,
        persist_dir: str | Path,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> int:
        """Illustrate every unillustrated illustrated-channel scene and return the success count.

        Args:
            novel_ctx: The composed novel context whose channel scenes get illustrated.
            persist_dir: Run directory receiving the ``images/`` output subdirectory.
            send_to: Routing group for the illustration-prompt proposals.
            **kwargs: Extra LLM knobs forwarded to the proposal call.

        Returns:
            The number of scenes whose image was rendered and recorded this run.
        """
        images_dir = Path(persist_dir) / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        for chapter in novel_ctx.iter_prefixed_contexts():
            for story in chapter.iter_prefixed_contexts():
                for scene in story.scene_context:
                    if not isinstance(scene, IllustratedSceneContext):
                        continue
                    if novel_config.illustration_skip_existing and scene.illustration_image:
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
                    scene.set_illustration(si.prompt, str(Path(path).resolve()))
                    count += 1
        logger.info(f"Illustrated {count} new scene(s) for novel '{novel_ctx.title}'")
        return count

    def materialize_illustrated(self, ctx: NovelContext, novel: Novel) -> Novel:
        """Swap every illustrated context's scene in the assembled novel for its illustrated output.

        Walks the context tree and the materialized novel in lockstep (both are built in the
        same prefix order) and replaces scenes whose context carries the illustration channel
        with :class:`~fabricatio_novel.models.illustration.IllustratedScene` copies; plain
        scenes pass through untouched.
        """
        for chapter, chapter_ctx in zip(novel.chapter, ctx.chapter_context, strict=True):
            for story, story_ctx in zip(chapter.story, chapter_ctx.story_context, strict=True):
                for index, scene_ctx in enumerate(story_ctx.scene_context):
                    if not isinstance(scene_ctx, IllustratedSceneContext) or not scene_ctx.illustration_image:
                        continue
                    story.scenes[index] = IllustratedScene.from_context(scene_ctx)
        return novel
