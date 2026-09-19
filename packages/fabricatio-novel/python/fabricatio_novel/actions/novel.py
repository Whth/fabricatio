"""Staged novel composition actions with per-stage persistence.

Each stage runs one segment of the ``compose_novel`` chain through its
mixed-in capability, then persists a whole-tree snapshot of the novel context,
so a wrong result can be traced back to the stage that produced it. The stages
follow the chain's shape: stage names mirror the chain phase they wrap, and the
lifecycle hooks fire at their chain positions — the level's before-context hook
brackets the planning segments, the after-context and post-process hooks close
each unit out after its segments complete — so overriding a hook on a stage
customizes the staged run exactly like it customizes the programmatic chain.
"""

from abc import ABC
from pathlib import Path
from typing import Any, ClassVar

from fabricatio_core import logger
from fabricatio_core.models.action import OUTPUT_KEY, Action
from fabricatio_core.rust import TASK
from fabricatio_core.utils import ok

from fabricatio_novel.capabilities.bible import BibleCompose
from fabricatio_novel.capabilities.chapter import ChapterCompose
from fabricatio_novel.capabilities.illustration import IllustrateScenes
from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.capabilities.rag import RAGChapterCompose, RAGNovelCompose
from fabricatio_novel.capabilities.story import StoryCompose
from fabricatio_novel.models.chapter import Chapter
from fabricatio_novel.models.context.chapter import RagChapterContext
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.novel import Novel
from fabricatio_novel.models.series_book import SeriesBible
from fabricatio_novel.models.story import Story

__all__ = [
    "AssembleNovelStage",
    "ComposeScenesStage",
    "DumpNovelStage",
    "IllustrateNovelStage",
    "InitNovelContext",
    "PlanChaptersStage",
    "PlanScenesStage",
    "PlanStoriesStage",
    "PrepareCharacterSpanStage",
    "ProposeNovelMetadataStage",
    "ProposeSettingBibleStage",
    "RagComposeScenesStage",
    "RagInitNovelContext",
    "RagPlanChaptersStage",
    "RagPlanScenesStage",
    "RagPlanStoriesStage",
    "StageAction",
]


class StageAction(Action, ABC):
    """Base action for staged novel phases: run the phase, then snapshot the whole tree."""

    stage: ClassVar[str] = ""
    """Stage name used to build the snapshot directory (e.g. ``02_metadata``)."""

    async def snapshot(self, novel_ctx: NovelContext, cxt: dict[str, Any]) -> None:
        """Persist the whole novel context tree into the stage's snapshot directory."""
        persist_dir = cxt.get("persist_dir")
        if not persist_dir:
            return
        stage_dir = Path(persist_dir) / f"stage_{self.stage}"
        stage_dir.mkdir(parents=True, exist_ok=True)
        novel_ctx.persist(stage_dir)
        logger.debug(f"Persisted stage '{self.stage}' snapshot to {stage_dir}")


class InitNovelContext(StageAction, NovelCompose):
    """Build the novel context from the task init context, fire ``before_compose_novel_context``, persist."""

    output_key: str = "novel_ctx"
    stage: ClassVar[str] = "01_init"

    async def init_novel_context(
        self,
        outline: str,
        *,
        language: str | None = None,
        constraint: str = "",
        bible_path: Path | None = None,
        send_to: str | None = TASK,
    ) -> NovelContext:
        """Build the root from the run's settings and fire the before hook on it.

        The hook's return replaces the root — it is where a RAG run seals the
        context class itself and fetches the references the planning prompts
        render — so the caller snapshots exactly what the hook handed back.
        """
        ctx = NovelContext.create(outline, language=language)
        if constraint:
            ctx.set_writing_constraints([constraint])
        if bible_path is not None:
            ctx.set_series_bible(SeriesBible.model_validate_json(bible_path.read_text(encoding="utf-8")))
        ctx.seed_bible_prefix()
        return await self.before_compose_novel_context(ctx, send_to=send_to)

    async def _execute(self, *_: Any, **cxt: Any) -> NovelContext:
        ctx = await self.init_novel_context(
            ok(cxt.get("novel_outline"), "`novel_outline` is required in the task init context"),
            language=cxt.get("novel_language"),
            constraint=cxt.get("writing_constraint") or "",
            bible_path=cxt.get("bible_path"),
            send_to=cxt.get("send_to", TASK),
        )
        await self.snapshot(ctx, cxt)
        return ctx


class RagInitNovelContext(InitNovelContext, RAGNovelCompose):
    """Init stage of a RAG run: the before hook seals the root and fetches the novel's style references.

    The stage body stays the base one — build, hook, snapshot — because the RAG
    work lives in the hook the mixin overrides, so the single snapshot the base
    writes already holds the sealed root with its references.
    """

    ctx_override: ClassVar[bool] = True


class ProposeNovelMetadataStage(StageAction, NovelCompose):
    """Propose the novel metadata plan and adopt it onto the context."""

    output_key: str = "metadata_ok"
    stage: ClassVar[str] = "02_metadata"

    async def _execute(self, novel_ctx: NovelContext, *_: Any, **cxt: Any) -> bool:
        planned = await self.propose_novel_metadata(novel_ctx, send_to=cxt.get("send_to", TASK))
        await self.snapshot(novel_ctx, cxt)
        return planned


class ProposeSettingBibleStage(StageAction, BibleCompose):
    """Propose the setting bible from the outline; skipped when the context already holds one."""

    output_key: str = "bible_ok"
    stage: ClassVar[str] = "03_bible"

    async def _execute(self, novel_ctx: NovelContext, *_: Any, **cxt: Any) -> bool:
        bible = novel_ctx.series_bible
        if bible is not None and not bible.is_empty():
            logger.debug("Setting bible already present; skipping proposal")
            await self.snapshot(novel_ctx, cxt)
            return True
        proposed = await self.compose_setting_bible(
            novel_ctx.outline, novel_ctx.language, send_to=cxt.get("send_to", TASK)
        )
        if proposed is None:
            logger.error("Setting bible proposal failed; aborting novel generation")
            await self.snapshot(novel_ctx, cxt)
            return False
        novel_ctx.set_series_bible(proposed).seed_bible_prefix()
        logger.info("Proposed the setting bible from the outline")
        await self.snapshot(novel_ctx, cxt)
        return True


class PrepareCharacterSpanStage(StageAction, NovelCompose):
    """Propose the novel roster character spans from the bible; skipped when the bible is empty."""

    output_key: str = "characters_ok"
    stage: ClassVar[str] = "04_characters"

    async def _execute(self, novel_ctx: NovelContext, *_: Any, **cxt: Any) -> bool:
        await self.prepare_character_span(novel_ctx, send_to=cxt.get("send_to", TASK))
        await self.snapshot(novel_ctx, cxt)
        return True


class PlanChaptersStage(StageAction, NovelCompose):
    """Plan chapters and draft per-chapter character spans."""

    output_key: str = "chapter_plan_ok"
    stage: ClassVar[str] = "05_chapter_plans"

    async def _execute(self, novel_ctx: NovelContext, *_: Any, **cxt: Any) -> bool:
        send_to = cxt.get("send_to", TASK)
        planned = await self.plan_chapters_phase(novel_ctx, send_to=send_to)
        await self.snapshot(novel_ctx, cxt)
        return planned


class RagPlanChaptersStage(PlanChaptersStage, RAGNovelCompose):
    """Chapter planning of a RAG run: the novel's references reach the prompt and the chapters carry the RAG type.

    The stage body stays the base one — :meth:`RAGNovelCompose.plan_chapters_phase`
    renders the phase's prompt from the sealed root and promotes what it plans — so
    the snapshot already holds the chapters the later stages seal stories into.
    """


class PlanStoriesStage(StageAction, ChapterCompose):
    """Fire ``before_compose_chapter_context`` per chapter, then plan its stories and draft their spans."""

    output_key: str = "story_plan_ok"
    stage: ClassVar[str] = "06_story_plans"

    async def _execute(self, novel_ctx: NovelContext, *_: Any, **cxt: Any) -> bool:
        send_to = cxt.get("send_to", TASK)
        for chapter in novel_ctx.iter_prefixed_contexts():
            chapter_ctx = await self.before_compose_chapter_context(chapter, send_to=send_to)
            if not await self.plan_stories_phase(chapter_ctx, send_to=send_to):
                await self.snapshot(novel_ctx, cxt)
                return False
        await self.snapshot(novel_ctx, cxt)
        return True


class RagPlanStoriesStage(PlanStoriesStage, RAGChapterCompose):
    """Story planning with the RAG seal.

    :meth:`RAGChapterCompose.plan_stories_phase` seals each chapter's stories with
    the context-overridden retrieval settings right after they are planned;
    each sealed chapter is then promoted to
    :class:`~fabricatio_novel.models.context.chapter.RagChapterContext`, so the
    snapshot tree type-states that its stories are sealed, and the later scene
    stages only consume sealed story contexts.
    """

    ctx_override: ClassVar[bool] = True

    async def _execute(self, novel_ctx: NovelContext, *_: Any, **cxt: Any) -> bool:
        send_to = cxt.get("send_to", TASK)
        for index, chapter in enumerate(novel_ctx.child_contexts):
            chapter_ctx = await self.before_compose_chapter_context(chapter, send_to=send_to)
            if not await self.plan_stories_phase(chapter_ctx, send_to=send_to):
                await self.snapshot(novel_ctx, cxt)
                return False
            novel_ctx.child_contexts[index] = RagChapterContext.model_validate(vars(chapter_ctx))
        await self.snapshot(novel_ctx, cxt)
        return True


class PlanScenesStage(StageAction, StoryCompose):
    """Fire ``before_compose_story_context`` per story, then plan its scenes."""

    output_key: str = "scene_plan_ok"
    stage: ClassVar[str] = "07_scene_plans"

    async def _execute(self, novel_ctx: NovelContext, *_: Any, **cxt: Any) -> bool:
        send_to = cxt.get("send_to", TASK)
        for chapter in novel_ctx.iter_prefixed_contexts():
            for story in chapter.iter_prefixed_contexts():
                story_ctx = await self.before_compose_story_context(story, send_to=send_to)
                if not await self.plan_scenes_phase(story_ctx, send_to=send_to):
                    await self.snapshot(novel_ctx, cxt)
                    return False
        await self.snapshot(novel_ctx, cxt)
        return True


class ComposeScenesStage(StageAction, ChapterCompose):
    """Write every scene serially in prefix order, then close each story and chapter out.

    Mirrors the chain tail per unit: after a story's scenes are composed, its
    after-context hook fires and the story is assembled and handed to
    ``post_process_story``; once a chapter's stories are done, its after-context
    hook fires and the chapter is assembled and handed to
    ``post_process_chapter``. A ``None`` post-process return fails the stage,
    exactly like the chain's compose loops do.
    """

    output_key: str = "scenes_ok"
    stage: ClassVar[str] = "08_scenes"

    async def _execute(self, novel_ctx: NovelContext, *_: Any, **cxt: Any) -> bool:
        send_to = cxt.get("send_to", TASK)
        for chapter in novel_ctx.iter_prefixed_contexts():
            for story in chapter.iter_prefixed_contexts():
                await self.prepare_scene_write(story, send_to=send_to)
                if not await self.compose_scenes_phase(story, send_to=send_to):
                    await self.snapshot(novel_ctx, cxt)
                    return False
                story_ctx = await self.after_compose_story_context(story, send_to=send_to)
                story_artifact = Story.from_context(story_ctx)
                logger.info(
                    f"Story '{story_artifact.title}' composed ({len(story_artifact.scenes)} scene(s),"
                    f"  word count satisfaction: {story_artifact.satisfy_ratio()}",
                )
                if await self.post_process_story(story_ctx, story_artifact) is None:
                    await self.snapshot(novel_ctx, cxt)
                    return False
            chapter_ctx = await self.after_compose_chapter_context(chapter, send_to=send_to)
            chapter_artifact = Chapter.from_context(chapter_ctx)
            logger.info(
                f"Chapter '{chapter_artifact.title}' composed ({len(chapter_artifact.story)} story(s),"
                f"  word count satisfaction: {chapter_artifact.satisfy_ratio()}",
            )
            if await self.post_process_chapter(chapter_ctx, chapter_artifact) is None:
                await self.snapshot(novel_ctx, cxt)
                return False
        await self.snapshot(novel_ctx, cxt)
        return True


class AssembleNovelStage(StageAction, NovelCompose):
    """Fire ``after_compose_novel_context``, then materialize the composed context tree as a Novel."""

    output_key: str = "novel"
    stage: ClassVar[str] = "09_novel"

    async def _execute(self, novel_ctx: NovelContext, *_: Any, **cxt: Any) -> Novel:
        send_to = cxt.get("send_to", TASK)
        ctx = await self.after_compose_novel_context(novel_ctx, send_to=send_to)
        novel = self.assemble_novel(ctx)
        await self.snapshot(ctx, cxt)
        return novel


class DumpNovelStage(Action, NovelCompose):
    """Fire ``post_process_novel``, then export the novel to JSON plus EPUB and/or per-chapter texts.

    The hook call resolves polymorphically: plain workflows get the identity
    default, while the illustration variant (:class:`IllustrateNovelStage`)
    resolves it to :meth:`IllustrateScenes.post_process_novel`, so every scene
    is illustrated before the artifact is written.
    """

    output_key: str = OUTPUT_KEY

    async def _execute(self, novel_ctx: NovelContext, novel: Novel, *_: Any, **cxt: Any) -> Path:
        persist_dir = Path(ok(cxt.get("persist_dir"), "`persist_dir` is required in the task init context"))
        persist_dir.mkdir(parents=True, exist_ok=True)
        novel = await self.post_process_novel(
            novel_ctx,
            novel,
            persist_dir=persist_dir,
            send_to=cxt.get("send_to", TASK),
            illustration_choose_loras=cxt.get("illustration_choose_loras"),
            illustration_judge=cxt.get("illustration_judge"),
            illustration_judge_max_tries=cxt.get("illustration_judge_max_tries"),
        )
        fmt = str(cxt.get("format") or "epub")
        ok(fmt in ("epub", "txt", "both"), f"`format` must be 'epub', 'txt', or 'both', got '{fmt}'")
        output = cxt.get("output_path")
        epub_path = persist_dir / output if output else persist_dir / "novel.epub"
        texts_dir = persist_dir / "chapters"
        novel.persist(persist_dir)
        if fmt in ("epub", "both"):
            novel.dump_epub(epub_path, font=cxt.get("font"), cover=cxt.get("cover"))
            logger.info(f"EPUB dumped to {epub_path}")
        if fmt in ("txt", "both"):
            novel.dump_texts(texts_dir)
            logger.info(f"Chapter texts dumped to {texts_dir}")
        return texts_dir if fmt == "txt" else epub_path


class RagPlanScenesStage(PlanScenesStage, RAGChapterCompose):
    """Scene planning over stories already sealed by :class:`RagPlanStoriesStage`.

    Mixing in :class:`RAGChapterCompose` resolves :meth:`RAGChapterCompose.prepare_story`
    ahead of the plain implementation, so each sealed story's style
    references are retrieved before its scenes are planned.
    """


class RagComposeScenesStage(ComposeScenesStage, RAGChapterCompose):
    """Scene composition over stories already sealed by :class:`RagPlanScenesStage`."""


class IllustrateNovelStage(DumpNovelStage, IllustrateScenes):
    """Dump-stage variant whose ``post_process_novel`` resolves to per-scene illustration."""
