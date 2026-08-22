"""Test module for the setting bible: models, creation, update, and consumption."""

import pytest
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import Value, return_mixed_router_usage
from fabricatio_mock.utils import install_router_usage
from fabricatio_novel.capabilities.bible import BibleCompose, parse_sections
from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.plan import NovelPlan
from fabricatio_novel.models.series_book import SeriesBible


def raw_value(text: str) -> Value[str]:
    """Wrap a plain scene response for mixed router usage."""
    return Value(text, "raw", convertor=lambda s: s)


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
        assert bible.characters == []
        assert bible.background_settings == []
        assert bible.is_empty()

    def test_json_round_trip(self) -> None:
        """Assert a filled bible survives a JSON dump/validate round trip."""
        bible = SeriesBible(
            characters=["Hero: brave protagonist."],
            background_settings=["Qi is the world's vital energy.", "The Azure Sect rules the north."],
        )
        assert not bible.is_empty()
        restored = SeriesBible.model_validate_json(bible.model_dump_json())
        assert restored == bible

    def test_as_prompt_renders_both_sections(self) -> None:
        """Assert as_prompt renders the roster and every background fact."""
        bible = SeriesBible(
            characters=["Hero: brave protagonist."],
            background_settings=["Qi is the world's vital energy.", "The Azure Sect rules the north."],
        )
        prompt = bible.as_prompt()
        assert prompt.startswith("## Setting Bible")
        assert "Hero: brave protagonist." in prompt
        assert "Qi is the world's vital energy." in prompt
        assert "The Azure Sect rules the north." in prompt

    def test_legacy_string_characters_coerce_to_lines(self) -> None:
        """Assert pre-list bibles load by splitting a bare string roster into non-blank lines."""
        legacy = '{"characters": "Hero.\\n\\n  Mentor.  \\n", "background_settings": []}'
        bible = SeriesBible.model_validate_json(legacy)
        assert bible.characters == ["Hero.", "Mentor."]


class TestBibleSeeding:
    """Test suite for seeding the bible into the novel's running prefix."""

    def test_seed_bible_prefix_seeds_rendered_block_once(self) -> None:
        """Assert seeding appends one rendered setting-bible entry and is idempotent."""
        novel = NovelContext.create("The hero.", language="English")
        novel.set_series_bible(SeriesBible(characters=["Hero — brave protagonist."]))

        novel.seed_bible_prefix()
        novel.seed_bible_prefix()

        entries = [entry for entry in novel.prefix_log.entries if entry.kind == "setting_bible"]
        assert len(entries) == 1
        assert entries[0].body.startswith("## Setting Bible")
        assert "Hero — brave protagonist." in entries[0].body

    def test_seed_bible_prefix_skips_empty_and_missing_bibles(self) -> None:
        """Assert an uninitialized or empty bible seeds nothing."""
        novel = NovelContext.create("The hero.", language="English")
        novel.seed_bible_prefix()
        assert novel.prefix_log.entries == ()
        novel.set_series_bible(SeriesBible())
        novel.seed_bible_prefix()
        assert novel.prefix_log.entries == ()


class BibleRole(LLMTestRole, NovelCompose, BibleCompose):
    """Test role combining mock LLM with bible and novel composition."""


class TestCreateSettingBible:
    """Test suite for bible creation."""

    async def test_create_full_bible(self) -> None:
        """Assert both sections are proposed and assembled into the bible."""
        role = BibleRole(name="bible_role")
        roster = ["Hero — protagonist, brave, wants to find his father.", "Mentor — supporting, wise."]
        background = [
            "Qi is the vital energy of the world.",
            "The Azure Sect rules the north.",
            "A lost sword awaits its master.",
        ]
        with install_router_usage(*return_mixed_router_usage(Value(roster, "json"), Value(background, "json"))):
            bible = await role.create_setting_bible("The hero seeks his father.", language="English")

        assert bible is not None
        assert bible.characters == roster
        assert bible.background_settings == background

    async def test_create_characters_only(self) -> None:
        """Assert a section filter proposes only that section."""
        role = BibleRole(name="bible_role")
        roster = ["Hero — brave protagonist."]
        with install_router_usage(*return_mixed_router_usage(Value(roster, "json"))):
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
        with install_router_usage(*return_mixed_router_usage(Value(["Hero."], "json"), Value("not-an-array", "json"))):
            bible = await role.create_setting_bible("The hero.", language="English")
        assert bible is None


class TestUpdateSettingBible:
    """Test suite for bible update."""

    async def test_update_replaces_requested_section_only(self) -> None:
        """Assert updating one section keeps the others intact."""
        role = BibleRole(name="bible_role")
        bible = SeriesBible(
            characters=["Old roster."],
            background_settings=["Qi is vital.", "Old fact."],
        )
        with install_router_usage(*return_mixed_router_usage(Value(["New roster."], "json"))):
            updated = await role.update_setting_bible(bible, "The hero.", language="English", sections="characters")

        assert updated is not None
        assert updated.characters == ["New roster."]
        assert updated.background_settings == ["Qi is vital.", "Old fact."]

    async def test_update_all_sections(self) -> None:
        """Assert updating without a filter re-proposes every section."""
        role = BibleRole(name="bible_role")
        bible = SeriesBible(characters=["Old roster."], background_settings=["Old fact."])
        with install_router_usage(
            *return_mixed_router_usage(Value(["New roster."], "json"), Value(["New fact."], "json"))
        ):
            updated = await role.update_setting_bible(bible, "The hero.", language="English")

        assert updated is not None
        assert updated.characters == ["New roster."]
        assert updated.background_settings == ["New fact."]


class TestBibleConsumption:
    """Test suite for the seeded bible reaching scene prompts through the prefix log."""

    def _bible(self) -> SeriesBible:
        return SeriesBible(
            characters=["Hero — brave protagonist, seeks his father."],
            background_settings=["Qi is the vital energy of the world.", "The Azure Sect rules the north."],
        )

    def _scene_with_seeded_prefix(self) -> SceneContext:
        novel = NovelContext.create("The hero seeks his father.", language="English")
        novel.set_series_bible(self._bible())
        novel.seed_bible_prefix()
        chapter = ChapterContext(title="Ch1", description="The start.")
        novel.add_chapter_context(chapter)
        list(novel.iter_prefixed_contexts())
        story = StoryContext(title="St1", description="The departure.")
        chapter.add_story_context(story)
        list(chapter.iter_prefixed_contexts())
        scene = SceneContext(title="S1", description="Leaving home.", expected_word_count=50)
        story.add_scene_context(scene)
        scene.set_prefix_log(story.prefix_log)
        return scene

    def test_seeded_bible_reaches_scene_prefix_log(self) -> None:
        """Assert the seeded entry rides every composition walk into the scene's prefix."""
        scene = self._scene_with_seeded_prefix()
        kinds = [entry.kind for entry in scene.prefix_log.entries]
        assert kinds[0] == "setting_bible"
        assert "Hero — brave protagonist" in scene.prefix_log.render()

    async def test_seeded_bible_renders_inside_previous_content(self) -> None:
        """Assert the bible renders within the previous-content block, not a dedicated section."""
        role = BibleRole(name="bible_role")
        scene = self._scene_with_seeded_prefix()
        requirement = await role.prepare_scene_requirement(scene)
        assert requirement.startswith("# Scene Writing")
        assert "## Setting Bible" in requirement
        assert requirement.index("## Setting Bible") > requirement.index("# Previous Content")
        assert requirement.index("Hero — brave protagonist") > requirement.index("# Previous Content")
        assert requirement.index("## Setting Bible") < requirement.index("## Scene")

    async def test_unseeded_scene_omits_the_bible(self) -> None:
        """Assert a scene without a seeded prefix renders no bible block."""
        role = BibleRole(name="bible_role")
        scene = SceneContext(title="S1", description="Leaving home.", expected_word_count=50)
        requirement = await role.prepare_scene_requirement(scene)
        assert "## Setting Bible" not in requirement
        assert requirement.startswith("# Scene Writing")


class TestBibleThreading:
    """Test suite for threading the bible through the composition chain."""

    async def test_compose_novel_seeds_bible_into_every_scene_prefix(self) -> None:
        """Assert a composed run leaves the seeded bible entry in every scene's prefix log."""
        role = BibleRole(name="bible_role")
        bible = SeriesBible(background_settings=["Qi is vital."])
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        ctx.set_series_bible(bible)
        meta = NovelPlan(
            title="The Search", description="A hero searching.", expected_word_count=40, series_bible=bible
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
            novel = await role.compose_novel(ctx)

        assert novel is not None
        assert novel.series_bible == bible
        scene = ctx.chapter_context[0].story_context[0].scene_context[0]
        kinds = [entry.kind for entry in scene.prefix_log.entries]
        assert "setting_bible" in kinds
        assert "Qi is vital." in scene.prefix_log.render()

    async def test_compose_novel_keeps_preset_bible_when_plan_is_empty(self) -> None:
        """Assert a pre-set bible survives generation when the plan proposes an empty one."""
        role = BibleRole(name="bible_role")
        bible = SeriesBible(background_settings=["Qi is vital."])
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        ctx.set_series_bible(bible)
        meta = NovelPlan(
            title="The Search", description="A hero searching.", expected_word_count=40, series_bible=SeriesBible()
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
            novel = await role.compose_novel(ctx)

        assert novel is not None
        assert novel.series_bible is bible
        scene = ctx.chapter_context[0].story_context[0].scene_context[0]
        assert "Qi is vital." in scene.prefix_log.render()

    async def test_compose_novel_seeds_prefilled_tree_exactly_once(self) -> None:
        """Assert repeated composition walks over a prefilled tree never duplicate the seed."""
        role = BibleRole(name="bible_role")
        bible = SeriesBible(background_settings=["Qi is vital."])
        ctx = NovelContext.create("The hero seeks his father.", language="English")
        ctx.set_series_bible(bible)
        scene_ctx = SceneContext(title="S1", description="Leaving home.", expected_word_count=40)
        story_ctx = StoryContext(title="St1", description="The departure.")
        story_ctx.add_scene_context(scene_ctx)
        chapter_ctx = ChapterContext(title="Ch1", description="The hero sets out.")
        chapter_ctx.add_story_context(story_ctx)
        ctx.add_chapter_context(chapter_ctx)

        meta = NovelPlan(
            title="The Search", description="A hero searching.", expected_word_count=40, series_bible=SeriesBible()
        )
        with install_router_usage(
            *return_mixed_router_usage(
                Value(meta, "model"),
                raw_value("He left."),
            )
        ):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        kinds = [entry.kind for entry in scene_ctx.prefix_log.entries]
        assert kinds.count("setting_bible") == 1
        assert novel.series_bible is bible
