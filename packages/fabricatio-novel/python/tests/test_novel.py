"""Test module for fabricatio-novel contexts, models, and generation capabilities."""

from pathlib import Path
from typing import List

import pytest
from fabricatio_character.models.character import CharacterCard, CharacterCardDiff, CharacterCardSlices
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import (
    Value,
    return_json_router_usage,
    return_mixed_router_usage,
    return_model_json_router_usage,
    return_router_usage,
)
from fabricatio_mock.utils import code_block, generic_block, install_router_usage
from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.capabilities.rag import RAGCompose
from fabricatio_novel.models.context.base import CharacterTrace
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.novel import Novel
from fabricatio_novel.models.plan import ChapterPlan, NovelPlan, ScenePlan, StoryPlan
from fabricatio_novel.models.rag import WritingStyleDocument, WritingStyleFetchConfig
from fabricatio_novel.models.scene import Scene
from fabricatio_novel.models.series_book import SeriesBible


def card(name: str = "Hero", look: str = "tall") -> CharacterCard:
    """Build a default protagonist CharacterCard for tests."""
    return CharacterCard(name=name, role="protagonist", look=look, act="brave", want="seek truth", flaw="stubborn")


def raw_value(text: str) -> Value[str]:
    """Wrap a plain scene response for mixed router usage."""
    return Value(text, "raw", convertor=lambda s: s)


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
            series_bible=SeriesBible(characters="Hero — brave protagonist."),
        )
        result = ctx.update_from(plan)
        assert result is ctx
        assert ctx.title == "The Search"
        assert ctx.description == "A hero searching."
        assert ctx.expected_word_count == 100
        assert ctx.series_bible == plan.series_bible

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
            .set_prefixed_content("Before.")
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
        assert scene.prefixed_content == "Before."
        assert scene.language == "English"
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


class TestCharactorTrace:
    """Test suite for CharactorTrace."""

    def test_iter_charactor_cards_applies_diffs_in_order(self) -> None:
        """Assert iter_character_cards yields start then one card per interpolated diff."""
        start = card()
        diff = CharacterCardDiff(look="scarred", reason="took a blade")
        trace = CharacterTrace(start=start, interpolates=[diff])
        cards: List[CharacterCard] = list(trace.iter_character_cards())
        assert cards[0] is start
        assert [c.look for c in cards] == ["tall", "scarred"]
        # the final card is the derived end state, equal to the fold of the diffs
        assert cards[-1] == start.apply(diff)
        assert trace.end == start.apply(diff)

    def test_intepl_replaces_interpolates_and_returns_self(self) -> None:
        """Assert intepl replaces the interpolates list and returns the trace itself."""
        start = card()
        trace = CharacterTrace(start=start)
        diff = CharacterCardDiff(look="wounded", reason="fell in battle")
        assert trace.intepl([diff]) is trace
        assert trace.interpolates == [diff]

    def test_dump_to_prompt_shows_start_and_only_changed_fields(self) -> None:
        """Assert the prompt renders the identity once and each change with its reason."""
        start = card()
        trace = CharacterTrace(
            start=start,
            interpolates=[
                CharacterCardDiff(look="wounded", reason="fell in battle"),
                CharacterCardDiff(act="cautious", reason="learned from defeat"),
                CharacterCardDiff(reason="reflected"),
            ],
        )
        prompt = trace.dump_to_prompt()
        lines = prompt.splitlines()
        assert lines[0].startswith("Hero — protagonist.")
        assert "look: tall" in lines[0]
        assert "flaw: stubborn" in lines[0]
        assert "look: tall → wounded; reason: fell in battle" in lines[1]
        assert "act: brave → cautious; reason: learned from defeat" in lines[2]
        # a diff that changes nothing renders only its labeled reason
        assert lines[3] == "3. reason: reflected"
        # unchanged fields are not repeated per step
        assert prompt.count("flaw: stubborn") == 1
        assert prompt.count("want: seek truth") == 1

    def test_dump_to_prompt_without_changes_is_just_identity(self) -> None:
        """Assert a fresh trace renders only its starting card line."""
        start = card()
        trace = CharacterTrace(start=start)
        assert trace.dump_to_prompt() == (
            "Hero — protagonist. look: tall | act: brave | want: seek truth | flaw: stubborn"
        )


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
        assert ctx.writing_style == "Gothic, lyrical prose."
        assert ctx.scene_plan is plan

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


class TestCharactorTraces:
    """Test suite for hierarchical character state chains."""

    async def test_create_charactor_traces_skips_without_roster(self) -> None:
        """Assert trace creation is skipped without a bible roster."""
        role = NovelRole(name="novel_role")
        ctx = NovelContext.create("The hero.", language="English")
        await role.create_charactor_traces(ctx)
        assert ctx.character_trace == []

    async def test_create_charactor_traces_from_bible(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert the bible roster seeds one trace per character."""
        role = NovelRole(name="novel_role")
        ctx = NovelContext.create("The hero.", language="English")
        ctx.set_series_bible(SeriesBible(characters="Hero — brave.\nVillain — cruel."))
        hero = card()
        villain = card(name="Villain", look="dark")

        async def fake_compose(requirements: list[str], **kwargs: object) -> list[CharacterCard | None]:
            return [hero, villain]

        monkeypatch.setattr(NovelRole, "compose_characters", staticmethod(fake_compose))
        await role.create_charactor_traces(ctx)
        assert [t.start.name for t in ctx.character_trace] == ["Hero", "Villain"]
        assert all(t.start == t.end for t in ctx.character_trace)

    async def test_compose_novel_builds_hierarchical_chains(self) -> None:
        """Assert each level extends its allocated slice of the parent chain, without mutating it."""
        role = NovelRole(name="novel_role")
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        bible = SeriesBible(characters="Hero — brave protagonist.")
        ctx.set_series_bible(bible)
        meta = NovelPlan(
            title="The Search", description="A hero searching.", expected_word_count=100, series_bible=bible
        )
        hero = card()
        d_novel = CharacterCardDiff(look="wounded", reason="fell in battle")
        d_chapter = CharacterCardDiff(act="cautious", reason="learned from defeat")
        d_story = CharacterCardDiff(flaw="distrustful", reason="betrayed once")
        d_scene = CharacterCardDiff(want="find his father", reason="learned the truth")
        chapter_plans_json = [{"title": "Ch1", "description": "The start.", "weight": 1.0}]
        story_plans_json = [{"title": "St1", "description": "The departure.", "weight": 1.0}]
        scene_plans_json = [{"title": "S1", "description": "Leaving home.", "weight": 1.0}]
        with install_router_usage(
            *return_mixed_router_usage(
                Value(meta, "model"),
                Value(hero, "model"),
                Value([d_novel.model_dump()], "json"),
                Value(chapter_plans_json, "json"),
                Value([[d_novel.model_dump()]], "json"),
                Value([d_chapter.model_dump()], "json"),
                Value(story_plans_json, "json"),
                Value([[d_novel.model_dump(), d_chapter.model_dump()]], "json"),
                Value([d_story.model_dump()], "json"),
                Value(scene_plans_json, "json"),
                Value([[d_novel.model_dump(), d_chapter.model_dump(), d_story.model_dump()]], "json"),
                Value([d_scene.model_dump()], "json"),
                raw_value("He left."),
            )
        ):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        novel_trace = ctx.character_trace[0]
        chapter_trace = ctx.chapter_context[0].character_trace[0]
        story_trace = ctx.chapter_context[0].story_context[0].character_trace[0]
        scene_trace = ctx.chapter_context[0].story_context[0].scene_context[0].character_trace[0]
        assert novel_trace.interpolates == [d_novel]
        assert chapter_trace.interpolates == [d_novel, d_chapter]
        assert story_trace.interpolates == [d_novel, d_chapter, d_story]
        assert scene_trace.interpolates == [d_novel, d_chapter, d_story, d_scene]
        # extending a child must not mutate the parent's chain
        assert novel_trace.interpolates == [d_novel]
        assert novel_trace.end.look == "wounded"
        assert scene_trace.end.want == "find his father"

    async def test_split_charactor_slices_assigns_per_child(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert the chain splits into aligned per-child slices with recomputed ends."""
        role = NovelRole(name="novel_role")
        ctx = NovelContext.create("The hero.", language="English")
        hero = card()
        d1 = CharacterCardDiff(look="wounded", reason="fell in battle")
        d2 = CharacterCardDiff(look="scarred", reason="took a blade")
        ctx.set_charactor_traces([CharacterTrace(start=hero, interpolates=[d1, d2])])
        child_a = ChapterContext(title="Ch1", description="The start.")
        child_b = ChapterContext(title="Ch2", description="The road.")

        async def fake_ask(question: object, validator: object, **kwargs: object) -> list[CharacterCardSlices]:
            return [CharacterCardSlices(root=[[d1], [d2]])]

        monkeypatch.setattr(NovelRole, "aask_validate", staticmethod(fake_ask))
        await role.split_character_slices(ctx, [child_a, child_b])

        assert child_a.character_trace[0].interpolates == [d1]
        assert child_b.character_trace[0].interpolates == [d2]
        assert child_a.character_trace[0].start == hero
        assert child_a.character_trace[0].end.look == "wounded"
        assert child_b.character_trace[0].end.look == "scarred"

    async def test_scene_requirement_shows_character_chain(self) -> None:
        """Assert every state of the arc appears in the scene prompt's Characters section."""
        role = NovelRole(name="novel_role")
        ctx = SceneContext(title="S2", description="A stranger appears.", expected_word_count=50)
        hero = card()
        ctx.character_trace = [
            CharacterTrace(
                start=hero,
                interpolates=[CharacterCardDiff(look="scarred", reason="took a blade")],
            )
        ]
        requirement = await role.prepare_scene_requirement(ctx)
        assert "Hero — protagonist." in requirement
        assert "look: tall → scarred" in requirement
        assert "took a blade" in requirement


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

    async def test_compose_scene_evolves_charactor_trace(self) -> None:
        """Assert compose_scene applies the proposed diff to the scene's character trace."""
        role = NovelRole(name="novel_role")
        trace = CharacterTrace(start=card())
        ctx = SceneContext(title="Battle", description="The hero fights.", expected_word_count=50)
        ctx.character_trace.append(trace)
        expected_diff = CharacterCardDiff(look="scarred", reason="took a blade")
        with install_router_usage(
            *return_mixed_router_usage(
                Value([expected_diff.model_dump()], "json"),
                raw_value("He fought."),
            )
        ):
            scene = await role.compose_scene(ctx)
        assert scene is not None
        assert trace.interpolates == [expected_diff]
        assert trace.end.look == "scarred"

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
        assert (
            ctx.chapter_context[0].story_context[0].scene_context[1].prefixed_content == f"{chapter_header}\n\nHe left."
        )
        assert ctx.chapter_context[0].story_context[0].scene_context[0].prefixed_content == chapter_header

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
        ctx.prefixed_content = "He walked into the dark."

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
        ctx.writing_style = "Terse action lines, present tense, close third person."
        requirement = await role.prepare_scene_requirement(ctx)
        assert "## Writing Style" in requirement
        assert "Terse action lines, present tense, close third person." in requirement
        assert requirement.index("## Writing Style") > requirement.index("## Scene")

    async def test_prepare_scene_requirement_skips_writing_style_when_empty(self) -> None:
        """Assert an unset writing style renders no style section."""
        role = NovelRole(name="novel_role")
        ctx = SceneContext(title="S2", description="A stranger appears.", expected_word_count=50)
        requirement = await role.prepare_scene_requirement(ctx)
        assert "## Writing Style" not in requirement


class TestPrefixAccumulation:
    """Test suite for prefixed_content dependency injection across levels."""

    def _scene_ctx(self, title: str, description: str) -> SceneContext:
        return SceneContext(title=title, description=description, expected_word_count=20)

    async def test_compose_story_injects_prefix_across_scenes(self) -> None:
        """Assert later scenes accumulate earlier scene content into prefixed_content."""
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
        assert scene_1.prefixed_content == ""
        assert scene_2.prefixed_content == "He left."

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
        assert story_a.prefixed_content == chapter_header
        assert story_b.prefixed_content == f"{chapter_header}\n\n{story_a_block}"
        assert story_b.scene_context[0].prefixed_content == f"{chapter_header}\n\n{story_a_block}"

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
        assert chapter_1.prefixed_content == ""
        assert chapter_2.prefixed_content == chapter_1_block
        assert chapter_1.story_context[1].prefixed_content == f"{chapter_1_header}\n\nA."
        assert chapter_2.story_context[0].prefixed_content == f"{chapter_1_block}\n\n{chapter_2_header}"
        assert (
            chapter_2.story_context[1].prefixed_content == f"{chapter_1_block}\n\n{chapter_2_header}\n\n{story_c_block}"
        )
        assert (
            chapter_2.story_context[0].scene_context[0].prefixed_content == f"{chapter_1_block}\n\n{chapter_2_header}"
        )
        assert (
            chapter_2.story_context[1].scene_context[0].prefixed_content
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

    async def test_prepare_scene_requirement_injects_style_digest(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert the RAG digest renders as a Writing Style Guideline with no raw reference section."""
        role = RAGRole(name="rag_role")
        ctx = SceneContext(title="Battle", description="The hero fights the dragon.", expected_word_count=50)
        doc = WritingStyleDocument.with_text_chunk("Dark gothic prose with terse action lines.")

        async def fake_fetch(query: str, config: object | None = None) -> List[WritingStyleDocument]:
            return [doc]

        async def fake_rank(
            query: str, documents: List[WritingStyleDocument], **kwargs: object
        ) -> List[WritingStyleDocument]:
            return documents

        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))
        monkeypatch.setattr(RAGRole, "arank_documents", staticmethod(fake_rank))
        with install_router_usage(
            *return_router_usage(
                code_block(
                    '["hero fights dragon", "dragon weaknesses", "battle choreography", "dark gothic prose", "terse action lines", "victory conditions"]'
                ),
                generic_block("Use dark gothic prose with terse action lines.", "String"),
            )
        ):
            requirement = await role.prepare_scene_requirement(ctx)

        assert "## Writing Style Guideline" in requirement
        assert "Use dark gothic prose with terse action lines." in requirement
        assert "## Writing Style References" not in requirement

    async def test_prepare_scene_requirement_skips_digest_when_digest_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert a failed style digest leaves the scene requirement unchanged."""
        role = RAGRole(name="rag_role")
        ctx = SceneContext(title="Battle", description="The hero fights the dragon.", expected_word_count=50)
        doc = WritingStyleDocument.with_text_chunk("Dark gothic prose with terse action lines.")

        async def fake_fetch(query: str, config: object | None = None) -> List[WritingStyleDocument]:
            return [doc]

        async def fake_rank(
            query: str, documents: List[WritingStyleDocument], **kwargs: object
        ) -> List[WritingStyleDocument]:
            return documents

        async def fake_digest(prompt: str, **kwargs: object) -> str | None:
            return None

        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))
        monkeypatch.setattr(RAGRole, "arank_documents", staticmethod(fake_rank))
        monkeypatch.setattr(RAGRole, "ageneric_string", staticmethod(fake_digest))
        with install_router_usage(*return_json_router_usage('["hero fights dragon"]')):
            requirement = await role.prepare_scene_requirement(ctx)

        assert "## Writing Style Guideline" not in requirement
        assert "The hero fights the dragon." in requirement

    async def test_prepare_scene_requirement_without_docs_keeps_base(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert empty fetched docs leave the base scene requirement unchanged."""
        role = RAGRole(name="rag_role")
        ctx = SceneContext(title="Battle", description="The hero fights.", expected_word_count=50)

        async def fake_fetch(query: str, config: object | None = None) -> List[WritingStyleDocument]:
            return []

        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))
        with install_router_usage(*return_json_router_usage('["hero fights"]')):
            requirement = await role.prepare_scene_requirement(ctx)

        assert "## Writing Style Guideline" not in requirement
        assert "The hero fights." in requirement

    async def test_fetch_style_docs_combines_query_uses_limit_and_reranks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert _fetch_style_docs joins description and rag_query, applies the per-head limit, and reranks."""
        role = RAGRole(name="rag_role")
        ctx = SceneContext(title="Battle", description="The hero fights.", expected_word_count=50)
        ctx.set_rag_query("中文查询指南").set_rag_limit(7)
        doc = WritingStyleDocument.with_text_chunk("Dark gothic prose.")
        captured_queries: List[str] = []
        captured_configs: List[WritingStyleFetchConfig] = []
        ranked_queries: List[str] = []

        async def fake_refine(question: str, **kwargs: object) -> List[str]:
            captured_queries.append(question)
            return ["查询一", "查询二"]

        async def fake_fetch(
            query: object, config: WritingStyleFetchConfig | None = None
        ) -> List[WritingStyleDocument]:
            if config is not None:
                captured_configs.append(config)
            return [doc] * 8

        async def fake_rank(
            query: str, documents: List[WritingStyleDocument], **kwargs: object
        ) -> List[WritingStyleDocument]:
            ranked_queries.append(query)
            return documents

        monkeypatch.setattr(RAGRole, "arefined_query", staticmethod(fake_refine))
        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))
        monkeypatch.setattr(RAGRole, "arank_documents", staticmethod(fake_rank))

        docs = await role._fetch_style_docs(ctx)

        assert docs == [doc] * 7
        assert captured_queries == ["The hero fights.\n中文查询指南"]
        assert captured_configs
        assert captured_configs[0].limit == 7
        assert ranked_queries == ["The hero fights.\n中文查询指南"]

    async def test_fetch_style_docs_defaults_to_scene_description(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert _fetch_style_docs falls back to the scene description as the refine question."""
        role = RAGRole(name="rag_role")
        ctx = SceneContext(title="Battle", description="The hero fights.", expected_word_count=50)
        captured_queries: List[str] = []

        async def fake_refine(question: str, **kwargs: object) -> List[str]:
            captured_queries.append(question)
            return ["hero fights"]

        async def fake_fetch(
            query: object, config: WritingStyleFetchConfig | None = None
        ) -> List[WritingStyleDocument]:
            return []

        monkeypatch.setattr(RAGRole, "arefined_query", staticmethod(fake_refine))
        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))

        await role._fetch_style_docs(ctx)

        assert captured_queries == ["The hero fights."]

    async def test_rag_settings_propagate_to_scene_contexts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert retrieval settings set on a parent flow down to the composed scenes."""
        role = RAGRole(name="rag_role")
        story = StoryContext(title="St1", description="The departure.")
        story.set_rag_query("guide").set_rag_limit(7)

        async def fake_refine(question: str, **kwargs: object) -> List[str]:
            return []

        async def fake_fetch(
            query: object, config: WritingStyleFetchConfig | None = None
        ) -> List[WritingStyleDocument]:
            return []

        monkeypatch.setattr(RAGRole, "arefined_query", staticmethod(fake_refine))
        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))
        with install_router_usage(
            *return_router_usage('[{"title": "S1", "description": "Leaving home.", "weight": 1.0}]', "He left.")
        ):
            result = await role.compose_story(story)

        assert result is not None
        assert story.scene_context[0].rag_query == "guide"
        assert story.scene_context[0].rag_limit == 7

    async def test_fetch_style_docs_skips_blank_prompt_docs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert docs whose prompt renders blank never reach the reranker."""
        role = RAGRole(name="rag_role")
        ctx = SceneContext(title="Battle", description="The hero fights.", expected_word_count=50)
        doc = WritingStyleDocument.with_text_chunk("Dark gothic prose.")
        blank = WritingStyleDocument.with_text_chunk("   ")
        reranked_queries: List[str] = []

        async def fake_refine(question: str, **kwargs: object) -> List[str]:
            return ["q"]

        async def fake_fetch(
            query: object, config: WritingStyleFetchConfig | None = None
        ) -> List[WritingStyleDocument]:
            return [blank, doc, blank]

        async def fake_rank(
            query: str, documents: List[WritingStyleDocument], **kwargs: object
        ) -> List[WritingStyleDocument]:
            reranked_queries.append(query)
            return documents

        monkeypatch.setattr(RAGRole, "arefined_query", staticmethod(fake_refine))
        monkeypatch.setattr(RAGRole, "afetch_document", staticmethod(fake_fetch))
        monkeypatch.setattr(RAGRole, "arank_documents", staticmethod(fake_rank))

        docs = await role._fetch_style_docs(ctx)

        assert docs == [doc]
        assert reranked_queries == ["The hero fights."]
