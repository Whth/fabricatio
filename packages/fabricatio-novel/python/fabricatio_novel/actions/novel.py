"""Staged novel composition actions with per-stage persistence.

Each stage action runs one pipeline phase through the mixed-in capability
and then persists a whole-tree snapshot of the novel context, so a wrong
result can be traced back to the stage that produced it.
"""

from pathlib import Path
from typing import Any, ClassVar, Dict

from fabricatio_core import logger
from fabricatio_core.models.action import OUTPUT_KEY, Action
from fabricatio_core.rust import TASK
from fabricatio_core.utils import ok

from fabricatio_novel.capabilities.chapter import ChapterCompose
from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.capabilities.rag import RAGCompose
from fabricatio_novel.capabilities.story import StoryCompose
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.novel import Novel
from fabricatio_novel.models.series_book import SeriesBible

__all__ = [
    "AssembleStage",
    "ChapterPlanStage",
    "CharactersStage",
    "DumpEpubStage",
    "InitNovelContext",
    "MetadataStage",
    "RagScenePlanStage",
    "RagSceneWriteStage",
    "ScenePlanStage",
    "SceneWriteStage",
    "StageAction",
    "StoryPlanStage",
]


class StageAction(Action):
    """Base action for staged novel phases: run the phase, then snapshot the whole tree."""

    stage: ClassVar[str] = ""
    """Stage name used to build the snapshot directory (e.g. ``02_metadata``)."""

    async def snapshot(self, novel_ctx: NovelContext, cxt: Dict[str, Any]) -> None:
        """Persist the whole novel context tree into the stage's snapshot directory."""
        persist_dir = cxt.get("persist_dir")
        if not persist_dir:
            return
        stage_dir = Path(persist_dir) / f"stage_{self.stage}"
        stage_dir.mkdir(parents=True, exist_ok=True)
        novel_ctx.persist(stage_dir)
        logger.debug(f"Persisted stage '{self.stage}' snapshot to {stage_dir}")


class InitNovelContext(StageAction):
    """Build the novel context from the task init context and persist the starting state."""

    output_key: str = "novel_ctx"
    stage: ClassVar[str] = "01_init"

    async def _execute(self, *_: Any, **cxt: Any) -> NovelContext:
        outline = ok(cxt.get("novel_outline"), "`novel_outline` is required in the task init context")
        ctx = NovelContext.create(outline, cxt.get("novel_language"))
        if constraint := cxt.get("writing_constraint"):
            ctx.set_writing_constraint(str(constraint))
        if bible_path := cxt.get("bible_path"):
            ctx.set_series_bible(SeriesBible.model_validate_json(Path(bible_path).read_text(encoding="utf-8")))
        ctx.set_rag_query(str(cxt.get("rag_query") or "")).set_rag_limit(int(cxt.get("rag_limit") or 15))
        await self.snapshot(ctx, cxt)
        return ctx


class MetadataStage(StageAction, NovelCompose):
    """Propose the novel metadata plan and adopt it onto the context."""

    output_key: str = "metadata_ok"
    stage: ClassVar[str] = "02_metadata"

    async def _execute(self, novel_ctx: NovelContext, *_: Any, **cxt: Any) -> bool:
        planned = await self.propose_novel_metadata(novel_ctx, send_to=cxt.get("send_to", TASK))
        await self.snapshot(novel_ctx, cxt)
        return planned


class CharactersStage(StageAction, NovelCompose):
    """Create the character traces from the bible roster and interpolate them over the outline."""

    output_key: str = "characters_ok"
    stage: ClassVar[str] = "03_characters"

    async def _execute(self, novel_ctx: NovelContext, *_: Any, **cxt: Any) -> bool:
        await self.prepare_character_span(novel_ctx, send_to=cxt.get("send_to", TASK))
        await self.snapshot(novel_ctx, cxt)
        return True


class ChapterPlanStage(StageAction, NovelCompose):
    """Plan chapters, broadcast the bible, and split character slices per chapter."""

    output_key: str = "chapter_plan_ok"
    stage: ClassVar[str] = "04_chapter_plans"

    async def _execute(self, novel_ctx: NovelContext, *_: Any, **cxt: Any) -> bool:
        send_to = cxt.get("send_to", TASK)
        planned = await self.plan_chapters_phase(novel_ctx, send_to=send_to)
        if planned:
            novel_ctx.broadcast_settings_bible()
            await self.split_character_slices(novel_ctx, novel_ctx.chapter_context, send_to=send_to)
        await self.snapshot(novel_ctx, cxt)
        return planned


class StoryPlanStage(StageAction, ChapterCompose):
    """Interpolate and plan the stories of every chapter, then split per-story slices."""

    output_key: str = "story_plan_ok"
    stage: ClassVar[str] = "05_story_plans"

    async def _execute(self, novel_ctx: NovelContext, *_: Any, **cxt: Any) -> bool:
        send_to = cxt.get("send_to", TASK)
        for chapter in novel_ctx.chapter_context:
            if not await self.plan_stories_phase(chapter, send_to=send_to):
                await self.snapshot(novel_ctx, cxt)
                return False
            chapter.broadcast_settings_bible()
            await self.split_character_slices(chapter, chapter.story_context, send_to=send_to)
        await self.snapshot(novel_ctx, cxt)
        return True


class ScenePlanStage(StageAction, StoryCompose):
    """Interpolate and plan the scenes of every story."""

    output_key: str = "scene_plan_ok"
    stage: ClassVar[str] = "06_scene_plans"

    async def _execute(self, novel_ctx: NovelContext, *_: Any, **cxt: Any) -> bool:
        send_to = cxt.get("send_to", TASK)
        for chapter in novel_ctx.chapter_context:
            for story in chapter.story_context:
                if not await self.plan_scenes_phase(story, send_to=send_to):
                    await self.snapshot(novel_ctx, cxt)
                    return False
        await self.snapshot(novel_ctx, cxt)
        return True


class SceneWriteStage(StageAction, StoryCompose):
    """Compose every scene serially in prefix order across the whole novel."""

    output_key: str = "scenes_ok"
    stage: ClassVar[str] = "07_scenes"

    async def _execute(self, novel_ctx: NovelContext, *_: Any, **cxt: Any) -> bool:
        send_to = cxt.get("send_to", TASK)
        for chapter in novel_ctx.iter_prefixed_contexts():
            chapter.broadcast_settings_bible()
            for story in chapter.iter_prefixed_contexts():
                await self.prepare_scene_write(story, send_to=send_to)
                if not await self.compose_scenes_phase(story, send_to=send_to):
                    await self.snapshot(novel_ctx, cxt)
                    return False
        await self.snapshot(novel_ctx, cxt)
        return True


class AssembleStage(StageAction, NovelCompose):
    """Materialize the composed context tree as a Novel."""

    output_key: str = "novel"
    stage: ClassVar[str] = "08_novel"

    async def _execute(self, novel_ctx: NovelContext, *_: Any, **cxt: Any) -> Novel:
        novel = self.assemble_novel(novel_ctx)
        await self.snapshot(novel_ctx, cxt)
        return novel


class DumpEpubStage(Action):
    """Dump the composed novel to JSON and EPUB, returning the EPUB path."""

    output_key: str = OUTPUT_KEY
    stage: ClassVar[str] = "09_epub"

    async def _execute(self, novel: Novel, *_: Any, **cxt: Any) -> Path:
        persist_dir = Path(ok(cxt.get("persist_dir"), "`persist_dir` is required in the task init context"))
        persist_dir.mkdir(parents=True, exist_ok=True)
        novel.persist(persist_dir)
        output = cxt.get("output_path")
        epub_path = persist_dir / output if output else persist_dir / "novel.epub"
        novel.dump_epub(epub_path, font=cxt.get("font"), cover=cxt.get("cover"))
        logger.info(f"EPUB dumped to {epub_path}")
        return epub_path


class RagScenePlanStage(ScenePlanStage, RAGCompose):
    """Scene planning with story-level writing style retrieval."""


class RagSceneWriteStage(SceneWriteStage, RAGCompose):
    """Scene write preparation with the story's style digest."""
