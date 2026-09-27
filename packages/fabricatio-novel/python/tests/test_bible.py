"""Test module for the setting bible: models, composition, and consumption."""

from _support import unguarded_role
from fabricatio_mock import MockScript, Value
from fabricatio_novel.capabilities.bible import BibleCompose
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.plan import NovelPlan
from fabricatio_novel.models.series_book import SeriesBible


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


class TestBibleSeeding:
    """Test suite for seeding the bible into the novel's running prefix."""

    def test_seed_bible_prefix_seeds_rendered_block_once(self) -> None:
        """Assert seeding appends one rendered setting-bible entry and is idempotent."""
        novel = NovelContext.create("The hero..", language="English")
        novel.set_series_bible(SeriesBible(characters=["Hero — brave protagonist."]))

        novel.seed_bible_prefix()
        novel.seed_bible_prefix()

        entries = [entry for entry in novel.prefix_log.entries if entry.kind.is_setting_bible()]
        assert len(entries) == 1
        assert entries[0].body.startswith("## Setting Bible")
        assert "Hero — brave protagonist." in entries[0].body

    def test_seed_bible_prefix_skips_empty_and_missing_bibles(self) -> None:
        """Assert an uninitialized or empty bible seeds nothing."""
        novel = NovelContext.create("The hero..", language="English")
        novel.seed_bible_prefix()
        assert novel.prefix_log.entries == ()
        novel.set_series_bible(SeriesBible())
        novel.seed_bible_prefix()
        assert novel.prefix_log.entries == ()


class TestComposeSettingBible:
    """Test suite for bible composition."""

    async def test_compose_full_bible(self) -> None:
        """Assert both sections are proposed and assembled into the bible."""
        role = unguarded_role(BibleCompose, name="bible_role")
        roster = ["Hero — protagonist, brave, wants to find his father.", "Mentor — supporting, wise."]
        background = [
            "Qi is the vital energy of the world.",
            "The Azure Sect rules the north.",
            "A lost sword awaits its master.",
        ]
        with MockScript.from_values(
            Value.from_json(roster, name="bible characters"),
            Value.from_json(background, name="bible background"),
        ):
            bible = await role.compose_setting_bible("The hero seeks his father.", language="English")

        assert bible is not None
        assert bible.characters == roster
        assert bible.background_settings == background

    async def test_compose_fails_when_characters_fail(self) -> None:
        """Assert creation aborts when the characters proposal is invalid."""
        role = unguarded_role(BibleCompose, name="bible_role")
        with MockScript.from_values(Value.from_text("not a generic block", name="invalid characters response")):
            bible = await role.compose_setting_bible("The hero.", language="English")
        assert bible is None

    async def test_compose_fails_when_background_fails(self) -> None:
        """Assert creation aborts when the background proposal is invalid."""
        role = unguarded_role(BibleCompose, name="bible_role")
        with MockScript.from_values(
            Value.from_json(["Hero."], name="bible characters"),
            Value.from_json("not-an-array", name="invalid background response"),
        ):
            bible = await role.compose_setting_bible("The hero.", language="English")
        assert bible is None


class TestBibleConsumption:
    """Test suite for the seeded bible reaching scene prompts through the prefix log."""

    def _bible(self) -> SeriesBible:
        return SeriesBible(
            characters=["Hero — brave protagonist, seeks his father."],
            background_settings=["Qi is the vital energy of the world.", "The Azure Sect rules the north."],
        )

    def _scene_with_seeded_prefix(self) -> SceneContext:
        novel = NovelContext.create("The hero seeks his father..", language="English")
        novel.set_series_bible(self._bible())
        novel.seed_bible_prefix()
        chapter = ChapterContext(title="Ch1", description="The start.")
        novel.add_context(chapter)
        list(novel.iter_prefixed_contexts())
        story = StoryContext(title="St1", description="The departure.")
        chapter.add_context(story)
        list(chapter.iter_prefixed_contexts())
        scene = SceneContext(title="S1", description="Leaving home.", expected_word_count=50)
        story.add_context(scene)
        scene.set_prefix_log(story.prefix_log)
        return scene

    def test_seeded_bible_reaches_scene_prefix_log(self) -> None:
        """Assert the seeded entry rides every composition walk into the scene's prefix."""
        scene = self._scene_with_seeded_prefix()
        kinds = [entry.kind for entry in scene.prefix_log.entries]
        assert kinds[0].is_setting_bible()
        assert "Hero — brave protagonist" in scene.prefix_log.render()

    async def test_seeded_bible_renders_inside_novel_so_far(self) -> None:
        """Assert the bible renders within the leading novel-so-far block, not a dedicated section."""
        role = unguarded_role(BibleCompose, name="bible_role")
        scene = self._scene_with_seeded_prefix()
        requirement = await role.prepare_scene_requirement(scene)
        assert requirement.startswith("--- Start of Novel so far ---")
        assert requirement.index("## Setting Bible") < requirement.index("--- End of Novel so far ---")
        assert requirement.index("Hero — brave protagonist") < requirement.index("--- End of Novel so far ---")
        assert requirement.index("# Scene Writing") > requirement.index("--- End of Novel so far ---")
        assert requirement.index("## Setting Bible") < requirement.index("## Scene")

    async def test_unseeded_scene_omits_the_bible(self) -> None:
        """Assert a scene without a seeded prefix renders no bible block."""
        role = unguarded_role(BibleCompose, name="bible_role")
        scene = SceneContext(title="S1", description="Leaving home.", expected_word_count=50)
        requirement = await role.prepare_scene_requirement(scene)
        assert "## Setting Bible" not in requirement
        assert requirement.startswith("--- Start of Novel so far ---")
        assert "# Scene Writing" in requirement


class TestBibleThreading:
    """Test suite for threading the bible through the composition chain."""

    async def test_compose_novel_seeds_bible_into_every_scene_prefix(self) -> None:
        """Assert a composed run leaves the seeded bible entry in every scene's prefix log."""
        role = unguarded_role(BibleCompose, name="bible_role")
        bible = SeriesBible(background_settings=["Qi is vital."])
        ctx = NovelContext.create("The hero seeks his father..", language="English")
        ctx.set_series_bible(bible)
        meta = NovelPlan(
            title="The Search",
            description="A hero searching.",
            expected_word_count=40,
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
            Value.from_generic("He left.", name="scene prose"),
        ):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        assert novel.series_bible == bible
        scene = ctx.child_contexts[0].child_contexts[0].child_contexts[0]
        kinds = [entry.kind for entry in scene.prefix_log.entries]
        assert any(kind.is_setting_bible() for kind in kinds)
        assert "Qi is vital." in scene.prefix_log.render()

    async def test_compose_novel_keeps_preset_bible(self) -> None:
        """Assert a pre-set bible survives generation; plans never carry one."""
        role = unguarded_role(BibleCompose, name="bible_role")
        bible = SeriesBible(background_settings=["Qi is vital."])
        ctx = NovelContext.create("The hero seeks his father..", language="English")
        ctx.set_series_bible(bible)
        meta = NovelPlan(
            title="The Search",
            description="A hero searching.",
            expected_word_count=40,
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
            Value.from_generic("He left.", name="scene prose"),
        ):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        assert novel.series_bible is bible
        scene = ctx.child_contexts[0].child_contexts[0].child_contexts[0]
        assert "Qi is vital." in scene.prefix_log.render()

    async def test_compose_novel_seeds_prefilled_tree_exactly_once(self) -> None:
        """Assert repeated composition walks over a prefilled tree never duplicate the seed."""
        role = unguarded_role(BibleCompose, name="bible_role")
        bible = SeriesBible(background_settings=["Qi is vital."])
        ctx = NovelContext.create("The hero seeks his father..", language="English")
        ctx.set_series_bible(bible)
        scene_ctx = SceneContext(title="S1", description="Leaving home.", expected_word_count=40)
        story_ctx = StoryContext(title="St1", description="The departure.")
        story_ctx.add_context(scene_ctx)
        chapter_ctx = ChapterContext(title="Ch1", description="The hero sets out.")
        chapter_ctx.add_context(story_ctx)
        ctx.add_context(chapter_ctx)

        meta = NovelPlan(
            title="The Search",
            description="A hero searching.",
            expected_word_count=40,
            writing_styles=[],
            writing_constraints=[],
        )
        with MockScript.from_values(
            Value.from_model(meta, name="novel metadata"),
            Value.from_generic("He left.", name="scene prose"),
        ):
            novel = await role.compose_novel(ctx)

        assert novel is not None
        kinds = [entry.kind for entry in scene_ctx.prefix_log.entries]
        assert sum(kind.is_setting_bible() for kind in kinds) == 1
        assert novel.series_bible is bible
