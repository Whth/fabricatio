"""Scene composition capabilities: rendering requirements and generating scene content."""

from abc import ABC
from typing import Sequence, Unpack

from fabricatio_character.capabilities.character import CharacterCompose
from fabricatio_character.models.character import CharacterCardDiffs, CharacterCardSlices
from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK, detect_language, word_count
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.context.base import CharacterTrace, ContextBase
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.scene import Scene


class SceneCompose(CharacterCompose, ABC):
    """This class contains the capabilities for the scene."""

    async def before_compose_scene(
        self,
        ctx: SceneContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> SceneContext:
        """Identity hook invoked before composing a scene; may mutate the context."""
        return ctx

    async def after_compose_scene(
        self,
        ctx: SceneContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> SceneContext:
        """Identity hook invoked after generating a scene; may mutate the context."""
        return ctx

    async def post_process_scene(self, ctx: SceneContext, scene: Scene, **kwargs: Unpack[LLMKwargs]) -> Scene:
        """Identity hook invoked on the composed scene; may transform and return the scene."""
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
            "writing_style": ctx.writing_style,
            "writing_constraint": ctx.writing_constraint,
            "characters": characters,
            "language": ctx.language or detect_language(ctx.description),
            "prefixed_content": ctx.prefixed_content,
        }

    async def prepare_scene_requirement(
        self,
        ctx: SceneContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> str:
        """Render the scene requirement prompt from the scene context.

        Overriding capabilities may extend the rendered requirement, for
        example by appending writing style references.
        """
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
        """Generate the scene content via the LLM.

        Interpolates character states, renders the scene requirement, asks
        the LLM for the scene text, sets the expected word count, and stores
        the content on the context. Returns the generated scene.
        """
        logger.debug(f"Generating scene '{ctx.title}'")
        await self.interpolate_characters(ctx, send_to, **kwargs)
        requirement = await self.prepare_scene_requirement(ctx, **kwargs)
        logger.debug(f"Scene '{ctx.title}' requirement rendered ({len(requirement)} chars)")
        scene = Scene(
            title=ctx.title,
            description=ctx.description,
            expected_word_count=0,
            content=(await self.aask(requirement, send_to=send_to, **kwargs)).strip(),
        )
        scene.expect_(ctx.expected_word_count)
        ctx.set_content(scene.content)
        logger.info(
            f"Scene '{scene.title}' composed ({word_count(scene.content)} words, word count satisfaction: {scene.satisfy_ratio()}"
        )
        return scene

    async def interpolate_characters(
        self,
        ctx: ContextBase,
        send_to: str | None = TASK,
        outline: str = "",
        **kwargs: Unpack[LLMKwargs],
    ) -> None:
        """Extend every trace with the character states occurring in this element.

        Runs before the element is planned or written, so the pre-scheduled
        chain can guide both plan and content generation.

        ``outline`` is the novel-level story outline; only the novel root passes
        it. Lower levels leave it empty and the prompt section is dropped.
        """
        if not ctx.character_trace:
            return
        logger.debug(f"Interpolating {len(ctx.character_trace)} character(s) for '{ctx.title}'")
        prompts = [
            TEMPLATE_MANAGER.render_template(
                novel_config.charactor_diff_template,
                {
                    "title": ctx.title,
                    "description": ctx.description,
                    "outline": outline,
                    "chain": trace.dump_to_prompt(),
                    "language": ctx.language,
                },
            )
            for trace in ctx.character_trace
        ]
        chains = await self.propose(
            CharacterCardDiffs,
            prompts,
            send_to=send_to,
            **kwargs,
        )
        applied = 0
        for trace, chain in zip(ctx.character_trace, chains or [], strict=False):
            if chain is None or not chain.root:
                continue
            applied += 1
            trace.intepl([*trace.interpolates, *chain.root])
        logger.debug(f"Extended {applied} character chain(s) for '{ctx.title}'")

    async def split_character_slices(
        self,
        ctx: ContextBase,
        children: Sequence[ContextBase],
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> None:
        """Split each trace's chain into per-child slices and assign them to the children.

        Runs after the children are planned; every child receives one trace
        per character, holding its allocated slice (possibly empty), so the
        child extends only its own states.
        """
        if not ctx.character_trace or not children:
            return
        logger.debug(f"Splitting {len(ctx.character_trace)} character chain(s) into {len(children)} slice(s)")
        prompts = [
            TEMPLATE_MANAGER.render_template(
                novel_config.charactor_slice_template,
                {
                    "title": ctx.title,
                    "description": ctx.description,
                    "children": [{"title": child.title, "description": child.description} for child in children],
                    "chain": trace.dump_to_prompt(),
                    "language": ctx.language,
                },
            )
            for trace in ctx.character_trace
        ]
        slices = await self.propose(
            CharacterCardSlices,
            prompts,
            send_to=send_to,
            **kwargs,
        )
        assigned = 0
        for trace, per_child in zip(ctx.character_trace, slices or [], strict=False):
            if per_child is None:
                continue
            assigned += 1
            for child, slice_ in zip(children, per_child.root, strict=False):
                child.add_charactor_trace(CharacterTrace(start=trace.start, interpolates=slice_))
        logger.debug(f"Assigned {assigned} character chain slice(s) across {len(children)} child(ren)")

    async def compose_scene(
        self,
        ctx: SceneContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> Scene | None:
        """Compose a scene end to end: before, generate, after, then post-process; returns None when generation fails."""
        ctx = await self.before_compose_scene(ctx, **kwargs)
        scene = await self.generate_scene(ctx, send_to, **kwargs)
        ctx = await self.after_compose_scene(ctx, **kwargs)

        if scene is None:
            return None
        return await self.post_process_scene(ctx, scene, **kwargs)
