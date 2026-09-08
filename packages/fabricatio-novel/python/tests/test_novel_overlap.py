"""Overlapping-prefix stripping tests for serial scene generation."""

import asyncio

import pytest
from _support import NovelRole, prefix_log
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.utils import strip_overlapping_prefix

_TAIL = "and the harbor lights died one by one as the ferry pulled away."
_REMAINDER = (
    "Then the bell rang. The deck tilted under his boots, and the last boarding"
    " call dissolved into the fog behind him before he could turn around."
)


def _two_scene_ctx() -> NovelContext:
    """Build a one-chapter, one-story context holding two empty scenes."""
    ctx = NovelContext.create("The hero seeks his father.", language="English")
    chapter_ctx = ChapterContext(title="Ch1", description="The hero sets out.")
    story_ctx = StoryContext(title="St1", description="The departure.")
    for title in ("S1", "S2"):
        story_ctx.child_contexts.append(
            SceneContext(title=title, description=f"{title} prose.", expected_word_count=20)
        )
    chapter_ctx.child_contexts.append(story_ctx)
    ctx.child_contexts.append(chapter_ctx)
    return ctx


def test_strips_exact_overlapping_prefix() -> None:
    """Assert a re-emitted previous-scene tail is removed from the new content."""
    content = f"{_TAIL}\n\n{_REMAINDER}"
    assert strip_overlapping_prefix(content, f"Earlier prose.\n{_TAIL}", min_chars=40) == _REMAINDER


def test_strips_whitespace_reflowed_overlap() -> None:
    """Assert the match survives the model reflowing the duplicated paragraphs."""
    reflowed = _TAIL.replace(" ", "\n\n")
    content = f"{reflowed}{_REMAINDER}"
    assert strip_overlapping_prefix(content, f"Earlier prose.\n{_TAIL}", min_chars=40) == _REMAINDER


def test_keeps_short_echoes_below_threshold() -> None:
    """Assert overlaps shorter than min_chars are kept — a name or phrase is legitimate."""
    content = "the ferry pulled away. Then the bell rang."
    assert strip_overlapping_prefix(content, f"Earlier prose.\n{_TAIL}", min_chars=40) == content


def test_keeps_content_when_overlap_is_huge() -> None:
    """Assert a near-total re-emission is kept untouched instead of leaving a stump."""
    content = f"{_TAIL}\nThen the bell rang softly."
    previous = f"Earlier prose.\n{_TAIL}"
    assert strip_overlapping_prefix(content, previous, min_chars=40, max_ratio=0.6) == content


def test_noop_without_previous_prose() -> None:
    """Assert empty previous prose and short content pass through unchanged."""
    content = "He left."
    assert strip_overlapping_prefix(content, "", min_chars=40) == content
    assert strip_overlapping_prefix("", _TAIL, min_chars=40) == ""


def test_compose_scenes_phase_strips_and_propagates_stripped_prose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Assert the stripped content is what the log records for later scenes to see."""
    captured: list[str] = []

    async def fake_ageneric_string(self: object, question: str, **kwargs: object) -> str | None:
        captured.append(str(question))
        if len(captured) == 1:
            return f"The ropes groaned. {_TAIL}"
        return f"{_TAIL}\n{_REMAINDER}"

    monkeypatch.setattr(NovelRole, "ageneric_string", fake_ageneric_string)
    role = NovelRole(name="writer")
    ctx = _two_scene_ctx()
    story_ctx = ctx.child_contexts[0].child_contexts[0]
    story_ctx.set_prefix_log(prefix_log("Chapter One.", title="Ch1"))
    story_ctx.set_charactor_spans([])

    ok = asyncio.run(role.compose_scenes_phase(story_ctx))

    assert ok is True
    first, second = (scene.content for scene in story_ctx.child_contexts)
    assert first == f"The ropes groaned. {_TAIL}"
    assert second == _REMAINDER
    later_prose = [entry.body for entry in story_ctx.child_contexts[1].prefix_log.entries]
    assert later_prose == ["Chapter One.", first]
