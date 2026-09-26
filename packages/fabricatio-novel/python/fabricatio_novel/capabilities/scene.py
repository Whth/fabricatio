"""Scene composition capabilities: rendering requirements and generating scene content."""

from abc import ABC
from typing import TYPE_CHECKING, Unpack, cast

if TYPE_CHECKING:
    from collections.abc import Awaitable

from fabricatio_character.capabilities.character import CharacterCompose
from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import SMOL, TASK, word_count
from fabricatio_core.utils import first_available, override_kwargs

from fabricatio_novel.config import novel_config
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.refusal import SceneRefusalScopedConfig, SceneRefusedError
from fabricatio_novel.models.scene import Scene
from fabricatio_novel.utils import strip_overlapping_prefix


class SceneCompose[CTX: SceneContext](SceneRefusalScopedConfig, CharacterCompose, ABC):
    """This class contains the capabilities for the scene."""

    async def before_compose_scene_context(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> CTX:
        """Identity hook invoked before composing a scene; may mutate the context.

        ``send_to`` is the routing group the run's calls use, so a hook that reaches
        the model on its own routes it like the rest of the run.
        """
        return ctx

    async def after_compose_scene_context(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> CTX:
        """Identity hook invoked after generating a scene; may mutate the context.

        ``send_to`` is the routing group the run's calls use, so a hook that reaches
        the model on its own routes it like the rest of the run.
        """
        return ctx

    async def post_process_scene(self, ctx: SceneContext, scene: Scene, **kwargs: Unpack[LLMKwargs]) -> Scene:
        """Identity hook invoked on the composed scene; may transform and return the scene."""
        return scene

    async def prepare_scene_requirement(
        self,
        ctx: CTX,
        **kwargs: Unpack[LLMKwargs],
    ) -> str:
        """Render the scene requirement prompt from the scene context.

        Overriding capabilities may extend the rendered requirement, for
        example by appending writing style references. The chapter-opening flag
        comes off the context's prefix log, so the prompt can say when this
        scene starts its chapter instead of continuing the text above it.
        """
        return TEMPLATE_MANAGER.render_template(
            novel_config.scene_requirement_template,
            {
                "title": ctx.title,
                "description": ctx.description,
                "expected_word_count": ctx.expected_word_count,
                "writing_styles": ctx.writing_styles,
                "writing_constraints": ctx.writing_constraints,
                "characters": ctx.dump_characters(),
                "cast": ctx.cast,
                "language": ctx.language,
                "skills": ctx.skill_section(),
                "novel_so_far": ctx.prefix_log.render(),
                "chapter_opening": ctx.is_chapter_opening(),
            },
        )

    async def judge_scene_reply(self, ctx: SceneContext, content: str, **kwargs: Unpack[LLMKwargs]) -> bool:
        """Judge whether a scene's reply is the scene itself or a refusal.

        The reply's word count satisfaction against the scene's planned budget decides
        the clear cases: below the floor it is a refusal, at or above the accept ratio
        it is prose, and no judge is asked. Only a satisfaction in between — where a
        merely terse scene and a long refusal both land — is put to a judge, one yes/no
        verdict per reply through :meth:`ajudge` on the ``SMOL`` tier, the same cheap
        completion the other mechanical judgements ride. A scene with no planned budget
        has no ratio to read and goes to the judge directly. A verdict the judge cannot
        give — ``ajudge`` returns ``None`` when its answer never parses — counts as a
        refusal: a reply nobody could vouch for is not one to write into the novel.

        Args:
            ctx (SceneContext): the scene the reply belongs to; its ``expected_word_count`` is the budget.
            content (str): the reply to judge.
            **kwargs (Unpack[LLMKwargs]): the LLM kwargs of the generation call, for subclasses
                that judge by more than the budget.

        Returns:
            bool: True when the reply is the scene's prose, False when it is a refusal.
        """
        floor = first_available(
            (self.refusal_ratio_floor, novel_config.scene_refusal_ratio_floor),
            "the refusal floor is unset: set refusal_ratio_floor on the role or scene_refusal_ratio_floor in [ext.novel]",
        )
        accept = first_available(
            (self.refusal_ratio_accept, novel_config.scene_refusal_ratio_accept),
            "the refusal accept ratio is unset: set refusal_ratio_accept on the role or scene_refusal_ratio_accept in [ext.novel]",
        )
        ratio = word_count(content) / ctx.expected_word_count if ctx.expected_word_count else None
        if ratio is not None:
            if ratio < floor:
                logger.warn(f"Scene '{ctx.title}' came back at {ratio:.2f} of its word budget; reading it as a refusal")
                return False
            if ratio >= accept:
                return True
        refused = await self.ajudge(
            f"A scene of the novel was requested.\nTitle: {ctx.title}\nDescription: {ctx.description}\n"
            f"Planned length: {ctx.expected_word_count or 'unstated'} words\n\nThe model answered:\n{content}",
            # The judge is asked whether the scene is there, not whether the answer "refuses":
            # a refusal-shaped question reads explicit prose as a refusal (probed against the
            # SMOL tier on a real run's refusal and its prose), while presence separates them.
            affirm_case="the requested scene is missing from the answer",
            deny_case="the answer contains the requested scene's prose",
            send_to=SMOL,
        )
        ratio_text = f"{ratio:.2f}" if ratio is not None else "no"
        verdict = "prose" if refused is False else "a refusal" if refused else "no verdict, which reads as a refusal"
        logger.info(f"Scene '{ctx.title}' at {ratio_text} of its word budget was judged {verdict}")
        return refused is False

    async def generate_scene_context(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> CTX:
        """Generate the scene content via the LLM.

        Renders the scene requirement, asks the LLM for the scene text, and stores the
        content on the context. Returns the composed context.

        A reply that reads as a refusal — see :meth:`judge_scene_reply` — is asked
        again, up to ``refusal_max_retries`` times: the retries bypass the cache read
        so the deployment is re-asked instead of replaying the refusal that is already
        stored for that prompt, while the answer that replaces it is stored in its
        turn. A scene refused on every attempt fails the run instead of being written
        down; the refusal text never reaches the context, so it cannot leak into the
        chapter, the prefix log or the EPUB.

        Raises:
            SceneRefusedError: every attempt read as a refusal; the run cannot go on.
            ValueError: the overlap stripping left no prose; an empty scene would be
                serialized into the chapter, the export and the EPUB unnoticed.
        """
        logger.debug(f"Generating scene '{ctx.title}'")
        requirement = await self.prepare_scene_requirement(ctx, **kwargs)
        logger.debug(f"Scene '{ctx.title}' requirement rendered ({len(requirement)} chars)")

        retries = first_available(
            (self.refusal_max_retries, novel_config.scene_refusal_max_retries),
            "the refusal retries are unset: set refusal_max_retries on the role or scene_refusal_max_retries in [ext.novel]",
        )
        for lap in range(retries + 1):
            # The refusal settings' extra ScopedConfig base widens ty's overload
            # resolution for `aask` into a union of every declared return, so the
            # awaited shape is named here rather than inferred.
            content = await cast("Awaitable[str]", self.aask(requirement, send_to=send_to, **kwargs))
            if await self.judge_scene_reply(ctx, content, **kwargs):
                break
            if lap == retries:
                raise SceneRefusedError(
                    f"Scene '{ctx.title}' read as a refusal on every one of its {retries + 1} attempt(s) "
                    f"({word_count(content)} words against {ctx.expected_word_count} planned); a refusal is not "
                    f"prose, so the run stops here: {content[:200]}"
                )
            logger.warn(f"Scene '{ctx.title}' read as a refusal; asking again ({lap + 2}/{retries + 1})")
            kwargs = override_kwargs(kwargs, no_cache=True, no_store=False)

        previous = "\n".join(entry.body for entry in ctx.prefix_log.entries if entry.kind.is_scene_content())
        content = strip_overlapping_prefix(
            content,
            previous,
            min_chars=novel_config.scene_overlap_min_chars,
            max_ratio=novel_config.scene_overlap_max_ratio,
        )
        if not content.strip():
            raise ValueError(f"Scene '{ctx.title}' produced no prose; empty scenes are never serialized")

        ctx.set_content(content)
        return ctx

    async def prepare_story(
        self,
        ctx: StoryContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> None:
        """Prepare the story before its scenes are planned.

        Identity hook; retrieval capabilities (e.g. RAG) override it to
        gather style references held on the story context for planning.
        """

    async def compose_scene(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> Scene | None:
        """Compose a scene end to end: before, generate, after, then post-process; returns None when generation fails."""
        ctx = await self.before_compose_scene_context(ctx, send_to=send_to, **kwargs)
        ctx = await self.generate_scene_context(ctx, send_to, **kwargs)
        ctx = await self.after_compose_scene_context(ctx, send_to=send_to, **kwargs)

        scene = Scene.from_context(ctx)
        logger.info(
            f"Scene '{scene.title}' composed ({word_count(scene.content)} words, word count satisfaction: {scene.satisfy_ratio()}",
        )
        return await self.post_process_scene(ctx, scene, **kwargs)
