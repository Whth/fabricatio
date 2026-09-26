"""Shared builders for the fabricatio-novel test modules."""

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

from fabricatio_character.models.character import CharacterCard
from fabricatio_core import Role
from fabricatio_mock import make_test_role
from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.models.context.chapter import ChapterContext, RagChapterContext
from fabricatio_novel.models.context.log import ContextEntry, ContextLog, EntryKind
from fabricatio_novel.models.context.novel import NovelContext, RagNovelContext
from fabricatio_novel.models.context.rag import RagRetrieval, RagStoryContext
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext

if TYPE_CHECKING:
    from fabricatio_novel.models.refusal import SceneRefusalScopedConfig


def unguarded[RoleT: Role](role: RoleT) -> RoleT:
    """Let a role's scenes pass the refusal guard whatever comes back.

    The guard reads a reply against its scene's word budget, so a fixture that scripts a
    two-word scene to exercise prefixes, hooks or assembly reads as a refusal there and
    gets asked again. Collapsing both ratio thresholds to zero keeps every reply; the
    guard's own behaviour is covered by ``test_novel_refusal``.

    Args:
        role: A role carrying ``SceneCompose`` and its refusal settings.

    Returns:
        RoleT: The same role, for chaining into the call under test.
    """
    knobs = cast("SceneRefusalScopedConfig", role)
    knobs.refusal_ratio_floor = 0.0
    knobs.refusal_ratio_accept = 0.0
    return role


def unguarded_role(*capabilities: type[object], name: str = "novel_role") -> Role:
    """Build a novel role whose scenes the refusal guard keeps whatever comes back.

    Args:
        *capabilities: Extra mixins to compose on top of ``NovelCompose``, e.g. a RAG
            capability a test monkeypatches methods on.
        name: Name given to the role instance.
    """
    return unguarded(make_test_role(NovelCompose, *capabilities, name=name))


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
    return ContextLog(entries=(ContextEntry(kind=EntryKind.SCENE_CONTENT, title=title, body=body),))


BENCH_OUTLINE = "A lighthouse keeper chases a storm that never lands."
"""Outline of the synthetic staged run the benchmark tests score."""


SCENE_PROSE = (
    "He left before the bells, and the pass took him the way water takes a stone. "
    "The road narrowed under the pines until the last of the town fell out of sight behind him, "
    "and for a while there was only the sound of his own steps and the wind moving through the branches. "
    "Snow had come down in the night and held the shape of every rut and stone, so that walking was a "
    "matter of guessing where the ground had been. He counted the switchbacks because counting kept the "
    "cold at arm's length. At the third turn the valley opened, and the river showed itself far below, "
    "grey and slow between its banks. He stopped long enough to fix the ford in his mind, then went on, "
    "because stopping was the one thing the winter could not forgive. By the time the light failed he had "
    "put the whole of the lower road behind him and found the shelter he had been told about, a stone wall "
    "against a rock face with a fire pit someone had kept swept. He ate what he had, laid his coat over his "
    "legs, and slept the way travellers do, in pieces, waking to the sound of the river every hour."
)
"""A scene's worth of prose: over the budgets the mocked plans hand a scene, so the refusal guard reads it as prose."""


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
    story: StoryContext
    if not with_docs:
        story = StoryContext.create(
            BENCH_OUTLINE, language="English", title=spec.title, description=spec.description
        ).set_writing_styles(list(spec.styles))
    else:
        story = (
            RagStoryContext.seal(
                StoryContext.create(BENCH_OUTLINE, language="English", title=spec.title, description=spec.description),
                RagRetrieval(),
            )
            .set_writing_styles(list(spec.styles))
            .add_retrieved_styles(list(spec.docs))
        )
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
    novel_docs: tuple[str, ...] = (),
) -> Path:
    """Persist a synthetic staged run for the benchmark tests and return its directory.

    The plan stage carries planned styles only — no retrieved documents, no
    composed prose — like the real planning snapshot. The prose stage carries
    the documents on each story's ``retrieved_styles`` behind a RAG seal, plus
    the novel's own ``novel_docs`` on the sealed root, and the scorecard
    restores the seals by reloading the snapshot as ``RagNovelContext``.
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
        if novel_docs and with_docs:
            # Seal the root with its chapter already in place, then promote the
            # chapter — the order the staged pipeline seals at, which leaves the
            # snapshot reloading as RagNovelContext.
            novel = RagNovelContext.seal(novel, RagRetrieval()).add_retrieved_styles(list(novel_docs))
            novel.add_context(RagChapterContext.model_validate(vars(chapter)))
        else:
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
