"""Composition-chain tests for fabricatio-novel with mock LLM routers."""

from typing import Unpack

import pytest
from _support import card, prefix_log, unguarded, unguarded_role
from fabricatio_character.models.character import CharacterSpan
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK
from fabricatio_mock import MockScript, Value, make_test_role
from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.plan import NovelPlan, ScenePlan
from fabricatio_novel.models.refusal import SceneRefusedError
from fabricatio_novel.models.series_book import SeriesBible


class TestCharacterSpans:
    """Test suite for the per-level CharacterSpan pipeline."""

    async def test_compose_novel_stitches_chapter_boundaries_to_roster_ends(self) -> None:
        """Assert N chapters need N-1 boundary cards; chapter 1 starts at the novel start and the last ends at the novel end."""
        role = unguarded_role()
        ctx = NovelContext.create("The hero seeks his father..", language="English")
        bible = SeriesBible(characters=["Hero — brave protagonist."])
        ctx.set_series_bible(bible)
        meta = NovelPlan(
            title="The Search",
            description="A hero searching.",
            expected_word_count=100,
            writing_styles=[],
            writing_constraints=[],
        )
        novel_start = card()
        novel_end = novel_start.model_copy(update={"look": "wounded"})
        chapter_boundary = novel_start.model_copy(update={"act": "cautious"})
        chapter_plans_json = [
            {
                "title": "Ch1",
                "description": "The start.",
                "weight": 1.0,
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
            Value.from_json([CharacterSpan(start=novel_start, end=novel_end).model_dump()], name="novel spans"),
            Value.from_json(chapter_plans_json, name="chapter plans"),
            # 2 chapters -> 1 boundary card per roster character
            Value.from_json([[chapter_boundary.model_dump()]], name="chapter boundary spans"),
            Value.from_json(story_plans_json, name="chapter 1 story plans"),
            Value.from_json(scene_plans_json, name="chapter 1 scene plans"),
            Value.from_text("He left.", name="chapter 1 scene prose"),
            Value.from_json(story_plans_json, name="chapter 2 story plans"),
            Value.from_json(scene_plans_json, name="chapter 2 scene plans"),
            Value.from_text("He walked.", name="chapter 2 scene prose"),
        ):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        assert len(ctx.charactor_span) == 1
        assert ctx.charactor_span[0].start.name == "Hero"
        assert ctx.charactor_span[0].end.look == "wounded"
        # chapter 1 opens at the novel start and closes at the boundary
        ch1 = ctx.child_contexts[0]
        assert len(ch1.charactor_span) == 1
        assert ch1.charactor_span[0].start.look == "tall"
        assert ch1.charactor_span[0].end.act == "cautious"
        # chapter 2 opens at the boundary and closes at the novel end
        ch2 = ctx.child_contexts[1]
        assert len(ch2.charactor_span) == 1
        assert ch2.charactor_span[0].start.act == "cautious"
        assert ch2.charactor_span[0].end.look == "wounded"
        # a single story inherits the chapter span directly, and scenes broadcast it
        story_ctx = ch1.child_contexts[0]
        assert story_ctx.charactor_span is ch1.charactor_span
        scene_ctx = story_ctx.child_contexts[0]
        assert scene_ctx.charactor_span is ch1.charactor_span
        requirement = await role.prepare_scene_requirement(scene_ctx)
        assert "Initial State:" in requirement
        assert "finalizing State:" in requirement
        assert "## Act" in requirement
        assert "cautious" in requirement

    async def test_draft_chapter_spans_single_chapter_inherits_roster(self) -> None:
        """Assert a single chapter gets the roster spans directly without an LLM call."""
        role = unguarded_role()
        ctx = NovelContext.create("The hero..", language="English")
        span = CharacterSpan(start=card(), end=card())
        ctx.set_charactor_spans([span])
        ctx.add_context(ChapterContext(title="Ch1", description="The start."))
        await role.draft_chapter_spans(ctx)
        assert ctx.child_contexts[0].charactor_span is ctx.charactor_span

    async def test_draft_story_spans_single_story_inherits_chapter_span(self) -> None:
        """Assert a single story gets the chapter's spans directly without an LLM call."""
        role = unguarded_role()
        chapter = ChapterContext(title="Ch1", description="The start.")
        span = CharacterSpan(start=card(), end=card())
        chapter.set_charactor_spans([span])
        chapter.add_context(StoryContext(title="St1", description="The departure."))
        await role.draft_story_spans(chapter)
        assert chapter.child_contexts[0].charactor_span is chapter.charactor_span

    async def test_scene_requirement_shows_character_span(self) -> None:
        """Assert the scene prompt renders the broadcast span's start and end."""
        role = unguarded_role()
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
        role = unguarded_role()
        ctx = SceneContext(title="Departure", description="The hero leaves home.", expected_word_count=50)
        with MockScript.from_values(Value.from_text("He walked out.", name="scene prose")):
            scene = await role.compose_scene(ctx)
        assert scene is not None
        assert scene.content == "He walked out."
        assert scene.expected_word_count == 50
        assert ctx.content == "He walked out."

    async def test_compose_novel_broadcasts_story_span_to_scenes(self) -> None:
        """Assert every scene inherits the story's spans when prepare_scene_write runs."""
        role = unguarded_role()
        story = StoryContext(title="St1", description="The departure.")
        span = CharacterSpan(start=card(), end=card())
        story.set_charactor_spans([span])
        scene_ctx = SceneContext(title="Battle", description="The hero fights.", expected_word_count=50)
        story.child_contexts.append(scene_ctx)
        with MockScript.from_values(Value.from_text("He fought.", name="scene prose")):
            await role.prepare_scene_write(story)
            scene = await role.compose_scene(scene_ctx)
        assert scene is not None
        assert scene_ctx.charactor_span is story.charactor_span
        assert scene_ctx.charactor_span == [span]

    async def test_compose_novel_end_to_end(self) -> None:
        """Assert a full composition fills content and prefixes across a prefilled tree."""
        role = unguarded_role()
        ctx = NovelContext.create("The hero seeks his father..", language="English")
        chapter_ctx = ChapterContext(title="Ch1", description="The hero sets out.")
        story_ctx = StoryContext(title="St1", description="The departure.")
        scene_1 = SceneContext(title="S1", description="Leaving home.", expected_word_count=20)
        scene_2 = SceneContext(title="S2", description="A stranger appears.", expected_word_count=20)
        story_ctx.child_contexts.extend([scene_1, scene_2])
        chapter_ctx.child_contexts.append(story_ctx)
        ctx.child_contexts.append(chapter_ctx)

        meta = NovelPlan(
            title="The Search",
            description="A hero searching for his father.",
            expected_word_count=40,
            writing_styles=[],
            writing_constraints=[],
        )

        with MockScript.from_values(
            Value.from_model(meta, name="novel metadata"),
            Value.from_text("He left.", name="scene 1 prose"),
            Value.from_text("A stranger appeared.", name="scene 2 prose"),
        ):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        assert novel.title == "The Search"
        assert len(novel.chapter) == 1
        assert len(novel.chapter[0].story) == 1
        assert len(novel.chapter[0].story[0].scenes) == 2
        assert novel.chapter[0].story[0].scenes[1].content == "A stranger appeared."
        assert ctx.title == "The Search"
        assert ctx.child_contexts[0].child_contexts[0].child_contexts[1].content == "A stranger appeared."
        chapter_header = "# Ch1"
        scenes = ctx.child_contexts[0].child_contexts[0].child_contexts
        assert scenes[0].prefix_log.render() == chapter_header
        assert scenes[1].prefix_log.render() == f"{chapter_header}\n\nHe left."

    async def test_compose_novel_logs_progress_per_level(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Assert composition emits per-level progress and completion log lines."""
        role = unguarded_role()
        ctx = NovelContext.create("The hero seeks his father..", language="English")
        chapter_ctx = ChapterContext(title="Ch1", description="The hero sets out.")
        story_ctx = StoryContext(title="St1", description="The departure.")
        scene_1 = SceneContext(title="S1", description="Leaving home.", expected_word_count=20)
        scene_2 = SceneContext(title="S2", description="A stranger appears.", expected_word_count=20)
        story_ctx.child_contexts.extend([scene_1, scene_2])
        chapter_ctx.child_contexts.append(story_ctx)
        ctx.child_contexts.append(chapter_ctx)
        meta = NovelPlan(
            title="The Search",
            description="A hero searching for his father.",
            expected_word_count=40,
            writing_styles=[],
            writing_constraints=[],
        )

        with MockScript.from_values(
            Value.from_model(meta, name="novel metadata"),
            Value.from_text("He left.", name="scene 1 prose"),
            Value.from_text("A stranger appeared.", name="scene 2 prose"),
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
        role = unguarded_role()
        ctx = NovelContext.create("The hero..", language="English")
        with MockScript.from_values(
            Value.from_text("not valid json", name="invalid metadata response"),
            Value.from_text("", name="empty response 2"),
            Value.from_text("", name="empty response 3"),
        ):
            novel = await role.compose_novel(ctx)
        assert novel is None

    async def test_prepare_scene_requirement_leads_with_novel_so_far(self) -> None:
        """Assert the novel-so-far block leads the prompt and the stage instructions follow it."""
        role = unguarded_role()
        ctx = SceneContext(title="S2", description="A stranger appears.", expected_word_count=50)
        ctx.set_prefix_log(prefix_log("He walked into the dark.", title="S2"))

        requirement = await role.prepare_scene_requirement(ctx)

        # the shared manuscript context leads so the provider prefix cache hits across stages
        assert requirement.startswith("--- Start of Novel so far ---")
        assert requirement.index("He walked into the dark.") < requirement.index("--- End of Novel so far ---")
        assert requirement.index("# Scene Writing") > requirement.index("--- End of Novel so far ---")
        assert requirement.index("A stranger appears.") > requirement.index("## Scene")
        # the per-scene word count must not sit inside the static Requirements block
        assert requirement.index("Write approximately 50 words.") > requirement.index("Respond entirely in")

    async def test_prepare_scene_requirement_renders_writing_styles(self) -> None:
        """Assert the accumulated style entries render together inside the styles section."""
        role = unguarded_role()
        ctx = SceneContext(title="S2", description="A stranger appears.", expected_word_count=50)
        ctx.set_writing_styles(["Terse action lines, present tense, close third person."])
        ctx.set_plan(
            ScenePlan(
                title="S2",
                description="A stranger appears.",
                writing_styles=["Close first person."],
                writing_constraints=[],
            ),
        )
        requirement = await role.prepare_scene_requirement(ctx)
        assert "### Writing styles" in requirement
        assert "Terse action lines, present tense, close third person." in requirement
        assert requirement.index("## Scene") < requirement.index("### Writing styles")

    async def test_prepare_scene_requirement_skips_writing_style_when_empty(self) -> None:
        """Assert an unset writing style renders no style section."""
        role = unguarded_role()
        ctx = SceneContext(title="S2", description="A stranger appears.", expected_word_count=50)
        requirement = await role.prepare_scene_requirement(ctx)
        assert "### Writing styles" not in requirement

    async def test_prepare_scene_requirement_renders_writing_constraint(self) -> None:
        """Assert the scene's accumulated writing constraint guides the prose requirement."""
        role = unguarded_role()
        ctx = SceneContext(title="S2", description="A stranger appears.", expected_word_count=50)
        ctx.writing_constraints = ["First person view throughout."]
        requirement = await role.prepare_scene_requirement(ctx)
        assert "### Writing Constrains:" in requirement
        assert "First person view throughout." in requirement
        assert requirement.index("### Writing Constrains:") > requirement.index("## Scene")

    async def test_prepare_scene_requirement_skips_writing_constraint_when_empty(self) -> None:
        """Assert an unset writing constraint renders no constraint section."""
        role = unguarded_role()
        ctx = SceneContext(title="S2", description="A stranger appears.", expected_word_count=50)
        requirement = await role.prepare_scene_requirement(ctx)
        assert "### Writing Constrains:" not in requirement

    async def test_scene_requirement_renders_cast(self) -> None:
        """Assert the scene's cast renders as an on-stage roster in the prose requirement."""
        role = unguarded_role()
        ctx = SceneContext(title="S2", description="A stranger appears.", expected_word_count=50)
        ctx.set_cast(["Hero", "Villain"])
        requirement = await role.prepare_scene_requirement(ctx)
        assert "## Scene Cast" in requirement
        assert "- Hero\n- Villain" in requirement

    async def test_scene_requirement_omits_cast_when_empty(self) -> None:
        """Assert an empty cast renders no cast section."""
        role = unguarded_role()
        ctx = SceneContext(title="S2", description="A stranger appears.", expected_word_count=50)
        requirement = await role.prepare_scene_requirement(ctx)
        assert "## Cast" not in requirement

    async def test_plan_scenes_renders_story_cast(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert scene planning sees the story's cast as context."""
        role = unguarded_role()
        story = StoryContext(title="St1", description="The departure.")
        story.set_cast(["Hero", "Villain"])
        captured: list[str] = []

        async def fake_propose(model: object, requirement: str, **kwargs: object) -> None:
            captured.append(requirement)

        monkeypatch.setattr(type(role), "propose", staticmethod(fake_propose))
        await role.plan_scenes(story)

        assert captured
        assert "## Story Cast" in captured[0]
        assert "- Hero\n- Villain" in captured[0]

    async def test_plan_stories_renders_chapter_cast(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert story planning sees the chapter's cast as context."""
        role = unguarded_role()
        chapter = ChapterContext(title="Ch1", description="The start.")
        chapter.set_cast(["Hero"])
        captured: list[str] = []

        async def fake_propose(model: object, requirement: str, **kwargs: object) -> None:
            captured.append(requirement)

        monkeypatch.setattr(type(role), "propose", staticmethod(fake_propose))
        await role.plan_stories(chapter)

        assert captured
        assert "## Chapter Cast" in captured[0]
        assert "Hero" in captured[0]

    async def test_plan_scenes_pins_the_units_to_the_story(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert scene planning scopes the batch to the story and states the scope requirements."""
        role = unguarded_role()
        story = StoryContext(title="St1", description="The road.", expected_word_count=100)
        captured: list[str] = []

        async def fake_propose(model: object, requirement: str, **kwargs: object) -> None:
            captured.append(requirement)

        monkeypatch.setattr(type(role), "propose", staticmethod(fake_propose))
        await role.plan_scenes(story)

        assert captured
        assert "## Requirements" in captured[0]
        assert "Title: St1" in captured[0]
        assert "Description: The road." in captured[0]

    async def test_compose_scene_retries_a_blank_generation_then_fails(self) -> None:
        """Assert a blank generation is retried like a refusal and then fails loudly instead of composing an empty scene."""
        role = make_test_role(NovelCompose, name="novel_role")
        ctx = SceneContext(title="S1", description="Leaving home.", expected_word_count=50)
        with (
            MockScript.from_values(
                Value.from_text("", name="empty scene"),
                Value.from_text("", name="empty scene"),
                Value.from_text("", name="empty scene"),
                Value.from_text("", name="empty scene"),
            ),
            pytest.raises(SceneRefusedError, match="read as a refusal on every one of its 4 attempt"),
        ):
            await role.compose_scene(ctx)

        assert not ctx.content


class TestPrefixAccumulation:
    """Test suite for prefix log dependency injection across levels."""

    def _scene_ctx(self, title: str, description: str) -> SceneContext:
        return SceneContext(title=title, description=description, expected_word_count=20)

    def _two_chapter_novel(self) -> NovelContext:
        """Build a two-chapter novel whose first chapter is written and whose second is not."""
        novel = NovelContext.create("The hero seeks his father..", language="English")
        for chapter_title in ("Ch1", "Ch2"):
            chapter = ChapterContext(title=chapter_title, description="A chapter.")
            story = StoryContext(title="St1", description="The departure.")
            story.add_context(self._scene_ctx(f"{chapter_title}S1", "Leaving home.").set_content("He left."))
            story.add_context(self._scene_ctx(f"{chapter_title}S2", "A stranger appears."))
            chapter.add_context(story)
            novel.add_context(chapter)
        return novel

    def test_chapter_opening_flag_matches_the_scene_index(self) -> None:
        """Assert a scene reports a chapter opening exactly when it is its chapter's first scene."""
        novel = self._two_chapter_novel()

        openings = [
            (chapter.title, index, scene.is_chapter_opening())
            for chapter in novel.iter_prefixed_contexts()
            for index, _story, scene in chapter.iter_scenes()
        ]

        assert openings == [("Ch1", 1, True), ("Ch1", 2, False), ("Ch2", 1, True), ("Ch2", 2, False)]

    async def test_chapter_opener_prompt_announces_the_unwritten_chapter(self) -> None:
        """Assert a chapter's first scene prompts for the chapter opening while later scenes do not."""
        role = unguarded_role()
        chapter_2 = list(self._two_chapter_novel().iter_prefixed_contexts())[1]
        opener, later = [scene for _index, _story, scene in chapter_2.iter_scenes()]

        opener_prompt = await role.prepare_scene_requirement(opener)
        later_prompt = await role.prepare_scene_requirement(later)

        assert "## Chapter Opening" in opener_prompt
        assert "nothing of the chapter is written yet" in opener_prompt
        assert opener_prompt.index("## Scene") < opener_prompt.index("## Chapter Opening")
        assert opener_prompt.index("## Chapter Opening") < opener_prompt.index("## Goal")
        assert "## Chapter Opening" not in later_prompt

    async def test_compose_story_injects_prefix_across_scenes(self) -> None:
        """Assert later scenes accumulate earlier scene content into scenes_so_far."""
        role = unguarded_role()
        story = StoryContext(title="St1", description="The departure.")
        scene_1 = self._scene_ctx("S1", "Leaving home.")
        scene_2 = self._scene_ctx("S2", "A stranger appears.")
        story.add_context(scene_1).add_context(scene_2)
        with MockScript.from_values(
            Value.from_text("He left.", name="scene 1 prose"),
            Value.from_text("A stranger appeared.", name="scene 2 prose"),
        ):
            result = await role.compose_story(story)
        assert result is not None
        assert scene_1.prefix_log.render() == ""
        assert scene_2.prefix_log.render() == "He left."

    async def test_compose_chapter_injects_prefix_across_stories(self) -> None:
        """Assert stories inherit the chapter header plus prior story blocks as prefixed_content."""
        role = unguarded_role()
        chapter = ChapterContext(title="Ch1", description="The start.")
        story_a = StoryContext(title="StA", description="A.")
        story_a.add_context(self._scene_ctx("S1", "Leaving home."))
        story_b = StoryContext(title="StB", description="B.")
        story_b.add_context(self._scene_ctx("S2", "A stranger appears."))
        chapter.add_context(story_a).add_context(story_b)
        with MockScript.from_values(
            Value.from_text("Alpha.", name="story A scene prose"),
            Value.from_text("Beta.", name="story B scene prose"),
        ):
            result = await role.compose_chapter(chapter)
        assert result is not None
        story_a_block = "Alpha."
        # b05391cb seeds only the chapter title into prefixes: the description is a
        # whole-chapter synopsis and would leak later beats into every scene prompt.
        chapter_header = "# Ch1"
        assert story_a.prefix_log.render() == chapter_header
        assert story_b.prefix_log.render() == f"{chapter_header}\n\n{story_a_block}"
        assert story_b.child_contexts[0].prefix_log.render() == f"{chapter_header}\n\n{story_a_block}"

    async def test_compose_novel_injects_prefix_across_chapters_and_stories(self) -> None:
        """Assert chapter and story prefixed_content chain across the whole composed novel."""
        role = unguarded_role()
        ctx = NovelContext.create("The hero seeks his father..", language="English")
        ctx.title = "The Search"
        ctx.description = "A hero searching."
        ctx.expected_word_count = 80

        def story(title: str, scene_title: str, scene_description: str) -> StoryContext:
            s = StoryContext(title=title, description=scene_description)
            s.add_context(self._scene_ctx(scene_title, scene_description))
            return s

        chapter_1 = ChapterContext(title="Ch1", description="The start.")
        chapter_1.add_context(story("StA", "S1", "Leaving home."))
        chapter_1.add_context(story("StB", "S2", "A stranger appears."))
        chapter_2 = ChapterContext(title="Ch2", description="The road.")
        chapter_2.add_context(story("StC", "S3", "The journey."))
        chapter_2.add_context(story("StD", "S4", "The arrival."))
        ctx.add_context(chapter_1).add_context(chapter_2)

        meta = NovelPlan(
            title="The Search",
            description="A hero searching.",
            expected_word_count=80,
            writing_styles=[],
            writing_constraints=[],
        )
        with MockScript.from_values(
            Value.from_model(meta, name="novel metadata"),
            Value.from_text("A.", name="story A scene prose"),
            Value.from_text("B.", name="story B scene prose"),
            Value.from_text("C.", name="story C scene prose"),
            Value.from_text("D.", name="story D scene prose"),
        ):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        chapter_1_block = "# Ch1\n\nA.\n\nB."
        chapter_1_header = "# Ch1"
        chapter_2_header = "# Ch2"
        story_c_block = "C."
        assert chapter_1.prefix_log.render() == ""
        assert chapter_2.prefix_log.render() == chapter_1_block
        assert chapter_1.child_contexts[1].prefix_log.render() == f"{chapter_1_header}\n\nA."
        assert chapter_2.child_contexts[0].prefix_log.render() == f"{chapter_1_block}\n\n{chapter_2_header}"
        assert (
            chapter_2.child_contexts[1].prefix_log.render()
            == f"{chapter_1_block}\n\n{chapter_2_header}\n\n{story_c_block}"
        )
        assert (
            chapter_2.child_contexts[0].child_contexts[0].prefix_log.render()
            == f"{chapter_1_block}\n\n{chapter_2_header}"
        )
        assert (
            chapter_2.child_contexts[1].child_contexts[0].prefix_log.render()
            == f"{chapter_1_block}\n\n{chapter_2_header}\n\n{story_c_block}"
        )


class _HookMutating(NovelCompose):
    """Mixin whose after-compose hooks rename every level's context before assembly."""

    async def after_compose_novel_context(
        self, ctx: NovelContext, send_to: str | None = TASK, **kwargs: Unpack[LLMKwargs]
    ) -> NovelContext:
        ctx.title = "Hooked Novel"
        return ctx

    async def after_compose_chapter_context(
        self, ctx: ChapterContext, send_to: str | None = TASK, **kwargs: Unpack[LLMKwargs]
    ) -> ChapterContext:
        ctx.title = "Hooked Chapter"
        return ctx

    async def after_compose_story_context(
        self, ctx: StoryContext, send_to: str | None = TASK, **kwargs: Unpack[LLMKwargs]
    ) -> StoryContext:
        ctx.title = "Hooked Story"
        return ctx

    async def after_compose_scene_context(
        self, ctx: SceneContext, send_to: str | None = TASK, **kwargs: Unpack[LLMKwargs]
    ) -> SceneContext:
        ctx.title = "Hooked Scene"
        return ctx


class TestComposeHookOrdering:
    """Test suite for hook ordering: assembly must run after the after-compose hooks."""

    async def test_after_compose_hooks_land_in_assembled_outputs(self) -> None:
        """Assert after-compose context mutations reach the assembled tree; assembly used to run first."""
        role = unguarded(make_test_role(_HookMutating, name="hook_role"))
        ctx = NovelContext.create("The hero seeks his father..", language="English")
        chapter_ctx = ChapterContext(title="Ch1", description="The hero sets out.")
        story_ctx = StoryContext(title="St1", description="The departure.")
        story_ctx.child_contexts.append(SceneContext(title="S1", description="Leaving home.", expected_word_count=20))
        chapter_ctx.child_contexts.append(story_ctx)
        ctx.child_contexts.append(chapter_ctx)

        meta = NovelPlan(
            title="The Search",
            description="A hero searching for his father.",
            expected_word_count=20,
            writing_styles=[],
            writing_constraints=[],
        )
        with MockScript.from_values(
            Value.from_model(meta, name="novel metadata"),
            Value.from_text("He left.", name="scene prose"),
        ):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        assert novel.title == "Hooked Novel"
        assert novel.chapter[0].title == "Hooked Chapter"
        assert novel.chapter[0].story[0].title == "Hooked Story"
        assert novel.chapter[0].story[0].scenes[0].title == "Hooked Scene"
        assert novel.chapter[0].story[0].scenes[0].content == "He left."
