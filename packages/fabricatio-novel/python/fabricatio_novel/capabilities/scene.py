from abc import ABC
from typing import Unpack

from fabricatio_character.capabilities.character import CharacterCompose
from fabricatio_character.models.character import CharacterCardDiff
from fabricatio_character.utils import dump_card
from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK, TextCapturer, detect_language

from fabricatio_novel.config import novel_config
from fabricatio_novel.models.context.base import ContextBase
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.plan import plan_list_question, plan_list_validator
from fabricatio_novel.models.scene import Scene


_SCENE_CAPTURE = TextCapturer.with_pattern(r"###\s*(.+?)\s*\n\s*>\s*(.+?)\s*\n\n([\s\S]+)")


def capture_scene(response: str) -> Scene | None:
    """Capture the title, description, and content from a plain-text scene response.

    The scene is written as a ``###`` heading, a ``>`` blockquote
    description, and the prose after a blank line; no JSON is involved,
    so paragraphs keep their line breaks verbatim. Returns None when the
    structure is missing, which makes ``aask_validate`` retry.
    """
    captured = _SCENE_CAPTURE.cap3(response)
    if captured is None:
        return None
    title, description, content = (part.strip() for part in captured)
    if not (title and description and content):
        return None
    return Scene(title=title, description=description, expected_word_count=0, content=content)


class SceneCompose(CharacterCompose, ABC):
    """This class contains the capabilities for the scene."""

    async def before_compose_scene(
        self,
        ctx: SceneContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> SceneContext:
        return ctx

    async def after_compose_scene(
        self,
        ctx: SceneContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> SceneContext:
        return ctx

    async def post_process_scene(self, ctx: SceneContext, scene: Scene, **kwargs: Unpack[LLMKwargs]) -> Scene:
        return scene

    def _scene_requirement_vars(self, ctx: SceneContext) -> dict[str, object]:
        """Build the scene_requirement template variables for a scene context.

        Overriding capabilities (bible context, RAG) reuse these vars and add
        their own blocks before rendering.
        """
        characters = ctx.dump_charactors()
        return {
            "title": ctx.title,
            "description": ctx.description,
            "expected_word_count": ctx.expected_word_count,
            "characters": characters,
            "language": ctx.language or detect_language(ctx.description),
            "prefixed_content": ctx.prefixed_content,
        }

    async def prepare_scene_requirement(
        self,
        ctx: SceneContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> str:
        return TEMPLATE_MANAGER.render_template(
            novel_config.scene_requirement_template,
            self._scene_requirement_vars(ctx),
        )

    async def generate_scene(
        self,
        ctx: SceneContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> Scene | None:
        logger.debug(f"Generating scene '{ctx.title}'")
        await self.interpolate_charactors(ctx, send_to, **kwargs)
        requirement = await self.prepare_scene_requirement(ctx, **kwargs)
        scene = await self.aask_validate(requirement, capture_scene, send_to=send_to, **kwargs)
        if scene is None:
            return None
        scene.expect_(ctx.expected_word_count)
        ctx.set_content(scene.content)
        logger.info(f"Scene '{scene.title}' generated")
        return scene

    async def interpolate_charactors(
        self,
        ctx: ContextBase,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> None:
        """Extend every trace with the character states occurring in this element.

        Runs before the element is planned or written, so the pre-scheduled
        chain can guide both plan and content generation.
        """
        if not ctx.charactor_trace:
            return
        logger.debug(f"Interpolating {len(ctx.charactor_trace)} character(s) for '{ctx.title}'")
        prompts = [
            TEMPLATE_MANAGER.render_template(
                novel_config.charactor_diff_template,
                {
                    "title": ctx.title,
                    "description": ctx.description,
                    "outline": getattr(ctx, "outline", ""),
                    "chain": "\n\n".join(dump_card(card) for card in trace.iter_charactor_cards()),
                    "language": ctx.language,
                },
            )
            for trace in ctx.charactor_trace
        ]
        chains = await self.aask_validate(
            [plan_list_question(prompt, CharacterCardDiff) for prompt in prompts],
            plan_list_validator(CharacterCardDiff),
            send_to=send_to,
            **kwargs,
        )
        for trace, chain in zip(ctx.charactor_trace, chains or [], strict=False):
            if not chain:
                continue
            for diff in chain:
                trace.end = trace.end.apply(diff)
            trace.intepl([*trace.interpolates, *chain])

    async def compose_scene(
        self,
        ctx: SceneContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> Scene | None:
        ctx = await self.before_compose_scene(ctx, **kwargs)
        scene = await self.generate_scene(ctx, send_to, **kwargs)
        ctx = await self.after_compose_scene(ctx, **kwargs)

        if scene is None:
            return None
        ok_scene = await self.post_process_scene(ctx, scene, **kwargs)

        return ok_scene
