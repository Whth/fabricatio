"""Progressive-planning tests for fabricatio-novel: plans, word counts, outline grounding."""

from typing import List

import pytest
from _support import NovelRole, raw_value
from fabricatio_core.models.generic import ProposedAble
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_mock.models.mock_router import (
    Value,
    return_mixed_router_usage,
    return_model_json_router_usage,
)
from fabricatio_mock.utils import install_router_usage
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.plan import NovelPlan
from fabricatio_novel.models.series_book import SeriesBible


class TestNovelPlan:
    """Test suite for progressive planning of an empty context tree."""

    async def test_compose_novel_plans_empty_tree(self) -> None:
        """Assert compose_novel plans an empty context tree down to scenes and writes content."""
        role = NovelRole(name="novel_role")
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        meta = NovelPlan(
            title="The Search",
            description="A hero searching for his father.",
            expected_word_count=100,
            series_bible=SeriesBible(),
        )
        chapter_plans_json = [{"title": "Ch1", "description": "The hero sets out.", "weight": 1.0}]
        story_plans_json = [{"title": "St1", "description": "The departure.", "weight": 1.0}]
        scene_plans_json = [{"title": "S1", "description": "Leaving home.", "weight": 1.0}]
        responses = return_mixed_router_usage(
            Value(meta, "model"),
            Value(chapter_plans_json, "json"),
            Value(story_plans_json, "json"),
            Value(scene_plans_json, "json"),
            raw_value("He left."),
        )
        with install_router_usage(*responses):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        assert novel.title == "The Search"
        assert len(novel.chapter) == 1
        assert novel.chapter[0].title == "Ch1"
        assert novel.chapter[0].story[0].scenes[0].content == "He left."
        assert ctx.novel_plan is not None
        assert ctx.novel_plan.title == "The Search"
        assert ctx.chapter_context[0].chapter_plan is not None
        assert ctx.chapter_context[0].chapter_plan.title == "Ch1"
        assert ctx.chapter_context[0].story_context[0].story_plan is not None
        assert ctx.chapter_context[0].story_context[0].story_plan.title == "St1"
        assert ctx.chapter_context[0].story_context[0].scene_context[0].scene_plan is not None
        assert ctx.chapter_context[0].story_context[0].scene_context[0].scene_plan.title == "S1"
        assert ctx.chapter_context[0].story_context[0].scene_context[0].language == "English"

    async def test_compose_novel_allocates_writing_constraint_down_tree(self) -> None:
        """Assert the global constraint is generated and accumulated down to every scene."""
        role = NovelRole(name="novel_role")
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        ctx.set_writing_constraint("I hope the novel is first person view.")
        meta = NovelPlan(
            title="The Search",
            description="A hero searching for his father.",
            expected_word_count=100,
            writing_constraint="First person view throughout: narrate from the protagonist's perspective using I.",
            series_bible=SeriesBible(),
        )
        chapter_plans_json = [
            {
                "title": "Ch1",
                "description": "The hero sets out.",
                "weight": 1.0,
                "writing_constraint": "Keep first person during the road journey.",
            }
        ]
        story_plans_json = [{"title": "St1", "description": "The departure.", "weight": 1.0, "writing_constraint": ""}]
        scene_plans_json = [
            {
                "title": "S1",
                "description": "Leaving home.",
                "weight": 1.0,
                "writing_constraint": "Stay in the protagonist's head; no head-hopping.",
            }
        ]
        responses = return_mixed_router_usage(
            Value(meta, "model"),
            Value(chapter_plans_json, "json"),
            Value(story_plans_json, "json"),
            Value(scene_plans_json, "json"),
            raw_value("He left."),
        )
        with install_router_usage(*responses):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        chapter_ctx = ctx.chapter_context[0]
        story_ctx = chapter_ctx.story_context[0]
        scene_ctx = story_ctx.scene_context[0]
        # the generated global constraint replaces the author's raw intent
        assert ctx.writing_constraint == meta.writing_constraint
        # each level accumulates its own allocation on top of the parent's
        assert chapter_ctx.writing_constraint == (
            "First person view throughout: narrate from the protagonist's perspective using I.\n"
            "Keep first person during the road journey."
        )
        # a level without its own allocation inherits the parent's accumulated constraint
        assert story_ctx.writing_constraint == chapter_ctx.writing_constraint
        assert scene_ctx.writing_constraint == (
            "First person view throughout: narrate from the protagonist's perspective using I.\n"
            "Keep first person during the road journey.\n"
            "Stay in the protagonist's head; no head-hopping."
        )
        # the full accumulated chain reaches the scene's prose requirement
        requirement = await role.prepare_scene_requirement(scene_ctx)
        assert "## Writing Constraint" in requirement
        assert "First person view throughout" in requirement
        assert "no head-hopping" in requirement

    async def test_compose_novel_returns_none_when_plan_fails(self) -> None:
        """Assert compose_novel returns None when chapter plan generation fails."""
        role = NovelRole(name="novel_role")
        ctx = NovelContext.create("The hero.", language="English")
        meta = NovelPlan(title="T", description="D", expected_word_count=10, series_bible=SeriesBible())
        with install_router_usage(
            *return_model_json_router_usage(meta)[:1], "not valid json", "still not json", "nope"
        ):
            novel = await role.compose_novel(ctx)
        assert novel is None

    async def test_compose_novel_expands_stories_for_prefilled_chapter(self) -> None:
        """Assert compose_novel plans stories and scenes under a prefilled chapter context."""
        role = NovelRole(name="novel_role")
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        ctx.add_chapter_context(ChapterContext(title="Ch1", description="The hero sets out.").set_language("English"))

        meta = NovelPlan(
            title="The Search",
            description="A hero searching.",
            expected_word_count=100,
            series_bible=SeriesBible(),
        )
        story_plans_json = [{"title": "St1", "description": "The departure.", "weight": 1.0}]
        scene_plans_json = [{"title": "S1", "description": "Leaving home.", "weight": 1.0}]

        responses = return_mixed_router_usage(
            Value(meta, "model"),
            Value(story_plans_json, "json"),
            Value(scene_plans_json, "json"),
            raw_value("He left."),
        )
        with install_router_usage(*responses):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        assert novel.chapter[0].story[0].scenes[0].content == "He left."
        assert len(ctx.chapter_context) == 1
        assert len(ctx.chapter_context[0].story_context) == 1
        assert ctx.chapter_context[0].story_context[0].story_plan is not None
        assert ctx.chapter_context[0].story_context[0].story_plan.title == "St1"
        assert ctx.chapter_context[0].story_context[0].scene_context[0].scene_plan is not None
        assert ctx.chapter_context[0].story_context[0].scene_context[0].scene_plan.title == "S1"
        assert ctx.chapter_context[0].story_context[0].scene_context[0].language == "English"


class TestWordCountAllocation:
    """Test suite for LLM-weighted word count allocation across planning levels."""

    async def test_allocates_word_counts_by_plan_weights(self) -> None:
        """Assert plan weights drive the allocated word counts down the whole tree."""
        role = NovelRole(name="novel_role")
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        meta = NovelPlan(
            title="The Search", description="A hero searching.", expected_word_count=400, series_bible=SeriesBible()
        )
        chapter_plans_json = [
            {"title": "Ch1", "description": "The start.", "weight": 3.0},
            {"title": "Ch2", "description": "The road.", "weight": 1.0},
        ]
        story_plans_json = [{"title": "St1", "description": "The departure.", "weight": 1.0}]
        scene_plans_json = [{"title": "S1", "description": "Leaving home.", "weight": 1.0}]
        with install_router_usage(
            *return_mixed_router_usage(
                Value(meta, "model"),
                Value(chapter_plans_json, "json"),
                Value(story_plans_json, "json"),
                Value(scene_plans_json, "json"),
                raw_value("A."),
                Value(story_plans_json, "json"),
                Value(scene_plans_json, "json"),
                raw_value("B."),
            )
        ):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        assert ctx.chapter_context[0].expected_word_count == 300
        assert ctx.chapter_context[1].expected_word_count == 100
        assert ctx.chapter_context[0].story_context[0].expected_word_count == 300
        assert ctx.chapter_context[1].story_context[0].expected_word_count == 100
        assert ctx.chapter_context[0].story_context[0].scene_context[0].expected_word_count == 300
        assert ctx.chapter_context[1].story_context[0].scene_context[0].expected_word_count == 100


class TestPlanningOutlineGrounding:
    """Test suite for outline grounding across every planning prompt."""

    async def test_planning_requirements_embed_outline(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert chapter, story, and scene planning prompts all embed the raw outline text."""
        role = NovelRole(name="novel_role")
        captured: List[str] = []

        async def fake_propose(
            cls: type[ProposedAble],
            prompt: str,
            send_to: str,
            **kwargs: ValidateKwargs,
        ) -> None:
            captured.append(prompt)

        monkeypatch.setattr(NovelRole, "propose", staticmethod(fake_propose))

        novel = NovelContext.create("The hero seeks his father.", language="English")
        await role.plan_chapters_phase(novel)
        chapter = ChapterContext(title="Ch1", description="The start.").set_outline(novel.outline)
        await role.plan_stories_phase(chapter)
        story = StoryContext(title="St1", description="The departure.").set_outline(novel.outline)
        await role.plan_scenes_phase(story)

        assert len(captured) == 3
        assert all("The hero seeks his father." in requirement for requirement in captured)
