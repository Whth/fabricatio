"""Test module for the setting bible (设定集): models, creation, update, and consumption."""

import pytest
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import Value, return_mixed_router_usage, return_model_json_router_usage
from fabricatio_mock.utils import install_router_usage
from fabricatio_novel.capabilities.bible import BibleCompose, parse_sections
from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.plan import NovelPlan
from fabricatio_novel.models.scene import Scene
from fabricatio_novel.models.series_book import SeriesBible


class TestParseSections:
    """Test suite for the --sections option parser."""

    def test_none_and_empty_mean_all(self) -> None:
        """Assert None, empty, and 'all' all select every section."""
        assert parse_sections(None) is None
        assert parse_sections("") is None
        assert parse_sections("all") is None

    def test_parses_comma_separated_names(self) -> None:
        """Assert comma-separated names parse into a section set."""
        assert parse_sections("characters, background") == {"characters", "background"}
        assert parse_sections(["background"]) == {"background"}

    def test_rejects_unknown_sections(self) -> None:
        """Assert unknown section names raise ValueError."""
        with pytest.raises(ValueError, match="Unknown bible section"):
            parse_sections("bogus")


class TestSeriesBibleModel:
    """Test suite for the SeriesBible model."""

    def test_defaults_are_empty(self) -> None:
        """Assert a fresh bible is empty."""
        bible = SeriesBible()
        assert bible.characters == ""
        assert bible.background_settings == []
        assert bible.is_empty()

    def test_json_round_trip(self) -> None:
        """Assert a filled bible survives a JSON dump/validate round trip."""
        bible = SeriesBible(
            characters="Hero: brave protagonist.",
            background_settings=["Qi is the world's vital energy.", "The Azure Sect rules the north."],
        )
        assert not bible.is_empty()
        restored = SeriesBible.model_validate_json(bible.model_dump_json())
        assert restored == bible


class BibleRole(LLMTestRole, NovelCompose, BibleCompose):
    """Test role combining mock LLM with bible and novel composition."""


class TestCreateSettingBible:
    """Test suite for bible creation."""

    async def test_create_full_bible(self) -> None:
        """Assert both sections are proposed and assembled into the bible."""
        role = BibleRole(name="bible_role")
        roster = "Hero — protagonist, brave, wants to find his father.\nMentor — supporting, wise."
        background = [
            "Qi is the vital energy of the world.",
            "The Azure Sect rules the north.",
            "A lost sword awaits its master.",
        ]
        with install_router_usage(*return_mixed_router_usage(Value(roster, "generic"), Value(background, "json"))):
            bible = await role.create_setting_bible("The hero seeks his father.", language="English")

        assert bible is not None
        assert bible.characters == roster
        assert bible.background_settings == background

    async def test_create_characters_only(self) -> None:
        """Assert a section filter proposes only that section."""
        role = BibleRole(name="bible_role")
        roster = "Hero — brave protagonist."
        with install_router_usage(*return_mixed_router_usage(Value(roster, "generic"))):
            bible = await role.create_setting_bible(
                "The hero seeks his father.", language="English", sections="characters"
            )

        assert bible is not None
        assert bible.characters == roster
        assert bible.background_settings == []

    async def test_create_fails_when_characters_fail(self) -> None:
        """Assert creation aborts when the characters proposal is invalid."""
        role = BibleRole(name="bible_role")
        with install_router_usage("not a generic block"):
            bible = await role.create_setting_bible("The hero.", language="English")
        assert bible is None

    async def test_create_fails_when_background_fails(self) -> None:
        """Assert creation aborts when the background proposal is invalid."""
        role = BibleRole(name="bible_role")
        with install_router_usage(*return_mixed_router_usage(Value("Hero.", "generic"), Value("not-an-array", "json"))):
            bible = await role.create_setting_bible("The hero.", language="English")
        assert bible is None


class TestUpdateSettingBible:
    """Test suite for bible update."""

    async def test_update_replaces_requested_section_only(self) -> None:
        """Assert updating one section keeps the others intact."""
        role = BibleRole(name="bible_role")
        bible = SeriesBible(
            characters="Old roster.",
            background_settings=["Qi is vital.", "Old fact."],
        )
        with install_router_usage(*return_mixed_router_usage(Value("New roster.", "generic"))):
            updated = await role.update_setting_bible(bible, "The hero.", language="English", sections="characters")

        assert updated is not None
        assert updated.characters == "New roster."
        assert updated.background_settings == ["Qi is vital.", "Old fact."]

    async def test_update_all_sections(self) -> None:
        """Assert updating without a filter re-proposes every section."""
        role = BibleRole(name="bible_role")
        bible = SeriesBible(characters="Old roster.", background_settings=["Old fact."])
        with install_router_usage(
            *return_mixed_router_usage(Value("New roster.", "generic"), Value(["New fact."], "json"))
        ):
            updated = await role.update_setting_bible(bible, "The hero.", language="English")

        assert updated is not None
        assert updated.characters == "New roster."
        assert updated.background_settings == ["New fact."]


class TestBibleConsumption:
    """Test suite for bible context in scene prompts."""

    def _bible(self) -> SeriesBible:
        return SeriesBible(
            characters="Hero — brave protagonist, seeks his father.",
            background_settings=["Qi is the vital energy of the world.", "The Azure Sect rules the north."],
        )

    def test_render_bible_context_empty_bible_returns_empty(self) -> None:
        """Assert an empty bible renders no context block."""
        role = BibleRole(name="bible_role")
        ctx = SceneContext(title="S1", description="Leaving home.", expected_word_count=50)
        assert role.render_bible_context(ctx) == ""

    def test_render_bible_context_renders_both_sections(self) -> None:
        """Assert both bible sections render into the context block."""
        role = BibleRole(name="bible_role")
        ctx = SceneContext(title="S1", description="Leaving home.", expected_word_count=50)
        ctx.set_series_bible(self._bible())
        block = role.render_bible_context(ctx)
        assert block.startswith("## Setting Bible")
        assert "Hero — brave protagonist" in block
        assert "Qi is the vital energy" in block
        assert "The Azure Sect rules the north." in block

    async def test_prepare_scene_requirement_injects_bible_before_previous_content(self) -> None:
        """Assert the run-constant bible block leads the per-scene content."""
        role = BibleRole(name="bible_role")
        ctx = SceneContext(title="S2", description="A stranger appears.", expected_word_count=50)
        ctx.set_series_bible(self._bible())
        ctx.prefixed_content = "He walked into the dark."

        requirement = await role.prepare_scene_requirement(ctx)

        assert requirement.startswith("# Scene Writing")
        assert "## Setting Bible" in requirement
        # run-constant bible block sits in the shared prefix, before per-scene content
        assert requirement.index("## Setting Bible") < requirement.index("# Previous Content")
        assert requirement.index("He walked into the dark.") > requirement.index("# Previous Content")

    async def test_prepare_scene_requirement_without_bible_matches_base(self) -> None:
        """Assert an empty bible leaves the base requirement untouched."""
        role = BibleRole(name="bible_role")
        ctx = SceneContext(title="S1", description="Leaving home.", expected_word_count=50)
        requirement = await role.prepare_scene_requirement(ctx)
        assert "## Setting Bible" not in requirement
        assert requirement.startswith("# Scene Writing")


class TestBibleThreading:
    """Test suite for threading the bible through the composition chain."""

    async def test_compose_novel_threads_bible_to_all_contexts(self) -> None:
        """Assert the bible reaches chapter, story, and scene contexts."""
        role = BibleRole(name="bible_role")
        bible = SeriesBible(characters="Hero.", background_settings=["Qi is vital."])
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        ctx.set_series_bible(bible)
        meta = NovelPlan(
            title="The Search", description="A hero searching.", expected_word_count=40, series_bible=bible
        )
        chapter_plans_json = [{"title": "Ch1", "description": "The hero sets out.", "expected_word_count": 40}]
        story_plans_json = [{"title": "St1", "description": "The departure.", "expected_word_count": 40}]
        scene_plans_json = [{"title": "S1", "description": "Leaving home.", "expected_word_count": 40}]
        expected_scene = Scene(title="S1", description="Leaving home.", expected_word_count=40, content="He left.")
        with install_router_usage(
            *return_mixed_router_usage(
                Value(meta, "model"),
                Value(chapter_plans_json, "json"),
                Value(story_plans_json, "json"),
                Value(scene_plans_json, "json"),
                Value(expected_scene, "model"),
            )
        ):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        assert novel.series_bible == bible
        assert ctx.chapter_context[0].series_bible == bible
        assert ctx.chapter_context[0].story_context[0].series_bible == bible
        assert ctx.chapter_context[0].story_context[0].scene_context[0].series_bible == bible

    async def test_compose_novel_keeps_preset_bible_when_plan_is_empty(self) -> None:
        """Assert a pre-set bible survives generation when the plan proposes an empty one."""
        role = BibleRole(name="bible_role")
        bible = SeriesBible(characters="Hero.", background_settings=["Qi is vital."])
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        ctx.set_series_bible(bible)
        meta = NovelPlan(
            title="The Search", description="A hero searching.", expected_word_count=40, series_bible=SeriesBible()
        )
        chapter_plans_json = [{"title": "Ch1", "description": "The hero sets out.", "expected_word_count": 40}]
        story_plans_json = [{"title": "St1", "description": "The departure.", "expected_word_count": 40}]
        scene_plans_json = [{"title": "S1", "description": "Leaving home.", "expected_word_count": 40}]
        expected_scene = Scene(title="S1", description="Leaving home.", expected_word_count=40, content="He left.")
        with install_router_usage(
            *return_mixed_router_usage(
                Value(meta, "model"),
                Value(chapter_plans_json, "json"),
                Value(story_plans_json, "json"),
                Value(scene_plans_json, "json"),
                Value(expected_scene, "model"),
            )
        ):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        assert novel.series_bible is bible
        assert ctx.chapter_context[0].series_bible is bible
        assert ctx.chapter_context[0].story_context[0].scene_context[0].series_bible is bible

    async def test_compose_novel_rethreads_bible_to_prefilled_contexts(self) -> None:
        """Assert prefilled contexts adopt the novel's bible even when they carried a stale one."""
        role = BibleRole(name="bible_role")
        bible = SeriesBible(characters="Hero.", background_settings=["Qi is vital."])
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        ctx.set_series_bible(bible)
        # prefilled tree: child contexts keep their default (empty) bible instances
        scene_ctx = SceneContext(title="S1", description="Leaving home.", expected_word_count=40)
        story_ctx = StoryContext(title="St1", description="The departure.")
        story_ctx.add_scene_context(scene_ctx)
        chapter_ctx = ChapterContext(title="Ch1", description="The hero sets out.")
        chapter_ctx.add_story_context(story_ctx)
        ctx.add_chapter_context(chapter_ctx)

        meta = NovelPlan(
            title="The Search", description="A hero searching.", expected_word_count=40, series_bible=SeriesBible()
        )
        expected_scene = Scene(title="S1", description="Leaving home.", expected_word_count=40, content="He left.")
        with install_router_usage(*return_model_json_router_usage(meta, expected_scene)):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        assert ctx.chapter_context[0].series_bible is bible
        assert ctx.chapter_context[0].story_context[0].series_bible is bible
        assert ctx.chapter_context[0].story_context[0].scene_context[0].series_bible is bible
        assert novel.series_bible is bible
