"""Shared builders for the fabricatio-novel test modules."""

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from fabricatio_character.models.character import CharacterCard
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.log import ContextEntry, ContextLog
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext


def card(name: str = "Hero", look: str = "tall") -> CharacterCard:
    """Build a default protagonist CharacterCard for tests."""
    return CharacterCard(
        name=name,
        roles=["protagonist"],
        activated_role="protagonist",
        look=look,
        act="brave",
        want="seek truth",
        flaw="stubborn",
        where="starting village",
        condition="healthy",
        mood="determined",
        metric={},
    )


def prefix_log(body: str, *, title: str = "S1") -> ContextLog:
    """Build a one-entry scene-content prefix log for tests."""
    return ContextLog(entries=(ContextEntry(kind="scene_content", title=title, body=body),))


BENCH_OUTLINE = "A lighthouse keeper chases a storm that never lands."
"""Outline of the synthetic staged run the benchmark tests score."""


@dataclass(frozen=True, slots=True)
class SceneSpec:
    """One scene of a synthetic run: its plan text, composed prose and word budget.

    The default budget is the size the fixture prose is written to: a scene is
    only reported as truncated when it falls below half of it.
    """

    title: str
    description: str
    content: str
    target: int = 15


@dataclass(frozen=True, slots=True)
class StorySpec:
    """One story of a synthetic run: its scenes, the styles its plan set, and the documents it retrieved."""

    title: str
    description: str
    scenes: tuple[SceneSpec, ...]
    styles: tuple[str, ...] = ()
    docs: tuple[str, ...] = ()


def _story_context(spec: StorySpec, *, with_docs: bool, with_content: bool) -> StoryContext:
    """Build one story context, optionally carrying its retrieved documents and composed scenes."""
    story = StoryContext.create(
        BENCH_OUTLINE, language="English", title=spec.title, description=spec.description
    ).set_writing_styles([*spec.styles, *spec.docs] if with_docs else list(spec.styles))
    for scene in spec.scenes:
        context = SceneContext.create(
            BENCH_OUTLINE, language="English", title=scene.title, description=scene.description
        ).expect_(scene.target)
        if with_content:
            context.set_content(scene.content)
        story.add_context(context)
    return story


def benchmark_run(
    root: Path,
    specs: tuple[StorySpec, ...],
    *,
    name: str = "20260101-000000",
    chapter_file: bool = True,
) -> Path:
    """Persist a synthetic staged run for the benchmark tests and return its directory.

    The plan stage carries the story styles without the retrieved documents and no
    composed prose — like the real planning snapshot — so a scorecard can tell
    reference documents apart from planned styles.
    """
    run_dir = root / name
    plan_stage = run_dir / "stage_06_story_plans"
    prose_stage = run_dir / "stage_08_scenes"
    plan_stage.mkdir(parents=True)
    prose_stage.mkdir()
    for with_docs, with_content, stage in ((False, False, plan_stage), (True, True, prose_stage)):
        novel = NovelContext.create(
            BENCH_OUTLINE, language="English", title="Bench Novel", description="A synthetic run."
        ).expect_(sum(scene.target for spec in specs for scene in spec.scenes))
        chapter = ChapterContext.create(
            BENCH_OUTLINE, language="English", title="Chapter One", description="The framing chapter."
        )
        for spec in specs:
            chapter.add_context(_story_context(spec, with_docs=with_docs, with_content=with_content))
        novel.add_context(chapter)
        novel.persist(stage)
    # Fixed mtimes keep the measured duration stable: run-to-run timing noise would
    # otherwise show up as a regression in every scorecard comparison.
    base = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC).timestamp()
    for offset, stage in ((0.0, plan_stage), (90.0, prose_stage)):
        for snapshot in stage.glob("*.json"):
            os.utime(snapshot, (base + offset, base + offset))
    if chapter_file:
        chapters = run_dir / "chapters"
        chapters.mkdir()
        (chapters / "01.txt").write_text(
            "\n\n".join(scene.content for spec in specs for scene in spec.scenes), encoding="utf-8"
        )
    return run_dir
