"""Staged-workflow tests for fabricatio-novel: DebugNovelWorkflow end to end."""

from pathlib import Path

from _support import raw_value
from fabricatio_mock.models.mock_router import Value, return_mixed_router_usage
from fabricatio_mock.utils import install_router_usage
from fabricatio_novel.models.plan import NovelPlan
from fabricatio_novel.models.series_book import SeriesBible


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

    async def test_debug_workflow_txt_format_exports_chapter_texts(self, tmp_path: Path) -> None:
        """Assert format='txt' skips the EPUB and returns the per-chapter text directory."""
        from fabricatio_core import Event, Role, Task
        from fabricatio_novel.workflows.novel import DebugNovelWorkflow

        namespace = "write_test_txt"
        persist_dir = tmp_path / "persist"
        Role.with_bio(name="writer_txt").subscribe(Event.quick_instantiate(namespace), DebugNovelWorkflow).dispatch()
        task = Task(name="wf novel texts").update_init_context(
            novel_outline="The hero seeks his father.",
            novel_language="English",
            persist_dir=persist_dir,
            format="txt",
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
            artifact = await task.delegate(namespace)

        assert artifact is not None, "txt-format run must return the texts directory"
        assert artifact == persist_dir / "chapters"
        assert not (persist_dir / "novel.epub").exists()
