"""Staged-workflow tests for fabricatio-novel: DebugNovelWorkflow end to end."""

from pathlib import Path

import pytest
from _support import card, raw_value
from fabricatio_core.rust import CONFIG, TASK
from fabricatio_mock import DUMMY_LLM_GROUP
from fabricatio_mock.models.mock_router import Value, return_mixed_router_usage
from fabricatio_mock.utils import install_router_usage
from fabricatio_novel.models.context.base import CharacterSpan
from fabricatio_novel.models.plan import NovelPlan

# Workflow tests subscribe a plain ``Role`` (no scoped ``llm_send_to``), so the real
# resolver runs: route the ``task`` agent variant to the dummy router group so explicit
# ``send_to=TASK`` in the staged actions resolves to what ``install_router_usage`` seeds.
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
            novel_outline="The hero seeks his father across the winter mountains.",
            novel_language="English",
            persist_dir=persist_dir,
        )
        meta = NovelPlan(
            title="The Search",
            description="A hero searching for his father.",
            expected_word_count=100,
        )
        chapter_plans_json = [{"title": "Ch1", "description": "The hero sets out.", "weight": 1.0}]
        story_plans_json = [{"title": "St1", "description": "The departure.", "weight": 1.0}]
        scene_plans_json = [{"title": "S1", "description": "Leaving home.", "weight": 1.0}]
        with install_router_usage(
            *return_mixed_router_usage(
                Value(meta, "model"),
                Value(["Hero — brave protagonist, seeking his father."], "json"),
                Value(["A quiet riverside town in late summer."], "json"),
                Value([CharacterSpan(start=card(), end=card()).model_dump()], "json"),
                Value(chapter_plans_json, "json"),
                Value(story_plans_json, "json"),
                Value(scene_plans_json, "json"),
                raw_value("He left."),
            ),
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
        """Assert format='txt' skips the EPUB and returns the per-chapter text directory."""
        from fabricatio_core import Event, Role, Task
        from fabricatio_novel.workflows.novel import DebugNovelWorkflow

        namespace = "write_test_txt"
        persist_dir = tmp_path / "persist"
        Role.with_bio(name="writer_txt").subscribe(Event.quick_instantiate(namespace), DebugNovelWorkflow).dispatch()
        task = Task(name="wf novel texts").update_init_context(
            novel_outline="The lighthouse keeper's daughter charts the reef at low tide.",
            novel_language="English",
            persist_dir=persist_dir,
            format="txt",
        )
        meta = NovelPlan(
            title="The Search",
            description="A hero searching for his father.",
            expected_word_count=100,
        )
        chapter_plans_json = [{"title": "Ch1", "description": "The hero sets out.", "weight": 1.0}]
        story_plans_json = [{"title": "St1", "description": "The departure.", "weight": 1.0}]
        scene_plans_json = [{"title": "S1", "description": "Leaving home.", "weight": 1.0}]
        with install_router_usage(
            *return_mixed_router_usage(
                Value(meta, "model"),
                Value(["Hero — brave protagonist, seeking his father."], "json"),
                Value(["A quiet riverside town in late summer."], "json"),
                Value([CharacterSpan(start=card(), end=card()).model_dump()], "json"),
                Value(chapter_plans_json, "json"),
                Value(story_plans_json, "json"),
                Value(scene_plans_json, "json"),
                raw_value("He left."),
            ),
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
            novel_outline="The clockmaker's apprentice winds the great gear at dawn.",
            novel_language="English",
            persist_dir=persist_dir,
            format="txt",
        )
        meta = NovelPlan(
            title="The Search",
            description="A hero searching for his father.",
            expected_word_count=100,
        )
        chapter_plans_json = [{"title": "Ch1", "description": "The hero sets out.", "weight": 1.0}]
        story_plans_json = [{"title": "St1", "description": "The departure.", "weight": 1.0}]
        scene_plans_json = [{"title": "S1", "description": "Leaving home.", "weight": 1.0}]
        with install_router_usage(
            *return_mixed_router_usage(
                Value(meta, "model"),
                Value(["Hero — brave protagonist, seeking his father."], "json"),
                Value(["A quiet riverside town in late summer."], "json"),
                Value([CharacterSpan(start=card(), end=card()).model_dump()], "json"),
                Value(chapter_plans_json, "json"),
                Value(story_plans_json, "json"),
                Value(scene_plans_json, "json"),
                raw_value("He left."),
            ),
        ):
            artifact = await task.delegate(namespace)

        assert artifact == persist_dir / "chapters"
        texts = list((persist_dir / "chapters").glob("*.txt"))
        assert texts, "chapter texts must be exported"
        assert any("HOOKED" in p.read_text(encoding="utf-8") for p in texts)

    async def test_rag_illustration_workflow_embeds_scene_images(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert the RAG+illustration workflow renders scene images and embeds them in the EPUB."""
        import base64
        import zipfile

        from fabricatio_comfyui.models.specs import SketchSpec
        from fabricatio_core import Event, Role, Task
        from fabricatio_novel.actions.novel import IllustrateNovelStage
        from fabricatio_novel.capabilities.rag import RAGCompose
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

        monkeypatch.setattr(RAGCompose, "afetch_document", staticmethod(fake_afetch_document))

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
            novel_outline="A young tide-cartographer surveys the drowned bells of the Amber Strait.",
            novel_language="English",
            persist_dir=persist_dir,
        )
        meta = NovelPlan(
            title="The Floating Atlas II",
            description="An apprentice mapping a city that drifts among the clouds.",
            expected_word_count=100,
        )
        chapter_plans_json = [
            {"title": "Harbor", "description": "The apprentice boards the ferry barge.", "weight": 1.0}
        ]
        story_plans_json = [{"title": "Departure", "description": "The mooring lines are cut at dawn.", "weight": 1.0}]
        scene_plans_json = [{"title": "Cut Lines", "description": "The city pulls away from the sea.", "weight": 1.0}]
        illustration = SketchSpec(prompt="a lone rider at dawn")
        with install_router_usage(
            *return_mixed_router_usage(
                # The scene-write and illustration prompts embed the manuscript
                # context first, so their first post-change runs miss the
                # persistent cache and consume the stack head in stage order:
                # the scene write takes the raw prose, the illustrate-stage
                # proposal takes the illustration value next.
                raw_value("He left."),
                Value(illustration, "model"),
                Value(meta, "model"),
                Value(["Hero — brave protagonist, seeking his father."], "json"),
                Value(["A quiet riverside town in late summer."], "json"),
                Value([CharacterSpan(start=card(), end=card()).model_dump()], "json"),
                Value(chapter_plans_json, "json"),
                Value(story_plans_json, "json"),
                Value(scene_plans_json, "json"),
                raw_value("He left."),
            ),
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
        with zipfile.ZipFile(epub) as zf:
            names = zf.namelist()
            assert any(name.endswith("images/scene_01_01.png") for name in names)
            assert any(
                b'<img src="images/scene_01_01.png"' in zf.read(name) for name in names if name.endswith(".xhtml")
            )
        assert (persist_dir / "images" / "scene_01_01.png").is_file()
