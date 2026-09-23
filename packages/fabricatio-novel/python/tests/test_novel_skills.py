"""Built-in skill tests for fabricatio-novel: the user's skills on the context, in the prompts."""

from pathlib import Path

import pytest
from _support import card
from fabricatio_character.models.character import CharacterCardBoundaries, CharacterSpan
from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_mock import make_test_role
from fabricatio_novel.actions.novel import InitNovelContext
from fabricatio_novel.capabilities.bible import BibleCompose
from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.capabilities.rag import RAGChapterCompose, RAGNovelCompose
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.context.base import CharacterSpans
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.context.rag import RagRetrieval, RagStoryContext
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.plan import ChapterPlan, ScenePlan, StoryPlan
from fabricatio_novel.models.rag import WritingStyleDocument
from fabricatio_novel.models.series_book import SeriesBible
from fabricatio_skill.rust import SkillRegistry

OUTLINE = "The hero leaves home and returns changed."
SKILL_BODY = "Keep every paragraph under forty words, and never explain the weather."


def _write_skill(root: Path, name: str, body: str) -> Path:
    """Write one markdown skill into its own directory under ``root``."""
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        f"---\nname: {name}\ndescription: {name} house style\ntags: [writing]\n---\n\n{body}\n",
        encoding="utf-8",
    )
    return skill_file


def _install_skills(root: Path) -> None:
    """Load the skills written under ``root`` into the process-wide library, beside the roots it loads on its own."""
    SkillRegistry().load_scanned([str(root)])


class TestSkillInit:
    """Test suite for resolving the user's skills onto the run's root."""

    async def test_init_stage_binds_skills_by_name(self, tmp_path: Path) -> None:
        """Assert the init stage binds the resolved names and renders their bodies as tags named after them."""
        name = "novel-lead-prefix"
        _write_skill(tmp_path, name, SKILL_BODY)
        _install_skills(tmp_path)
        bible_path = tmp_path / "bible.json"
        bible_path.write_text(
            SeriesBible(characters=["Hero"], background_settings=["A cold coast."]).model_dump_json(),
            encoding="utf-8",
        )

        ctx = await InitNovelContext().init_novel_context(OUTLINE, skills=[name], bible_path=bible_path)

        assert ctx.skill_names == [name]
        assert ctx.skill_references() == [f"<{name}>{SKILL_BODY}</{name}>"]
        assert ctx.skill_section().startswith("--- Start of Novel Skills ---")

    async def test_unknown_skill_is_skipped_not_fatal(self, tmp_path: Path) -> None:
        """Assert a name that resolves nowhere is left out while the run goes on with the rest."""
        _write_skill(tmp_path, "style", SKILL_BODY)
        _install_skills(tmp_path)

        ctx = await InitNovelContext().init_novel_context(OUTLINE, skills=["style", "no-such-skill"])

        assert ctx.skill_names == ["style"]
        assert ctx.skill_references() == [f"<style>{SKILL_BODY}</style>"]

    async def test_vanished_skill_drops_out_without_crashing_the_walk(self) -> None:
        """Assert a name that no longer resolves in a rebuilt tree renders nothing instead of raising."""
        ctx = NovelContext.create(OUTLINE, language="English").with_skills(["gone"])

        assert ctx.skill_references() == []
        assert ctx.skill_section() == ""

    async def test_assignment_order_does_not_change_the_rendered_section(self, tmp_path: Path) -> None:
        """Assert the same selection in either order renders one byte-identical section, so prefix cache holds."""
        _write_skill(tmp_path, "alpha-style", SKILL_BODY)
        _write_skill(tmp_path, "zeta-style", "Open every chapter on a turn of weather.")
        _install_skills(tmp_path)

        forward = await InitNovelContext().init_novel_context(OUTLINE, skills=["alpha-style", "zeta-style"])
        reverse = await InitNovelContext().init_novel_context(OUTLINE, skills=["zeta-style", "alpha-style"])

        section = forward.skill_section()
        assert section == reverse.skill_section()
        assert section.index(SKILL_BODY) < section.index("Open every chapter on a turn of weather.")

    async def test_skills_travel_down_the_creation_chains(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert the chapters, stories and scenes planned under the root carry the run's skill selection."""
        role = make_test_role(NovelCompose, name="skill_chain_role")
        novel = NovelContext.create(OUTLINE, language="English").with_skills(["style"])
        chapter_plan = ChapterPlan(
            title="Ch1",
            description="The hero leaves.",
            weight=1.0,
            writing_styles=[],
            writing_constraints=[],
        )
        story_plan = StoryPlan(
            title="St1",
            description="The departure.",
            weight=1.0,
            writing_styles=[],
            writing_constraints=[],
        )
        scene_plan = ScenePlan(
            title="Sc1",
            description="The hero packs.",
            weight=1.0,
            writing_styles=[],
            writing_constraints=[],
        )

        async def fake_chapters(ctx: NovelContext, *_: object, **__: object) -> list[ChapterPlan]:
            return [chapter_plan]

        async def fake_stories(ctx: ChapterContext, *_: object, **__: object) -> list[StoryPlan]:
            return [story_plan]

        async def fake_scenes(ctx: StoryContext, *_: object, **__: object) -> list[ScenePlan]:
            return [scene_plan]

        monkeypatch.setattr(type(role), "plan_chapters", staticmethod(fake_chapters))
        monkeypatch.setattr(type(role), "plan_stories", staticmethod(fake_stories))
        monkeypatch.setattr(type(role), "plan_scenes", staticmethod(fake_scenes))

        assert await role.plan_chapters_phase(novel) is True
        chapter = novel.child_contexts[0]
        assert await role.plan_stories_phase(chapter) is True
        story = chapter.child_contexts[0]
        assert await role.plan_scenes_phase(story) is True
        scene = story.child_contexts[0]

        for planned in (chapter, story, scene):
            assert planned.skill_names == ["style"]


class TestSkillPrompts:
    """Test suite for the skills in the planning and scene-write prompts."""

    async def test_content_prompts_lead_with_the_skills(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Assert the skills head every content prompt: metadata, bible, roster spans, plans and boundary cards."""
        role = make_test_role(NovelCompose, BibleCompose, name="skill_plan_role")
        _write_skill(tmp_path, "style", SKILL_BODY)
        _install_skills(tmp_path)
        role.fetch_skills(["style"])
        novel = NovelContext.create(OUTLINE, language="English").with_skills(["style"])
        novel.set_series_bible(SeriesBible(characters=["Hero"], background_settings=["A cold river."]))
        chapter = ChapterContext.create(OUTLINE, language="English").with_skills(["style"])
        story = StoryContext.create(OUTLINE, language="English").with_skills(["style"])
        captured: list[str] = []

        async def fake_propose(model: object, requirement: str, *args: object, **kwargs: object) -> object:
            captured.append(requirement)
            if model is CharacterSpans:
                return CharacterSpans(root=[])
            if model is CharacterCardBoundaries:
                return CharacterCardBoundaries(root=[])
            return None

        async def fake_list_v(requirement: str, *args: object, **kwargs: object) -> list[str]:
            captured.append(requirement)
            return ["Hero"]

        monkeypatch.setattr(type(role), "propose", staticmethod(fake_propose))
        monkeypatch.setattr(type(role), "alist_v", staticmethod(fake_list_v))

        await role.plan_chapters(novel)
        await role.plan_stories(chapter)
        await role.plan_scenes(story)
        await role.propose_novel_metadata(novel)
        await role.prepare_character_span(novel)
        await role.compose_setting_bible(OUTLINE, "English", novel.skill_section())
        chapter.add_context(StoryContext.create(OUTLINE, language="English", title="Story One", description="Go."))
        chapter.add_context(StoryContext.create(OUTLINE, language="English", title="Story Two", description="Back."))
        chapter.set_charactor_spans([CharacterSpan(start=card(), end=card())])
        await role.draft_story_spans(chapter)
        novel.add_context(ChapterContext.create(OUTLINE, language="English", title="Chapter One", description="Go."))
        novel.add_context(ChapterContext.create(OUTLINE, language="English", title="Chapter Two", description="Back."))
        novel.set_charactor_spans([CharacterSpan(start=card(), end=card())])
        await role.draft_chapter_spans(novel)

        assert len(captured) == 9
        section = novel.skill_section()
        for prompt in captured:
            assert prompt.startswith(section)
            assert SKILL_BODY in prompt
        with_outline = [prompt for prompt in captured if "--- Start of Novel Outline ---" in prompt]
        assert len(with_outline) == 7
        for prompt in with_outline:
            assert prompt.index(SKILL_BODY) < prompt.index("--- Start of Novel Outline ---")

    async def test_plain_run_renders_no_skills_section(self) -> None:
        """Assert a run without skills renders the plan prompt exactly as the template's outline block."""
        requirement = TEMPLATE_MANAGER.render_template(
            novel_config.plan_requirement_template,
            {
                "outline": OUTLINE,
                "planning_title": "Chapter Planning",
                "goal": "Plan the chapters of the novel from its `Novel Outline`",
                "parent_title": "Novel",
                "title": "",
                "description": "",
                "expected_word_count": 0,
                "writing_styles": [],
                "writing_constraints": [],
                "skills": "",
                "language": "English",
                "characters": [],
            },
        )

        assert "--- Start of Novel Skills ---" not in requirement
        assert requirement.startswith("--- Start of Novel Outline ---")

    async def test_scene_write_prompt_leads_with_the_skills(self, tmp_path: Path) -> None:
        """Assert the skills head the scene write prompt, ahead of the manuscript block."""
        role = make_test_role(NovelCompose, name="skill_scene_role")
        _write_skill(tmp_path, "style", SKILL_BODY)
        _install_skills(tmp_path)
        role.fetch_skills(["style"])
        novel = NovelContext.create(OUTLINE, language="English").with_skills(["style"])
        chapter = ChapterContext.create(OUTLINE, language="English").with_skills_from(novel)
        story = StoryContext.create(OUTLINE, language="English").with_skills_from(chapter)
        story.add_context(
            SceneContext(title="Sc1", description="The hero packs.", expected_word_count=50)
            .with_skills_from(story)
            .set_content("The hero folded the map and left.")
        )
        second = SceneContext(title="Sc2", description="The road.", expected_word_count=50).with_skills_from(story)
        story.add_context(second)
        chapter.add_context(story)
        novel.add_context(chapter)

        [seeded_chapter] = list(novel.iter_prefixed_contexts())
        [seeded_story] = list(seeded_chapter.iter_prefixed_contexts())
        list(seeded_story.iter_prefixed_contexts())

        requirement = await role.prepare_scene_requirement(second)

        assert [entry.kind for entry in second.prefix_log.entries] == ["chapter_header", "scene_content"]
        assert requirement.startswith(novel.skill_section())
        assert requirement.index(SKILL_BODY) < requirement.index("The hero folded the map and left.")

    async def test_story_retrieval_refinement_leads_with_the_same_section(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Assert a skill-bearing story's retrieval opens with the very bytes its prompts render."""
        role = make_test_role(NovelCompose, RAGChapterCompose, name="skill_refine_story_role")
        _write_skill(tmp_path, "style", SKILL_BODY)
        _install_skills(tmp_path)
        sealed = RagStoryContext.seal(
            StoryContext.create(OUTLINE, language="English", description=OUTLINE).with_skills(["style"]),
            RagRetrieval(),
        )
        plain = RagStoryContext.seal(
            StoryContext.create(OUTLINE, language="English", description=OUTLINE), RagRetrieval()
        )
        section = sealed.skill_section()
        assert section.startswith("--- Start of Novel Skills ---")
        captured: list[str] = []

        async def fake_list_v(requirement: str, *args: object, **kwargs: object) -> list[str]:
            captured.append(requirement)
            return ["head one", "head two"]

        async def fake_fetch(query: object, config: object | None = None) -> list[WritingStyleDocument]:
            return []

        monkeypatch.setattr(type(role), "alist_v", staticmethod(fake_list_v))
        monkeypatch.setattr(type(role), "afetch_document", staticmethod(fake_fetch))

        await role.prepare_story(sealed)
        await role.prepare_story(plain)

        assert captured[0].startswith(f"{section}\n\n")
        assert SKILL_BODY in captured[0]
        assert captured[1].startswith(OUTLINE)
        assert "--- Start of Novel Skills ---" not in captured[1]

    async def test_novel_retrieval_refinement_leads_with_the_same_section(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Assert the novel-level retrieval opens with the very bytes the plan prompts render."""
        role = make_test_role(RAGNovelCompose, name="skill_refine_novel_role")
        _write_skill(tmp_path, "style", SKILL_BODY)
        _install_skills(tmp_path)
        novel = NovelContext.create(OUTLINE, language="English").with_skills(["style"])
        section = novel.skill_section()
        assert section.startswith("--- Start of Novel Skills ---")
        captured: list[str] = []

        async def fake_list_v(requirement: str, *args: object, **kwargs: object) -> list[str]:
            captured.append(requirement)
            return ["head one", "head two"]

        async def fake_fetch(query: object, config: object | None = None) -> list[WritingStyleDocument]:
            return []

        monkeypatch.setattr(type(role), "alist_v", staticmethod(fake_list_v))
        monkeypatch.setattr(type(role), "afetch_document", staticmethod(fake_fetch))

        await role.retrieve_novel_styles(novel)

        assert captured[0].startswith(f"{section}\n\n")
        assert SKILL_BODY in captured[0]
