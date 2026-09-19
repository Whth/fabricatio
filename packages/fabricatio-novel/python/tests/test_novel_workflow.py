"""Staged-workflow tests for fabricatio-novel: DebugNovelWorkflow end to end."""

from pathlib import Path
from uuid import uuid4

import pytest
from _support import card
from fabricatio_character.models.character import CharacterSpan
from fabricatio_core.rust import CONFIG, TASK
from fabricatio_mock import DUMMY_LLM_GROUP, MockScript, Value
from fabricatio_novel.models.novel import ExportFormat
from fabricatio_novel.models.plan import NovelPlan

# Workflow tests subscribe a plain ``Role`` (no scoped ``llm_send_to``), so the real
# resolver runs: route the ``task`` agent variant to the dummy router group so explicit
# ``send_to=TASK`` in the staged actions resolves to what the ``MockScript`` seeds.
CONFIG.configure_llm_variant(TASK, DUMMY_LLM_GROUP)


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
            # Unique per run: every planning prompt embeds the outline and the span
            # prompt embeds the meta description, so a stale persistent-cache entry
            # can never serve a call and the dummy stack pops in seeded order.
            novel_outline=f"The hero seeks his father across the winter mountains, wf v3 salt. [run:{uuid4().hex[:8]}]",
            novel_language="English",
            persist_dir=persist_dir,
        )
        meta = NovelPlan(
            title="The Search",
            description=f"A hero searching for his father. [run:{uuid4().hex[:8]}]",
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
            Value.from_json(["Hero — brave protagonist, seeking his father."], name="bible roster"),
            Value.from_json(["A quiet riverside town in late summer."], name="bible background"),
            Value.from_json([CharacterSpan(start=card(), end=card()).model_dump()], name="character spans"),
            Value.from_json(chapter_plans_json, name="chapter plans"),
            Value.from_json(story_plans_json, name="story plans"),
            Value.from_json(scene_plans_json, name="scene plans"),
            Value.from_generic("He left.", name="scene prose"),
        ):
            epub = await task.delegate(namespace)

        assert epub == persist_dir / "novel.epub"
        assert epub.is_file()
        assert any(persist_dir.glob("Novel_*.json"))
        assert sorted(p.name for p in persist_dir.iterdir() if p.is_dir()) == [
            "stage_01_init",
            "stage_02_metadata",
            "stage_03_bible",
            "stage_04_characters",
            "stage_05_chapter_plans",
            "stage_06_story_plans",
            "stage_07_scene_plans",
            "stage_08_scenes",
            "stage_09_novel",
        ]
        for stage_dir in persist_dir.iterdir():
            if stage_dir.is_dir():
                assert any(stage_dir.glob("*.json")), f"{stage_dir.name} lacks a snapshot"

    async def test_debug_workflow_txt_format_exports_chapter_texts(self, tmp_path: Path) -> None:
        """Assert ``export_format='txt'`` skips the EPUB and returns the per-chapter text directory."""
        from fabricatio_core import Event, Role, Task
        from fabricatio_novel.workflows.novel import DebugNovelWorkflow

        namespace = "write_test_txt"
        persist_dir = tmp_path / "persist"
        Role.with_bio(name="writer_txt").subscribe(Event.quick_instantiate(namespace), DebugNovelWorkflow).dispatch()
        task = Task(name="wf novel texts").update_init_context(
            # Unique per run: every planning prompt embeds the outline and the span
            # prompt embeds the meta description, so a stale persistent-cache entry
            # can never serve a call and the dummy stack pops in seeded order.
            novel_outline=f"The lighthouse keeper's daughter charts the reef at low tide, wf v3 salt. [run:{uuid4().hex[:8]}]",
            novel_language="English",
            persist_dir=persist_dir,
            export_format=ExportFormat.TXT,
        )
        meta = NovelPlan(
            title="The Search",
            description=f"A hero searching for his father. [run:{uuid4().hex[:8]}]",
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
            Value.from_json(["Hero — brave protagonist, seeking his father."], name="bible roster"),
            Value.from_json(["A quiet riverside town in late summer."], name="bible background"),
            Value.from_json([CharacterSpan(start=card(), end=card()).model_dump()], name="character spans"),
            Value.from_json(chapter_plans_json, name="chapter plans"),
            Value.from_json(story_plans_json, name="story plans"),
            Value.from_json(scene_plans_json, name="scene plans"),
            Value.from_generic("He left.", name="scene prose"),
        ):
            artifact = await task.delegate(namespace)

        assert artifact is not None, "txt-format run must return the texts directory"
        assert artifact == persist_dir / "chapters"
        assert not (persist_dir / "novel.epub").exists()

    async def test_dump_stage_fires_post_process_novel_hook(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert DumpNovelStage runs post_process_novel on the assembled novel before export."""
        from fabricatio_core import Event, Role, Task
        from fabricatio_novel.actions.novel import DumpNovelStage
        from fabricatio_novel.models.context.novel import NovelContext
        from fabricatio_novel.models.novel import Novel
        from fabricatio_novel.workflows.novel import DebugNovelWorkflow

        async def mark_hook(self: object, ctx: NovelContext, novel: Novel, **kwargs: object) -> Novel:
            novel.chapter[0].story[0].scenes[0].content += " HOOKED"
            return novel

        monkeypatch.setattr(DumpNovelStage, "post_process_novel", mark_hook)

        namespace = "write_test_hook"
        persist_dir = tmp_path / "persist"
        Role.with_bio(name="writer_hook").subscribe(Event.quick_instantiate(namespace), DebugNovelWorkflow).dispatch()
        task = Task(name="wf novel hook").update_init_context(
            # Unique per run: every planning prompt embeds the outline and the span
            # prompt embeds the meta description, so a stale persistent-cache entry
            # can never serve a call and the dummy stack pops in seeded order.
            novel_outline=f"The clockmaker's apprentice winds the great gear at dawn. [run:{uuid4().hex[:8]}]",
            novel_language="English",
            persist_dir=persist_dir,
            export_format=ExportFormat.TXT,
        )
        meta = NovelPlan(
            title="The Search",
            description=f"A hero searching for his father. [run:{uuid4().hex[:8]}]",
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
            Value.from_json(["Hero — brave protagonist, seeking his father."], name="bible roster"),
            Value.from_json(["A quiet riverside town in late summer."], name="bible background"),
            Value.from_json([CharacterSpan(start=card(), end=card()).model_dump()], name="character spans"),
            Value.from_json(chapter_plans_json, name="chapter plans"),
            Value.from_json(story_plans_json, name="story plans"),
            Value.from_json(scene_plans_json, name="scene plans"),
            Value.from_generic("He left.", name="scene prose"),
        ):
            artifact = await task.delegate(namespace)

        assert artifact == persist_dir / "chapters"
        texts = list((persist_dir / "chapters").glob("*.txt"))
        assert texts, "chapter texts must be exported"
        assert any("HOOKED" in p.read_text(encoding="utf-8") for p in texts)

    async def test_dump_stage_calls_the_hook_with_the_declared_arguments_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert the dump action passes ``(ctx, novel)`` — a hook declaring no ``**kwargs`` still runs.

        The illustrated pipeline is a dump action of its own (:class:`IllustrateNovelStage`)
        precisely so this one never passes keywords the novel capability does not declare;
        the strict hook here rejects any leaked keyword with a ``TypeError``.
        """
        from fabricatio_novel.actions.novel import DumpNovelStage
        from fabricatio_novel.models.context.novel import NovelContext
        from fabricatio_novel.models.novel import Novel

        hooked: list[str] = []

        async def strict_hook(self: object, ctx: NovelContext, novel: Novel) -> Novel:
            hooked.append(ctx.outline)
            return novel

        monkeypatch.setattr(DumpNovelStage, "post_process_novel", strict_hook)

        ctx = NovelContext.create("The clockmaker's apprentice winds the great gear at dawn.", language="English")
        novel = Novel(
            title="The Gear",
            description="An apprentice winds the gear.",
            expected_word_count=100,
            writing_styles=[],
            writing_constraints=[],
            chapter=[],
        )

        artifact = await DumpNovelStage()._execute(ctx, novel, persist_dir=tmp_path, export_format=ExportFormat.TXT)

        assert hooked == [ctx.outline]
        assert artifact == tmp_path / "chapters"
        assert (tmp_path / "chapters").is_dir()
        assert next(tmp_path.glob("Novel_*.json"), None) is not None

    async def test_rag_illustration_workflow_embeds_scene_images(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert the RAG+illustration workflow renders scene images and embeds them in the EPUB."""
        import base64
        import zipfile

        from fabricatio_comfyui.models.specs import SketchSpec
        from fabricatio_core import Event, Role, Task
        from fabricatio_novel.actions.novel import IllustrateNovelStage
        from fabricatio_novel.benchmark.models import StageArtifact
        from fabricatio_novel.capabilities.rag import RAGStyleFetch
        from fabricatio_novel.models.context.novel import RagNovelContext
        from fabricatio_novel.workflows.novel import RagIllustrationDebugNovelWorkflow

        png_1x1 = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )

        async def fake_generate_image(prompt: str, download_dir: str | Path | None = None, **kwargs: object) -> Path:
            assert download_dir is not None
            target = Path(download_dir)
            target.mkdir(parents=True, exist_ok=True)
            path = target / "scene.png"
            path.write_bytes(png_1x1)
            return path

        async def fake_afetch_document(query: object, config: object | None = None) -> list[object]:
            return []

        async def fake_arefined_query(question: object, **kwargs: object) -> list[str]:
            return ["the floating atlas", "a drifting city"]

        monkeypatch.setattr(RAGStyleFetch, "afetch_document", staticmethod(fake_afetch_document))
        monkeypatch.setattr(RAGStyleFetch, "arefined_query", staticmethod(fake_arefined_query))

        monkeypatch.setattr(IllustrateNovelStage, "generate_image", staticmethod(fake_generate_image))

        namespace = "write_rag_illustration_test"
        persist_dir = tmp_path / "persist"
        Role.with_bio(name="writer").subscribe(
            Event.quick_instantiate(namespace), RagIllustrationDebugNovelWorkflow
        ).dispatch()
        task = Task(name="wf novel illustration").update_init_context(
            # Unique outline: every LLM prompt embeds it, so no persistent mock-router
            # cache entry can serve any call and skip its turn on the dummy response
            # stack. The illustration proposal itself is outline-independent; the
            # stack below keeps its value first so the steady state self-heals.
            # Resalt the outline whenever an upstream prompt template changes:
            # stale cache entries from the old prompt text otherwise create a
            # mixed hit/miss run that misaligns the scripted stack.
            novel_outline="A young tide-cartographer surveys the drowned bells of the Amber Strait, v5 salt.",
            novel_language="English",
            persist_dir=persist_dir,
        )
        meta = NovelPlan(
            title="The Floating Atlas II",
            description="An apprentice mapping a city that drifts among the clouds.",
            expected_word_count=100,
            writing_styles=[],
            writing_constraints=[],
        )
        chapter_plans_json = [
            {
                "title": "Harbor",
                "description": "The apprentice boards the ferry barge.",
                "weight": 1.0,
                "writing_styles": [],
                "writing_constraints": [],
            }
        ]
        story_plans_json = [
            {
                "title": "Departure",
                "description": "The mooring lines are cut at dawn.",
                "weight": 1.0,
                "writing_styles": [],
                "writing_constraints": [],
            }
        ]
        scene_plans_json = [
            {
                "title": "Cut Lines",
                "description": "The city pulls away from the sea.",
                "weight": 1.0,
                "writing_styles": [],
                "writing_constraints": [],
            }
        ]
        illustration = SketchSpec(prompt="a lone rider at dawn")
        with MockScript.from_values(
            # Stacks mirror the workflow's true LLM call order so the run is
            # deterministic whether or not the persistent cache serves any
            # key: metadata, bible roster and background, roster spans,
            # chapter/story/scene plan lists, the scene write, and finally
            # the outline-independent illustration proposal.
            Value.from_model(meta, name="novel metadata"),
            Value.from_json(["Hero — brave protagonist, seeking his father."], name="bible roster"),
            Value.from_json(["A quiet riverside town in late summer."], name="bible background"),
            Value.from_json([CharacterSpan(start=card(), end=card()).model_dump()], name="character spans"),
            Value.from_json(chapter_plans_json, name="chapter plans"),
            Value.from_json(story_plans_json, name="story plans"),
            Value.from_json(scene_plans_json, name="scene plans"),
            Value.from_generic("He left.", name="scene prose"),
            Value.from_model(illustration, name="illustration proposal"),
        ):
            epub = await task.delegate(namespace)

        assert epub == persist_dir / "novel.epub"
        assert epub is not None
        assert epub.is_file()
        stage_dirs = sorted(p.name for p in persist_dir.iterdir() if p.is_dir() and p.name.startswith("stage_"))
        assert stage_dirs == [
            "stage_01_init",
            "stage_02_metadata",
            "stage_03_bible",
            "stage_04_characters",
            "stage_05_chapter_plans",
            "stage_06_story_plans",
            "stage_07_scene_plans",
            "stage_08_scenes",
            "stage_09_novel",
        ]
        # the run is RAG-typed from the root down: the init and chapter-plan stages
        # snapshot trees whose retrieval state the benchmark's loader restores.
        stages = {stage.name: stage.load() for stage in StageArtifact.collect(persist_dir)}
        assert type(stages["stage_01_init"]) is RagNovelContext
        assert type(stages["stage_05_chapter_plans"]) is RagNovelContext
        with zipfile.ZipFile(epub) as zf:
            names = zf.namelist()
            assert any(name.endswith("images/scene_01_01.png") for name in names)
            assert any(
                b'<img src="images/scene_01_01.png"' in zf.read(name) for name in names if name.endswith(".xhtml")
            )
        assert (persist_dir / "images" / "scene_01_01.png").is_file()
