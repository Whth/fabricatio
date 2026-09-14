"""Progressive-planning tests for fabricatio-novel: plans, word counts, outline grounding."""

import pytest
from fabricatio_core.models.generic import ProposedAble
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_mock import MockScript, Value, make_test_role
from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.plan import NovelPlan


class TestNovelPlan:
    """Test suite for progressive planning of an empty context tree."""

    async def test_compose_novel_plans_empty_tree(self) -> None:
        """Assert compose_novel plans an empty context tree down to scenes and writes content."""
        role = make_test_role(NovelCompose, name="novel_role")
        ctx = NovelContext.create("The hero seeks his father., planning v2 salt.", language="English")
        meta = NovelPlan(
            title="The Search",
            description="A hero searching for his father.",
            expected_word_count=100,
            writing_styles=[],
            writing_constraints=[],
        )
        chapter_plans_json = [
            {
                "title": "Ch1",
                "description": "The hero sets out.",
                "weight": 1.0,
                "writing_styles": [],
                "writing_constraints": [],
            }
        ]
        story_plans_json = [
            {
                "title": "St1",
                "description": "The departure.",
                "weight": 1.0,
                "writing_styles": [],
                "writing_constraints": [],
            }
        ]
        scene_plans_json = [
            {
                "title": "S1",
                "description": "Leaving home.",
                "weight": 1.0,
                "writing_styles": [],
                "writing_constraints": [],
            }
        ]
        with MockScript.from_values(
            Value.from_model(meta, name="novel metadata"),
            Value.from_json(chapter_plans_json, name="chapter plans"),
            Value.from_json(story_plans_json, name="story plans"),
            Value.from_json(scene_plans_json, name="scene plans"),
            Value.from_text("He left.", name="scene prose"),
        ):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        assert novel.title == "The Search"
        assert len(novel.chapter) == 1
        assert novel.chapter[0].title == "Ch1"
        assert novel.chapter[0].story[0].scenes[0].content == "He left."
        assert ctx.plan is not None
        assert ctx.plan.title == "The Search"
        assert ctx.child_contexts[0].plan is not None
        assert ctx.child_contexts[0].plan.title == "Ch1"
        assert ctx.child_contexts[0].child_contexts[0].plan is not None
        assert ctx.child_contexts[0].child_contexts[0].plan.title == "St1"
        assert ctx.child_contexts[0].child_contexts[0].child_contexts[0].plan is not None
        assert ctx.child_contexts[0].child_contexts[0].child_contexts[0].plan.title == "S1"
        assert ctx.child_contexts[0].child_contexts[0].child_contexts[0].language == "English"

    async def test_compose_novel_allocates_writing_constraint_down_tree(self) -> None:
        """Assert every level carries its own constraints and reaches the scene requirement that way."""
        role = make_test_role(NovelCompose, name="novel_role")
        ctx = NovelContext.create("The hero seeks his father., planning v2 salt.", language="English")
        ctx.set_writing_constraints(["I hope the novel is first person view."])
        meta = NovelPlan(
            title="The Search",
            description="A hero searching for his father.",
            expected_word_count=100,
            writing_styles=["Close first person."],
            writing_constraints=["First person view throughout: narrate from the protagonist's perspective using I."],
        )
        chapter_plans_json = [
            {
                "title": "Ch1",
                "description": "The hero sets out.",
                "weight": 1.0,
                "writing_styles": [],
                "writing_constraints": ["Keep first person during the road journey."],
            },
        ]
        story_plans_json = [
            {
                "title": "St1",
                "description": "The departure.",
                "weight": 1.0,
                "writing_styles": [],
                "writing_constraints": [],
            }
        ]
        scene_plans_json = [
            {
                "title": "S1",
                "description": "Leaving home.",
                "weight": 1.0,
                "writing_styles": [],
                "writing_constraints": ["Stay in the protagonist's head; no head-hopping."],
            },
        ]
        with MockScript.from_values(
            Value.from_model(meta, name="novel metadata"),
            Value.from_json(chapter_plans_json, name="chapter plans"),
            Value.from_json(story_plans_json, name="story plans"),
            Value.from_json(scene_plans_json, name="scene plans"),
            Value.from_text("He left.", name="scene prose"),
        ):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        chapter_ctx = ctx.child_contexts[0]
        story_ctx = chapter_ctx.child_contexts[0]
        scene_ctx = story_ctx.child_contexts[0]
        # the generated global constraint replaces the author's raw intent
        assert ctx.writing_constraints == meta.writing_constraints
        # the novel plan's styles seed the root channel and reach every scene
        assert ctx.writing_styles == meta.writing_styles
        assert scene_ctx.writing_styles == meta.writing_styles
        # each level carries its own constraints, never the parent's chain
        assert chapter_ctx.writing_constraints == ["Keep first person during the road journey."]
        assert story_ctx.writing_constraints == []
        assert scene_ctx.writing_constraints == ["Stay in the protagonist's head; no head-hopping."]
        # the scene's prose requirement shows the scene's own entries and no ancestor's
        requirement = await role.prepare_scene_requirement(scene_ctx)
        assert "### Writing Constrains:" in requirement
        assert "no head-hopping" in requirement
        assert "Keep first person during the road journey." not in requirement

    async def test_propose_novel_metadata_keeps_intent_when_plan_constraint_empty(self) -> None:
        """Assert the author's stated constraint survives a plan that allocates none."""
        role = make_test_role(NovelCompose, name="novel_role")
        ctx = NovelContext.create("The hero., metadata intent salt.", language="English")
        ctx.set_writing_constraints(["I hope the novel is first person view."])
        meta = NovelPlan(
            title="The Search",
            description="A hero searching.",
            expected_word_count=100,
            writing_styles=[],
            writing_constraints=[],
        )
        with MockScript.from_values(Value.from_model(meta, name="novel metadata")):
            assert await role.propose_novel_metadata(ctx) is True
        assert ctx.writing_constraints == ["I hope the novel is first person view."]

    async def test_compose_novel_returns_none_when_plan_fails(self) -> None:
        """Assert compose_novel returns None when chapter plan generation fails."""
        role = make_test_role(NovelCompose, name="novel_role")
        ctx = NovelContext.create("The hero., planning v2 salt.", language="English")
        meta = NovelPlan(title="T", description="D", expected_word_count=10, writing_styles=[], writing_constraints=[])
        with MockScript.from_values(
            Value.from_model(meta, name="novel metadata"),
            Value.from_text("not valid json", name="malformed chapter plans"),
            Value.from_text("still not json", name="retry chapter plans"),
            Value.from_text("nope", name="final chapter plans"),
        ):
            novel = await role.compose_novel(ctx)
        assert novel is None

    async def test_compose_novel_expands_stories_for_prefilled_chapter(self) -> None:
        """Assert compose_novel plans stories and scenes under a prefilled chapter context."""
        role = make_test_role(NovelCompose, name="novel_role")
        ctx = NovelContext.create("The hero seeks his father., planning v2 salt.", language="English")
        ctx.add_context(ChapterContext(title="Ch1", description="The hero sets out.").set_language("English"))

        meta = NovelPlan(
            title="The Search",
            description="A hero searching.",
            expected_word_count=100,
            writing_styles=[],
            writing_constraints=[],
        )
        story_plans_json = [
            {
                "title": "St1",
                "description": "The departure.",
                "weight": 1.0,
                "writing_styles": [],
                "writing_constraints": [],
            }
        ]
        scene_plans_json = [
            {
                "title": "S1",
                "description": "Leaving home.",
                "weight": 1.0,
                "writing_styles": [],
                "writing_constraints": [],
            }
        ]

        with MockScript.from_values(
            Value.from_model(meta, name="novel metadata"),
            Value.from_json(story_plans_json, name="story plans"),
            Value.from_json(scene_plans_json, name="scene plans"),
            Value.from_text("He left.", name="scene prose"),
        ):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        assert novel.chapter[0].story[0].scenes[0].content == "He left."
        assert len(ctx.child_contexts) == 1
        assert len(ctx.child_contexts[0].child_contexts) == 1
        assert ctx.child_contexts[0].child_contexts[0].plan is not None
        assert ctx.child_contexts[0].child_contexts[0].plan.title == "St1"
        assert ctx.child_contexts[0].child_contexts[0].child_contexts[0].plan is not None
        assert ctx.child_contexts[0].child_contexts[0].child_contexts[0].plan.title == "S1"
        assert ctx.child_contexts[0].child_contexts[0].child_contexts[0].language == "English"


class TestWordCountAllocation:
    """Test suite for LLM-weighted word count allocation across planning levels."""

    async def test_allocates_word_counts_by_plan_weights(self) -> None:
        """Assert plan weights drive the allocated word counts down the whole tree."""
        role = make_test_role(NovelCompose, name="novel_role")
        ctx = NovelContext.create("The hero seeks his father., planning v2 salt.", language="English")
        meta = NovelPlan(
            title="The Search",
            description="A hero searching.",
            expected_word_count=400,
            writing_styles=[],
            writing_constraints=[],
        )
        chapter_plans_json = [
            {
                "title": "Ch1",
                "description": "The start.",
                "weight": 3.0,
                "writing_styles": [],
                "writing_constraints": [],
            },
            {
                "title": "Ch2",
                "description": "The road.",
                "weight": 1.0,
                "writing_styles": [],
                "writing_constraints": [],
            },
        ]
        story_plans_json = [
            {
                "title": "St1",
                "description": "The departure.",
                "weight": 1.0,
                "writing_styles": [],
                "writing_constraints": [],
            }
        ]
        scene_plans_json = [
            {
                "title": "S1",
                "description": "Leaving home.",
                "weight": 1.0,
                "writing_styles": [],
                "writing_constraints": [],
            }
        ]
        with MockScript.from_values(
            Value.from_model(meta, name="novel metadata"),
            Value.from_json(chapter_plans_json, name="chapter plans"),
            Value.from_json(story_plans_json, name="first chapter story plans"),
            Value.from_json(scene_plans_json, name="first story scene plans"),
            Value.from_text("A.", name="first scene prose"),
            Value.from_json(story_plans_json, name="second chapter story plans"),
            Value.from_json(scene_plans_json, name="second story scene plans"),
            Value.from_text("B.", name="second scene prose"),
        ):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        assert ctx.child_contexts[0].expected_word_count == 300
        assert ctx.child_contexts[1].expected_word_count == 100
        assert ctx.child_contexts[0].child_contexts[0].expected_word_count == 300
        assert ctx.child_contexts[1].child_contexts[0].expected_word_count == 100
        assert ctx.child_contexts[0].child_contexts[0].child_contexts[0].expected_word_count == 300
        assert ctx.child_contexts[1].child_contexts[0].child_contexts[0].expected_word_count == 100


class TestPlanningOutlineGrounding:
    """Test suite for outline grounding across every planning prompt."""

    async def test_planning_requirements_embed_outline(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert chapter, story, and scene planning prompts all embed the raw outline text."""
        role = make_test_role(NovelCompose, name="novel_role")
        captured: list[str] = []

        async def fake_propose(
            cls: type[ProposedAble],
            prompt: str,
            send_to: str,
            **kwargs: ValidateKwargs,
        ) -> None:
            captured.append(prompt)

        monkeypatch.setattr(type(role), "propose", staticmethod(fake_propose))

        novel = NovelContext.create("The hero seeks his father., planning v2 salt.", language="English")
        await role.plan_chapters_phase(novel)
        chapter = ChapterContext(title="Ch1", description="The start.").set_outline(novel.outline)
        await role.plan_stories_phase(chapter)
        story = StoryContext(title="St1", description="The departure.").set_outline(novel.outline)
        await role.plan_scenes_phase(story)

        assert len(captured) == 3
        assert all("The hero seeks his father." in requirement for requirement in captured)
