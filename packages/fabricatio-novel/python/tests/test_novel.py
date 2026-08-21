"""Test module for fabricatio-novel contexts, models, and generation capabilities."""

from itertools import pairwise
from pathlib import Path
from typing import List

import pytest
from fabricatio_character.models.character import CharacterCard
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import (
    Value,
    return_mixed_router_usage,
    return_model_json_router_usage,
    return_router_usage,
)
from fabricatio_mock.utils import install_router_usage
from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.capabilities.rag import RAGCompose
from fabricatio_novel.models.context.base import CharacterSpan, derive_child_spans
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.log import ContextEntry, ContextLog
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.context.rag import RagRetrieval
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.novel import Novel
from fabricatio_novel.models.plan import ChapterPlan, NovelPlan, ScenePlan, ScenePlans, StoryPlan
from fabricatio_novel.models.rag import WritingStyleDocument, WritingStyleFetchConfig
from fabricatio_novel.models.scene import Scene
from fabricatio_novel.models.series_book import SeriesBible


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
    )


def raw_value(text: str) -> Value[str]:
    """Wrap a plain scene response for mixed router usage."""
    return Value(text, "raw", convertor=lambda s: s)


def prefix_log(body: str, *, title: str = "S1") -> ContextLog:
    """Build a one-entry scene-content prefix log for tests."""
    return ContextLog(entries=(ContextEntry(kind="scene_content", title=title, body=body),))


class TestNovelContext:
    """Test suite for NovelContext."""

    def test_create_detects_language(self) -> None:
        """Assert create detects the outline language and initializes empty context fields."""
        ctx = NovelContext.create("少年踏上旅途。")
        assert ctx.language == "简体中文"
        assert ctx.outline == "少年踏上旅途。"
        assert ctx.title == ""
        assert ctx.description == ""
        assert ctx.series_bible is None
        assert ctx.chapter_context == []

    def test_create_with_explicit_language(self) -> None:
        """Assert an explicitly passed language overrides automatic detection."""
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        assert ctx.language == "English"

    def test_update_from_adopts_plan_fields(self) -> None:
        """Assert update_from copies the plan fields into the context and returns self."""
        ctx = NovelContext.create("The hero.", language="English")
        plan = NovelPlan(
            title="The Search",
            description="A hero searching.",
            expected_word_count=100,
            writing_constraint="First person view throughout.",
            series_bible=SeriesBible(characters="Hero — brave protagonist."),
        )
        result = ctx.update_from(plan)
        assert result is ctx
        assert ctx.title == "The Search"
        assert ctx.description == "A hero searching."
        assert ctx.expected_word_count == 100
        assert ctx.writing_constraint == "First person view throughout."
        assert ctx.series_bible == plan.series_bible

    def test_update_from_keeps_intent_when_plan_constraint_empty(self) -> None:
        """Assert the author's stated constraint survives an empty plan constraint."""
        ctx = NovelContext.create("The hero.", language="English")
        ctx.set_writing_constraint("I hope the novel is first person view.")
        plan = NovelPlan(title="The Search", description="A hero searching.", expected_word_count=100)
        ctx.update_from(plan)
        assert ctx.writing_constraint == "I hope the novel is first person view."

    def test_update_from_keeps_preset_bible_when_plan_bible_empty(self) -> None:
        """Assert a preset series bible survives update_from with an empty-plan bible."""
        ctx = NovelContext.create("The hero.", language="English")
        bible = SeriesBible(characters="Hero — brave protagonist.")
        ctx.set_series_bible(bible)
        plan = NovelPlan(title="The Search", description="A hero searching.", expected_word_count=100)
        ctx.update_from(plan)
        assert ctx.title == "The Search"
        assert ctx.series_bible is bible

    def test_update_from_rejects_non_plan(self) -> None:
        """Assert update_from raises TypeError when given a non-plan value."""
        ctx = NovelContext.create("The hero.", language="English")
        with pytest.raises(TypeError):
            ctx.update_from("not a plan")  # type: ignore[arg-type]

    def test_contexts_are_chainable(self) -> None:
        """Assert chained setters attach plans and children across every context level."""
        scene = (
            SceneContext(title="S1", description="Leaving home.", expected_word_count=100)
            .set_language("English")
            .set_content("He left.")
            .set_prefix_log(prefix_log("Before.", title="S1"))
            .set_writing_constraint("First person view throughout.")
            .set_scene_plan(ScenePlan(title="S1", description="Leaving home."))
        )
        story = StoryContext(title="St1", description="The departure.", expected_word_count=100)
        story.add_scene_context(scene)
        story.set_story_plan(StoryPlan(title="St1", description="The departure."))
        chapter = ChapterContext(title="Ch1", description="The start.", expected_word_count=100)
        chapter.add_story_context(story)
        chapter.set_chapter_plan(ChapterPlan(title="Ch1", description="The start."))
        novel = NovelContext.create("The hero.", language="English")
        novel.add_chapter_context(chapter)
        novel.set_novel_plan(
            NovelPlan(title="The Hero", description="A hero.", expected_word_count=100, series_bible=SeriesBible())
        )

        assert scene.title == "S1"
        assert scene.content == "He left."
        assert scene.prefix_log.render() == "Before."
        assert scene.language == "English"
        assert scene.writing_constraint == "First person view throughout."
        assert story.scene_context == [scene]
        assert chapter.story_context == [story]
        assert novel.chapter_context == [chapter]
        assert novel.novel_plan is not None
        assert novel.novel_plan.title == "The Hero"
        assert chapter.chapter_plan is not None
        assert chapter.chapter_plan.title == "Ch1"
        assert story.story_plan is not None
        assert story.story_plan.title == "St1"
        assert scene.scene_plan is not None
        assert scene.scene_plan.title == "S1"


class TestCharacterSpan:
    """Test suite for CharacterSpan."""

    def test_dump_to_prompt_renders_start_and_end(self) -> None:
        """Assert dump_to_prompt shows both states as Initial and finalizing."""
        start = card()
        end = card().model_copy(update={"look": "scarred"})
        span = CharacterSpan(start=start, end=end)
        prompt = span.dump_to_prompt()
        assert prompt.startswith("Initial State:")
        assert "finalizing State:" in prompt
        assert prompt.count("# Name") == 2
        assert prompt.count("## Look") == 2
        assert "tall" in prompt
        assert "scarred" in prompt

    def test_dump_to_prompt_with_same_start_and_end(self) -> None:
        """Assert a span whose end equals its start renders the same card twice."""
        start = card()
        span = CharacterSpan(start=start, end=start.model_copy(deep=True))
        prompt = span.dump_to_prompt()
        assert prompt.count("# Name") == 2
        assert "Initial State:" in prompt
        assert "finalizing State:" in prompt

    def test_derive_child_spans_stitches_boundaries_between_parent_ends(self) -> None:
        """Assert N children need N-1 boundary cards; the parent ends anchor the chain."""
        start = card()
        b1 = start.model_copy(update={"act": "cautious"})
        b2 = start.model_copy(update={"flaw": "distrustful"})
        end = start.model_copy(update={"look": "wounded"})
        spans = derive_child_spans(CharacterSpan(start=start, end=end), [b1, b2])
        assert len(spans) == 3
        assert [s.start for s in spans] == [start, b1, b2]
        assert [s.end for s in spans] == [b1, b2, end]
        # the chain is continuous by construction
        assert spans[0].end is spans[1].start
        assert spans[1].end is spans[2].start

    def test_derive_child_spans_without_boundaries_returns_single_span(self) -> None:
        """Assert one child inherits the parent span unchanged when no boundaries are drafted."""
        start = card()
        end = start.model_copy(update={"look": "wounded"})
        spans = derive_child_spans(CharacterSpan(start=start, end=end), [])
        assert len(spans) == 1
        assert spans[0].start is start
        assert spans[0].end is end


class TestFromContext:
    """Test suite for the from_context assembly methods."""

    def test_scene_from_context(self) -> None:
        """Assert Scene.from_context materializes the scene fields from its context."""
        ctx = SceneContext(title="Departure", description="The hero leaves.", expected_word_count=50)
        ctx.content = "He walked out."
        scene = Scene.from_context(ctx)
        assert scene.title == "Departure"
        assert scene.description == "The hero leaves."
        assert scene.content == "He walked out."
        assert scene.expected_word_count == 50

    def test_from_plan_copies_plan_fields(self) -> None:
        """Assert SceneContext.from_plan copies plan fields and keeps the plan reference."""
        plan = ScenePlan(title="S1", description="The descent.", weight=1.0, writing_style="Gothic, lyrical prose.")
        ctx = SceneContext.from_plan(plan, expected_word_count=300)
        assert ctx.title == "S1"
        assert ctx.description == "The descent."
        assert ctx.expected_word_count == 300
        assert ctx.writing_styles == []
        assert ctx.scene_plan is plan

    def test_plans_default_to_empty_cast(self) -> None:
        """Assert every weighted plan proposes an empty cast unless the planner names one."""
        assert ScenePlan(title="S1", description="D").cast == []
        assert StoryPlan(title="St1", description="D").cast == []
        assert ChapterPlan(title="C1", description="D").cast == []

    def test_from_plan_copies_cast(self) -> None:
        """Assert from_plan copies the proposed cast onto every context level."""
        scene = SceneContext.from_plan(ScenePlan(title="S1", description="D", cast=["Hero", "Villain"]), 100)
        story = StoryContext.from_plan(StoryPlan(title="St1", description="D", cast=["Hero"]), 300)
        chapter = ChapterContext.from_plan(ChapterPlan(title="C1", description="D", cast=["Hero"]), 1000)
        assert scene.cast == ["Hero", "Villain"]
        assert story.cast == ["Hero"]
        assert chapter.cast == ["Hero"]

    def test_novel_from_context_assembles_full_tree(self) -> None:
        """Assert Novel.from_context assembles the full chapter, story, and scene tree."""
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        ctx.title = "The Search"
        ctx.description = "A hero searching."
        ctx.expected_word_count = 200
        bible = SeriesBible(characters="Hero — brave protagonist.")
        ctx.set_series_bible(bible)

        chapter_ctx = ChapterContext(title="Ch1", description="The start.")
        story_ctx = StoryContext(title="St1", description="The departure.")
        scene_ctx = SceneContext(title="S1", description="Leaving home.", expected_word_count=100)
        scene_ctx.content = "He left."
        story_ctx.scene_context.append(scene_ctx)
        chapter_ctx.story_context.append(story_ctx)
        ctx.chapter_context.append(chapter_ctx)

        novel = Novel.from_context(ctx)
        assert novel.title == "The Search"
        assert len(novel.chapter) == 1
        assert novel.chapter[0].title == "Ch1"
        assert novel.chapter[0].story[0].title == "St1"
        assert novel.chapter[0].story[0].scenes[0].content == "He left."
        assert novel.series_bible is ctx.series_bible


class NovelRole(LLMTestRole, NovelCompose):
    """Test role combining mock LLM with the novel composition chain."""


class TestCharacterSpans:
    """Test suite for the per-level CharacterSpan pipeline."""

    async def test_compose_novel_stitches_chapter_boundaries_to_roster_ends(self) -> None:
        """Assert N chapters need N-1 boundary cards; chapter 1 starts at the novel start and the last ends at the novel end."""
        role = NovelRole(name="novel_role")
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        bible = SeriesBible(characters="Hero — brave protagonist.")
        ctx.set_series_bible(bible)
        meta = NovelPlan(
            title="The Search", description="A hero searching.", expected_word_count=100, series_bible=bible
        )
        novel_start = card()
        novel_end = novel_start.model_copy(update={"look": "wounded"})
        chapter_boundary = novel_start.model_copy(update={"act": "cautious"})
        chapter_plans_json = [
            {"title": "Ch1", "description": "The start.", "weight": 1.0},
            {"title": "Ch2", "description": "The road.", "weight": 1.0},
        ]
        story_plans_json = [{"title": "St1", "description": "The departure.", "weight": 1.0}]
        scene_plans_json = [{"title": "S1", "description": "Leaving home.", "weight": 1.0}]
        with install_router_usage(
            *return_mixed_router_usage(
                Value(meta, "model"),
                Value([CharacterSpan(start=novel_start, end=novel_end).model_dump()], "json"),
                Value(chapter_plans_json, "json"),
                # 2 chapters -> 1 boundary card per roster character
                Value([[chapter_boundary.model_dump()]], "json"),
                Value(story_plans_json, "json"),
                Value(scene_plans_json, "json"),
                raw_value("He left."),
                Value(story_plans_json, "json"),
                Value(scene_plans_json, "json"),
                raw_value("He walked."),
            )
        ):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        assert len(ctx.charactor_span) == 1
        assert ctx.charactor_span[0].start.name == "Hero"
        assert ctx.charactor_span[0].end.look == "wounded"
        # chapter 1 opens at the novel start and closes at the boundary
        ch1 = ctx.chapter_context[0]
        assert len(ch1.charactor_span) == 1
        assert ch1.charactor_span[0].start.look == "tall"
        assert ch1.charactor_span[0].end.act == "cautious"
        # chapter 2 opens at the boundary and closes at the novel end
        ch2 = ctx.chapter_context[1]
        assert len(ch2.charactor_span) == 1
        assert ch2.charactor_span[0].start.act == "cautious"
        assert ch2.charactor_span[0].end.look == "wounded"
        # a single story inherits the chapter span directly, and scenes broadcast it
        story_ctx = ch1.story_context[0]
        assert story_ctx.charactor_span is ch1.charactor_span
        scene_ctx = story_ctx.scene_context[0]
        assert scene_ctx.charactor_span is ch1.charactor_span
        requirement = await role.prepare_scene_requirement(scene_ctx)
        assert "Initial State:" in requirement
        assert "finalizing State:" in requirement
        assert "## Act" in requirement
        assert "cautious" in requirement

    async def test_draft_chapter_spans_single_chapter_inherits_roster(self) -> None:
        """Assert a single chapter gets the roster spans directly without an LLM call."""
        role = NovelRole(name="novel_role")
        ctx = NovelContext.create("The hero.", language="English")
        span = CharacterSpan(start=card(), end=card())
        ctx.set_charactor_spans([span])
        ctx.add_chapter_context(ChapterContext(title="Ch1", description="The start."))
        await role.draft_chapter_spans(ctx)
        assert ctx.chapter_context[0].charactor_span is ctx.charactor_span

    async def test_draft_story_spans_single_story_inherits_chapter_span(self) -> None:
        """Assert a single story gets the chapter's spans directly without an LLM call."""
        role = NovelRole(name="novel_role")
        chapter = ChapterContext(title="Ch1", description="The start.")
        span = CharacterSpan(start=card(), end=card())
        chapter.set_charactor_spans([span])
        chapter.add_story_context(StoryContext(title="St1", description="The departure."))
        await role.draft_story_spans(chapter)
        assert chapter.story_context[0].charactor_span is chapter.charactor_span

    async def test_scene_requirement_shows_character_span(self) -> None:
        """Assert the scene prompt renders the broadcast span's start and end."""
        role = NovelRole(name="novel_role")
        start = card()
        end = card().model_copy(update={"look": "scarred"})
        ctx = SceneContext(title="S2", description="A stranger appears.", expected_word_count=50)
        ctx.set_charactor_spans([CharacterSpan(start=start, end=end)])
        requirement = await role.prepare_scene_requirement(ctx)
        assert "Initial State:" in requirement
        assert "finalizing State:" in requirement
        assert "## Look" in requirement
        assert "scarred" in requirement

    def test_cast_missing_spans_reports_unknown_members(self) -> None:
        """Assert an uncovered cast member is reported as missing."""
        ctx = StoryContext(title="St1", description="D")
        ctx.set_cast(["Hero", "Ghost"])
        ctx.set_charactor_spans([CharacterSpan(start=card(), end=card())])
        assert ctx.cast_missing_spans() == ["Ghost"]

    def test_cast_missing_spans_empty_when_covered(self) -> None:
        """Assert a fully covered cast passes the roster check."""
        ctx = StoryContext(title="St1", description="D")
        ctx.set_cast(["Hero"])
        ctx.set_charactor_spans([CharacterSpan(start=card(), end=card())])
        assert ctx.cast_missing_spans() == []


class TestNovelCompose:
    """Test suite for the generation chain with mock LLM."""

    async def test_compose_scene_writes_content_back_to_context(self) -> None:
        """Assert compose_scene writes the generated scene content back to the context."""
        role = NovelRole(name="novel_role")
        ctx = SceneContext(title="Departure", description="The hero leaves home.", expected_word_count=50)
        with install_router_usage(*return_router_usage("He walked out.")):
            scene = await role.compose_scene(ctx)
        assert scene is not None
        assert scene.content == "He walked out."
        assert scene.expected_word_count == 50
        assert ctx.content == "He walked out."

    async def test_compose_novel_broadcasts_story_span_to_scenes(self) -> None:
        """Assert every scene inherits the story's spans when prepare_scene_write runs."""
        role = NovelRole(name="novel_role")
        story = StoryContext(title="St1", description="The departure.")
        span = CharacterSpan(start=card(), end=card())
        story.set_charactor_spans([span])
        scene_ctx = SceneContext(title="Battle", description="The hero fights.", expected_word_count=50)
        story.scene_context.append(scene_ctx)
        with install_router_usage(*return_router_usage("He fought.")):
            await role.prepare_scene_write(story)
            scene = await role.compose_scene(scene_ctx)
        assert scene is not None
        assert scene_ctx.charactor_span is story.charactor_span
        assert scene_ctx.charactor_span == [span]

    async def test_compose_novel_end_to_end(self) -> None:
        """Assert a full composition fills content and prefixes across a prefilled tree."""
        role = NovelRole(name="novel_role")
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        chapter_ctx = ChapterContext(title="Ch1", description="The hero sets out.")
        story_ctx = StoryContext(title="St1", description="The departure.")
        scene_1 = SceneContext(title="S1", description="Leaving home.", expected_word_count=20)
        scene_2 = SceneContext(title="S2", description="A stranger appears.", expected_word_count=20)
        story_ctx.scene_context.extend([scene_1, scene_2])
        chapter_ctx.story_context.append(story_ctx)
        ctx.chapter_context.append(chapter_ctx)

        meta = NovelPlan(
            title="The Search",
            description="A hero searching for his father.",
            expected_word_count=40,
            series_bible=SeriesBible(),
        )

        with install_router_usage(
            *return_mixed_router_usage(
                Value(meta, "model"),
                raw_value("He left."),
                raw_value("A stranger appeared."),
            )
        ):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        assert novel.title == "The Search"
        assert len(novel.chapter) == 1
        assert len(novel.chapter[0].story) == 1
        assert len(novel.chapter[0].story[0].scenes) == 2
        assert novel.chapter[0].story[0].scenes[1].content == "A stranger appeared."
        assert ctx.title == "The Search"
        assert ctx.chapter_context[0].story_context[0].scene_context[1].content == "A stranger appeared."
        chapter_header = "# Ch1\n\n> The hero sets out."
        scenes = ctx.chapter_context[0].story_context[0].scene_context
        assert scenes[0].prefix_log.render() == chapter_header
        assert scenes[0].scenes_log.render() == ""
        assert scenes[1].prefix_log.render() == chapter_header
        assert scenes[1].scenes_log.render() == "He left."

    async def test_compose_novel_logs_progress_per_level(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Assert composition emits per-level progress and completion log lines."""
        role = NovelRole(name="novel_role")
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        chapter_ctx = ChapterContext(title="Ch1", description="The hero sets out.")
        story_ctx = StoryContext(title="St1", description="The departure.")
        scene_1 = SceneContext(title="S1", description="Leaving home.", expected_word_count=20)
        scene_2 = SceneContext(title="S2", description="A stranger appears.", expected_word_count=20)
        story_ctx.scene_context.extend([scene_1, scene_2])
        chapter_ctx.story_context.append(story_ctx)
        ctx.chapter_context.append(chapter_ctx)
        meta = NovelPlan(
            title="The Search",
            description="A hero searching for his father.",
            expected_word_count=40,
            series_bible=SeriesBible(),
        )

        with install_router_usage(
            *return_mixed_router_usage(
                Value(meta, "model"),
                raw_value("He left."),
                raw_value("A stranger appeared."),
            )
        ):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        err = capfd.readouterr().err
        assert "Generating novel from outline" in err
        assert "Novel plan proposed: 'The Search'" in err
        assert "Composing chapter 1/1 'Ch1'" in err
        assert "Composing story 1/1 'St1'" in err
        assert "Composing scene 1/2 'S1'" in err
        assert "Composing scene 2/2 'S2'" in err
        assert "Scene 'S1' composed" in err
        assert "Chapter 'Ch1' composed" in err
        assert "Novel 'The Search' composed" in err

    async def test_compose_novel_returns_none_when_metadata_fails(self) -> None:
        """Assert compose_novel returns None when metadata generation fails."""
        role = NovelRole(name="novel_role")
        ctx = NovelContext.create("The hero.", language="English")
        with install_router_usage("not valid json", "", ""):
            novel = await role.compose_novel(ctx)
        assert novel is None

    async def test_prepare_scene_requirement_renders_prefixed_content_after_static_head(self) -> None:
        """Assert the static head leads and prefixed content renders after the Previous Content marker."""
        role = NovelRole(name="novel_role")
        ctx = SceneContext(title="S2", description="A stranger appears.", expected_word_count=50)
        ctx.set_prefix_log(prefix_log("He walked into the dark.", title="S2"))

        requirement = await role.prepare_scene_requirement(ctx)

        # the static head (incl. per-run language) leads so it stays prefix-cacheable
        assert requirement.startswith("# Scene Writing")
        assert requirement.index("Respond entirely in") < requirement.index("# Previous Content")
        assert requirement.index("He walked into the dark.") > requirement.index("# Previous Content")
        assert requirement.index("A stranger appears.") > requirement.index("## Scene")
        # the per-scene word count must not sit inside the static Requirements block
        assert requirement.index("Write approximately 50 words.") > requirement.index("Respond entirely in")

    async def test_prepare_scene_requirement_renders_writing_style(self) -> None:
        """Assert the scene's planned writing style guides the prose requirement."""
        role = NovelRole(name="novel_role")
        ctx = SceneContext(title="S2", description="A stranger appears.", expected_word_count=50)
        ctx.set_writing_styles(["Terse action lines, present tense, close third person."])
        requirement = await role.prepare_scene_requirement(ctx)
        assert "## Writing Styles" in requirement
        assert "Terse action lines, present tense, close third person." in requirement
        assert requirement.index("## Writing Styles") < requirement.index("## Scene")

    async def test_prepare_scene_requirement_skips_writing_style_when_empty(self) -> None:
        """Assert an unset writing style renders no style section."""
        role = NovelRole(name="novel_role")
        ctx = SceneContext(title="S2", description="A stranger appears.", expected_word_count=50)
        requirement = await role.prepare_scene_requirement(ctx)
        assert "## Writing Styles" not in requirement

    async def test_prepare_scene_requirement_renders_writing_constraint(self) -> None:
        """Assert the scene's accumulated writing constraint guides the prose requirement."""
        role = NovelRole(name="novel_role")
        ctx = SceneContext(title="S2", description="A stranger appears.", expected_word_count=50)
        ctx.writing_constraint = "First person view throughout."
        requirement = await role.prepare_scene_requirement(ctx)
        assert "## Writing Constraint" in requirement
        assert "First person view throughout." in requirement
        assert requirement.index("## Writing Constraint") > requirement.index("## Scene")

    async def test_prepare_scene_requirement_skips_writing_constraint_when_empty(self) -> None:
        """Assert an unset writing constraint renders no constraint section."""
        role = NovelRole(name="novel_role")
        ctx = SceneContext(title="S2", description="A stranger appears.", expected_word_count=50)
        requirement = await role.prepare_scene_requirement(ctx)
        assert "## Writing Constraint" not in requirement

    async def test_scene_requirement_renders_cast(self) -> None:
        """Assert the scene's cast renders as an on-stage roster in the prose requirement."""
        role = NovelRole(name="novel_role")
        ctx = SceneContext(title="S2", description="A stranger appears.", expected_word_count=50)
        ctx.set_cast(["Hero", "Villain"])
        requirement = await role.prepare_scene_requirement(ctx)
        assert "## Cast" in requirement
        assert "Hero, Villain" in requirement

    async def test_scene_requirement_omits_cast_when_empty(self) -> None:
        """Assert an empty cast renders no cast section."""
        role = NovelRole(name="novel_role")
        ctx = SceneContext(title="S2", description="A stranger appears.", expected_word_count=50)
        requirement = await role.prepare_scene_requirement(ctx)
        assert "## Cast" not in requirement

    async def test_plan_scenes_renders_story_cast(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert scene planning sees the story's cast as context."""
        role = NovelRole(name="novel_role")
        story = StoryContext(title="St1", description="The departure.")
        story.set_cast(["Hero", "Villain"])
        captured: List[str] = []

        async def fake_propose(model: object, requirement: str, **kwargs: object) -> None:
            captured.append(requirement)

        monkeypatch.setattr(NovelRole, "propose", staticmethod(fake_propose))
        await role.plan_scenes(story)

        assert captured
        assert "## Story Cast" in captured[0]
        assert "Hero, Villain" in captured[0]

    async def test_plan_stories_renders_chapter_cast(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert story planning sees the chapter's cast as context."""
        role = NovelRole(name="novel_role")
        chapter = ChapterContext(title="Ch1", description="The start.")
        chapter.set_cast(["Hero"])
        captured: List[str] = []

        async def fake_propose(model: object, requirement: str, **kwargs: object) -> None:
            captured.append(requirement)

        monkeypatch.setattr(NovelRole, "propose", staticmethod(fake_propose))
        await role.plan_stories(chapter)

        assert captured
        assert "## Chapter Cast" in captured[0]
        assert "Hero" in captured[0]


class TestPrefixAccumulation:
    """Test suite for prefix log dependency injection across levels."""

    def _scene_ctx(self, title: str, description: str) -> SceneContext:
        return SceneContext(title=title, description=description, expected_word_count=20)

    async def test_compose_story_injects_prefix_across_scenes(self) -> None:
        """Assert later scenes accumulate earlier scene content into scenes_so_far."""
        role = NovelRole(name="novel_role")
        story = StoryContext(title="St1", description="The departure.")
        scene_1 = self._scene_ctx("S1", "Leaving home.")
        scene_2 = self._scene_ctx("S2", "A stranger appears.")
        story.add_scene_context(scene_1).add_scene_context(scene_2)
        with install_router_usage(
            *return_router_usage(
                "He left.",
                "A stranger appeared.",
            )
        ):
            result = await role.compose_story(story)
        assert result is not None
        assert scene_1.prefix_log.render() == ""
        assert scene_1.scenes_log.render() == ""
        assert scene_2.prefix_log.render() == ""
        assert scene_2.scenes_log.render() == "He left."

    async def test_compose_chapter_injects_prefix_across_stories(self) -> None:
        """Assert stories inherit the chapter header plus prior story blocks as prefixed_content."""
        role = NovelRole(name="novel_role")
        chapter = ChapterContext(title="Ch1", description="The start.")
        story_a = StoryContext(title="StA", description="A.")
        story_a.add_scene_context(self._scene_ctx("S1", "Leaving home."))
        story_b = StoryContext(title="StB", description="B.")
        story_b.add_scene_context(self._scene_ctx("S2", "A stranger appears."))
        chapter.add_story_context(story_a).add_story_context(story_b)
        with install_router_usage(
            *return_router_usage(
                "Alpha.",
                "Beta.",
            )
        ):
            result = await role.compose_chapter(chapter)
        assert result is not None
        story_a_block = "Alpha."
        chapter_header = "# Ch1\n\n> The start."
        assert story_a.prefix_log.render() == chapter_header
        assert story_b.prefix_log.render() == f"{chapter_header}\n\n{story_a_block}"
        assert story_b.scene_context[0].prefix_log.render() == f"{chapter_header}\n\n{story_a_block}"

    async def test_compose_novel_injects_prefix_across_chapters_and_stories(self) -> None:
        """Assert chapter and story prefixed_content chain across the whole composed novel."""
        role = NovelRole(name="novel_role")
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        ctx.title = "The Search"
        ctx.description = "A hero searching."
        ctx.expected_word_count = 80

        def story(title: str, scene_title: str, scene_description: str) -> StoryContext:
            s = StoryContext(title=title, description=scene_description)
            s.add_scene_context(self._scene_ctx(scene_title, scene_description))
            return s

        chapter_1 = ChapterContext(title="Ch1", description="The start.")
        chapter_1.add_story_context(story("StA", "S1", "Leaving home."))
        chapter_1.add_story_context(story("StB", "S2", "A stranger appears."))
        chapter_2 = ChapterContext(title="Ch2", description="The road.")
        chapter_2.add_story_context(story("StC", "S3", "The journey."))
        chapter_2.add_story_context(story("StD", "S4", "The arrival."))
        ctx.add_chapter_context(chapter_1).add_chapter_context(chapter_2)

        meta = NovelPlan(
            title="The Search", description="A hero searching.", expected_word_count=80, series_bible=SeriesBible()
        )
        with install_router_usage(
            *return_mixed_router_usage(
                Value(meta, "model"),
                raw_value("A."),
                raw_value("B."),
                raw_value("C."),
                raw_value("D."),
            )
        ):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        chapter_1_block = "# Ch1\n\n> The start.\n\nA.\n\nB."
        chapter_1_header = "# Ch1\n\n> The start."
        chapter_2_header = "# Ch2\n\n> The road."
        story_c_block = "C."
        assert chapter_1.prefix_log.render() == ""
        assert chapter_2.prefix_log.render() == chapter_1_block
        assert chapter_1.story_context[1].prefix_log.render() == f"{chapter_1_header}\n\nA."
        assert chapter_2.story_context[0].prefix_log.render() == f"{chapter_1_block}\n\n{chapter_2_header}"
        assert (
            chapter_2.story_context[1].prefix_log.render()
            == f"{chapter_1_block}\n\n{chapter_2_header}\n\n{story_c_block}"
        )
        assert (
            chapter_2.story_context[0].scene_context[0].prefix_log.render()
            == f"{chapter_1_block}\n\n{chapter_2_header}"
        )
        assert (
            chapter_2.story_context[1].scene_context[0].prefix_log.render()
            == f"{chapter_1_block}\n\n{chapter_2_header}\n\n{story_c_block}"
        )


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


class TestNovelEpub:
    """Test suite for Novel.dump_epub."""

    def test_dump_epub_builds_valid_structure(self, tmp_path: Path) -> None:
        """Assert dump_epub produces a valid EPUB with mimetype first, chapter, font, and cover."""
        import zipfile

        ctx = NovelContext.create("The hero seeks his father.", language="English")
        ctx.title = "The Search"
        ctx.description = "A hero searching."
        ctx.expected_word_count = 100
        chapter_ctx = ChapterContext(title="Ch1", description="The start.")
        story_ctx = StoryContext(title="St1", description="The departure.")
        scene_ctx = SceneContext(title="S1", description="Leaving home.", expected_word_count=100)
        scene_ctx.content = "He left.\n\nHe walked into the dark."
        story_ctx.scene_context.append(scene_ctx)
        chapter_ctx.story_context.append(story_ctx)
        ctx.chapter_context.append(chapter_ctx)
        novel = Novel.from_context(ctx)

        font_file = tmp_path / "custom.ttf"
        font_file.write_bytes(b"\x00\x01fake font bytes")
        cover_file = tmp_path / "cover.png"
        cover_file.write_bytes(b"\x89PNG\r\n\x1a\nfake image bytes")
        path = novel.dump_epub(tmp_path / "novel.epub", font=font_file, cover=cover_file)
        assert path.exists()
        assert path.stat().st_size > 0

        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            assert names[0] == "mimetype", f"mimetype must be the first entry, got {names[:3]}"
            assert zf.read("mimetype") == b"application/epub+zip"
            assert "META-INF/container.xml" in names
            assert any(name.endswith("nav.xhtml") for name in names)
            chapter_files = [n for n in names if n.endswith(".xhtml") and not n.endswith("nav.xhtml")]
            assert len(chapter_files) == 1, f"expected 1 chapter xhtml, got {chapter_files}"
            assert "He walked into the dark." in zf.read(chapter_files[0]).decode("utf-8")
            assert any(n.endswith("fonts/custom.ttf") for n in names), f"expected embedded font, got {names}"
            assert any(n.endswith("cover.png") for n in names), f"expected cover image, got {names}"
            css_file = next(n for n in names if n.endswith(".css"))
            assert "custom" in zf.read(css_file).decode("utf-8"), "font-family rule must reference the embedded font"


class RAGRole(LLMTestRole, NovelCompose, RAGCompose):
    """Test role combining mock LLM with RAG-extended novel composition."""


class TestRAGCompose:
    """Test suite for writing style RAG scene prompts."""

    async def test_prepare_scene_requirement_injects_style_docs_in_order(self) -> None:
        """Assert raw style docs render between the before-story prefix and the story so far."""
        role = RAGRole(name="rag_role")
        ctx = SceneContext(title="Battle", description="The hero fights the dragon.", expected_word_count=50)
        ctx.set_prefix_log(prefix_log("Chapter One\n\nThe hero leaves home.", title="Battle"))
        ctx.set_scenes_log(prefix_log("Scene one: the hero rides north.", title="Scene one"))
        ctx.set_writing_styles(["Dark gothic prose with terse action lines."])

        requirement = await role.prepare_scene_requirement(ctx)

        assert "## Writing Styles" in requirement
        assert "Dark gothic prose with terse action lines." in requirement
        assert requirement.index("# Previous Content") < requirement.index("## Writing Styles")
        assert requirement.index("## Writing Styles") < requirement.index("## Story so far")
        assert "## Writing Style Guideline" not in requirement

    async def test_compose_story_keeps_stable_prefix_byte_identical(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert scene prompts share a byte-identical stable region so prefix caching holds.

        Scene k+1's prompt must have scene k's prompt as a byte prefix through
        the whole of scene k's composed content; only the newly written scene
        and the scene instruction may differ.
        """
        role = RAGRole(name="rag_role")
        story = StoryContext(title="St1", description="The departure.")
        bible = SeriesBible(characters="Hero, Villain", background_settings=["The world is cold."])
        story.set_series_bible(bible)
        for title, desc in [("S1", "Leaving home."), ("S2", "A stranger appears."), ("S3", "The road.")]:
            story.add_scene_context(
                SceneContext(title=title, description=desc, expected_word_count=50)
                .set_writing_styles(["Dark gothic prose with terse action lines."])
                .set_series_bible(bible)
            )

        async def fake_fetch(query: object, config: object | None = None) -> List[WritingStyleDocument]:
            return []

        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))
        with install_router_usage(*return_router_usage("One.", "Two.", "Three.")):
            result = await role.compose_story(story)

        assert result is not None
        reqs = [await role.prepare_scene_requirement(scene) for scene in story.scene_context]

        stable = reqs[1][: reqs[1].index("## Story so far")]
        assert reqs[0][: reqs[0].index("## Scene")] == stable
        assert reqs[2][: reqs[2].index("## Story so far")] == stable
        assert "Dark gothic prose with terse action lines." in stable
        assert "The world is cold." in stable

        for prev, nxt in pairwise(reqs):
            if "--- End of Story so far ---" in prev:
                shared = prev.index("\n--- End of Story so far ---")
                assert nxt.startswith(prev[:shared])

    async def test_prepare_story_retrieves_docs_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert plan_scenes_phase retrieves style docs exactly once."""
        role = RAGRole(name="rag_role")
        story = StoryContext(title="St1", description="The departure.")
        story.set_rag(RagRetrieval())
        story.scene_context.append(SceneContext(title="S1", description="Leaving home.", expected_word_count=50))
        fetched: List[object] = []
        doc = WritingStyleDocument.with_text_chunk("Dark gothic prose.")

        async def fake_fetch(query: object, config: object | None = None) -> List[WritingStyleDocument]:
            fetched.append(query)
            return [doc]

        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))

        async def fake_propose(model: object, requirement: object, **kwargs: object) -> object:
            return []

        monkeypatch.setattr(RAGRole, "propose", staticmethod(fake_propose))

        await role.plan_scenes_phase(story)

        assert fetched == [["The departure."]]

    async def test_prepare_story_without_docs_keeps_requirement_base(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert a story without retrieved style docs renders no references section."""
        role = RAGRole(name="rag_role")
        story = StoryContext(title="St1", description="The departure.")
        scene = SceneContext(title="Battle", description="The hero fights.", expected_word_count=50)
        story.scene_context.append(scene)
        story.set_rag(RagRetrieval())

        async def fake_fetch_docs(ctx: StoryContext, **kwargs: object) -> List[WritingStyleDocument]:
            return []

        monkeypatch.setattr(RAGRole, "_fetch_style_docs", staticmethod(fake_fetch_docs))

        await role.prepare_story(story)

        assert story.writing_styles == []
        requirement = await role.prepare_scene_requirement(scene)
        assert "## Writing Styles" not in requirement
        assert "The hero fights." in requirement

    async def test_plan_scenes_propagates_style_docs_to_scenes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert scenes materialized after the story prep inherit the story's style references."""
        role = RAGRole(name="rag_role")
        story = StoryContext(title="St1", description="The departure.")
        story.set_writing_styles(["Dark gothic prose with terse action lines."])

        async def fake_fetch_docs(ctx: StoryContext, **kwargs: object) -> List[WritingStyleDocument]:
            return []

        async def fake_propose(model: object, requirement: str, **kwargs: object) -> ScenePlans:
            return ScenePlans(root=[ScenePlan(title="S1", description="Leaving home.", weight=1.0)])

        monkeypatch.setattr(RAGRole, "_fetch_style_docs", staticmethod(fake_fetch_docs))
        monkeypatch.setattr(RAGRole, "propose", staticmethod(fake_propose))

        await role.plan_scenes_phase(story)

        assert len(story.scene_context) == 1
        assert story.scene_context[0].writing_styles == story.writing_styles

    async def test_plan_scenes_injects_held_style_docs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert the story's held style references render into the scene planning prompt."""
        role = RAGRole(name="rag_role")
        story = StoryContext(title="St1", description="The departure.")
        story.set_writing_styles(["Dark gothic prose with terse action lines."])
        captured: List[str] = []

        async def fake_propose(model: object, requirement: str, **kwargs: object) -> None:
            captured.append(requirement)

        monkeypatch.setattr(RAGRole, "propose", staticmethod(fake_propose))

        await role.plan_scenes(story)

        assert captured
        assert "- Writing styles:" in captured[0]
        assert "Dark gothic prose with terse action lines." in captured[0]

    async def test_fetch_style_docs_combines_query_and_applies_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert _fetch_style_docs joins description and rag_query and applies the limit."""
        role = RAGRole(name="rag_role")
        ctx = StoryContext(title="Battle", description="The hero fights.")
        ctx.set_rag(RagRetrieval(query="中文查询指南", limit=7))
        doc = WritingStyleDocument.with_text_chunk("Dark gothic prose.")
        captured_queries: List[object] = []
        captured_configs: List[WritingStyleFetchConfig] = []

        async def fake_fetch(
            query: object, config: WritingStyleFetchConfig | None = None
        ) -> List[WritingStyleDocument]:
            captured_queries.append(query)
            if config is not None:
                captured_configs.append(config)
            return [doc] * 8

        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))

        docs = await role._fetch_style_docs(ctx)

        assert docs == [doc] * 7
        assert captured_queries == [["The hero fights.\n中文查询指南"]]
        assert captured_configs
        assert captured_configs[0].limit == 7

    async def test_fetch_style_docs_defaults_to_story_description(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert _fetch_style_docs uses the story description when no rag_query is set."""
        role = RAGRole(name="rag_role")
        ctx = StoryContext(title="Battle", description="The hero fights.")
        ctx.set_rag(RagRetrieval())
        captured_queries: List[object] = []

        async def fake_fetch(
            query: object, config: WritingStyleFetchConfig | None = None
        ) -> List[WritingStyleDocument]:
            captured_queries.append(query)
            return []

        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))

        await role._fetch_style_docs(ctx)

        assert captured_queries == [["The hero fights."]]

    async def test_fetch_style_docs_skips_blank_prompt_docs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert docs whose prompt renders blank are filtered out."""
        role = RAGRole(name="rag_role")
        ctx = StoryContext(title="Battle", description="The hero fights.")
        ctx.set_rag(RagRetrieval())
        doc = WritingStyleDocument.with_text_chunk("Dark gothic prose.")
        blank = WritingStyleDocument.with_text_chunk("   ")

        async def fake_fetch(
            query: object, config: WritingStyleFetchConfig | None = None
        ) -> List[WritingStyleDocument]:
            return [blank, doc, blank]

        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))

        docs = await role._fetch_style_docs(ctx)

        assert docs == [doc]

    async def test_rag_settings_survive_story_composition(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert retrieval settings set on the story survive composition and scenes stay RAG-free."""
        role = RAGRole(name="rag_role")
        story = StoryContext(title="St1", description="The departure.")
        story.set_rag(RagRetrieval(query="guide", limit=7))

        async def fake_fetch(
            query: object, config: WritingStyleFetchConfig | None = None
        ) -> List[WritingStyleDocument]:
            return []

        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))
        with install_router_usage(
            *return_router_usage('[{"title": "S1", "description": "Leaving home.", "weight": 1.0}]', "He left.")
        ):
            result = await role.compose_story(story)

        assert result is not None
        assert story.rag == RagRetrieval(query="guide", limit=7)
        assert story.scene_context[0].writing_styles == []


class TestNovelWorkflow:
    """Test suite for the staged DebugNovelWorkflow."""

    async def test_debug_workflow_stages_persist_snapshots_and_returns_epub(self, tmp_path: Path) -> None:
        """Assert the workflow runs every stage, persists per-stage snapshots, and returns the EPUB path."""
        from fabricatio_core import Event, Role, Task
        from fabricatio_novel.workflows.novel import DebugNovelWorkflow

        namespace = "write_test"
        persist_dir = tmp_path / "persist"
        Role.with_bio(name="writer").subscribe(Event.quick_instantiate(namespace), DebugNovelWorkflow).dispatch()
        task = Task(name="wf novel").update_init_context(
            novel_outline="The hero seeks his father.",
            novel_language="English",
            persist_dir=persist_dir,
        )
        meta = NovelPlan(
            title="The Search",
            description="A hero searching for his father.",
            expected_word_count=100,
            series_bible=SeriesBible(),
        )
        chapter_plans_json = [{"title": "Ch1", "description": "The hero sets out.", "weight": 1.0}]
        story_plans_json = [{"title": "St1", "description": "The departure.", "weight": 1.0}]
        scene_plans_json = [{"title": "S1", "description": "Leaving home.", "weight": 1.0}]
        with install_router_usage(
            *return_mixed_router_usage(
                Value(meta, "model"),
                Value(chapter_plans_json, "json"),
                Value(story_plans_json, "json"),
                Value(scene_plans_json, "json"),
                raw_value("He left."),
            )
        ):
            epub = await task.delegate(namespace)

        assert epub == persist_dir / "novel.epub"
        assert epub.is_file()
        assert any(persist_dir.glob("Novel_*.json"))
        assert sorted(p.name for p in persist_dir.iterdir() if p.is_dir()) == [
            "stage_01_init",
            "stage_02_metadata",
            "stage_03_characters",
            "stage_04_chapter_plans",
            "stage_05_story_plans",
            "stage_06_scene_plans",
            "stage_07_scenes",
            "stage_08_novel",
        ]
        for stage_dir in persist_dir.iterdir():
            if stage_dir.is_dir():
                assert any(stage_dir.glob("*.json")), f"{stage_dir.name} lacks a snapshot"
