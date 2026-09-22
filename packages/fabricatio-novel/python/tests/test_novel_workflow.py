"""Staged-workflow tests for fabricatio-novel: DebugNovelWorkflow end to end."""

from pathlib import Path

import pytest
from _support import card
from fabricatio_character.models.character import CharacterSpan
from fabricatio_core.rust import CONFIG, PLAN, TASK
from fabricatio_mock import DUMMY_LLM_GROUP, MockScript, Value, make_test_role
from fabricatio_novel.models.novel import ExportFormat
from fabricatio_novel.models.plan import NovelPlan

# Workflow tests subscribe ``make_test_role`` roles: llm_no_cache/llm_no_store (and the
# embedding/reranker twins) keep every dummy call out of the shared cache, so the
# ``MockScript`` stack pops in seeded order. The stages resolve their own routing through
# the variant slots — ``TASK`` for a run that names no group, ``PLAN`` for the plan stages'
# fallback — so route both variants to the dummy group.
CONFIG.configure_llm_variant(TASK, DUMMY_LLM_GROUP)
CONFIG.configure_llm_variant(PLAN, DUMMY_LLM_GROUP)


PLAN_PROBE_GROUP = "wf_plan_probe_run"
"""Routing group the plan-routing tests deploy the run-tier chapter plan to, standing in for ``--send-to``."""


async def _planned_titles(send_to: str | None = None) -> list[str]:
    """Plan chapters once and return the title that materialized, naming the group the call rode.

    The run group holds a chapter plan titled ``TASK-TIER`` and the plan slot one titled
    ``PLAN-TIER``, so the materialized title reports which of the two the planning call used.
    The stage's own ``llm_no_cache``/``llm_no_store`` keep the shared completion cache from
    serving either plan regardless of routing: both dummy groups share one model id, so an
    identical prompt would otherwise be a cross-group hit.

    Args:
        send_to: Routing group to plan with, or ``None`` for a run whose context names none.
    """
    from fabricatio_novel.actions.novel import PlanChaptersStage
    from fabricatio_novel.models.context.novel import NovelContext

    def plans(title: str) -> list[dict[str, object]]:
        return [
            {
                "title": title,
                "description": "The hero sets out.",
                "weight": 1.0,
                "writing_styles": [],
                "writing_constraints": [],
            }
        ]

    novel = NovelContext.create("The hero seeks his father over the pass..", language="English")
    CONFIG.configure_llm_variant(TASK, PLAN_PROBE_GROUP)
    try:
        with (
            MockScript.from_values(Value.from_json(plans("PLAN-TIER"), name="plan tier plans")),
            MockScript.from_values(Value.from_json(plans("TASK-TIER"), name="run tier plans"), group=PLAN_PROBE_GROUP),
        ):
            stage = PlanChaptersStage(llm_no_cache=True, llm_no_store=True)
            cxt: dict[str, str] = {} if send_to is None else {"send_to": send_to}
            assert await stage._execute(novel, **cxt) is True
    finally:
        CONFIG.configure_llm_variant(TASK, DUMMY_LLM_GROUP)
    return [chapter.title for chapter in novel.child_contexts]


class TestNovelWorkflow:
    """Test suite for the staged DebugNovelWorkflow."""

    async def test_debug_workflow_stages_persist_snapshots_and_returns_epub(self, tmp_path: Path) -> None:
        """Assert the workflow runs every stage, persists per-stage snapshots, and returns the EPUB path."""
        from fabricatio_core import Event, Task
        from fabricatio_novel.workflows.novel import DebugNovelWorkflow

        namespace = "write_test"
        persist_dir = tmp_path / "persist"
        make_test_role(name="writer").subscribe(Event.quick_instantiate(namespace), DebugNovelWorkflow).dispatch()
        task = Task(name="wf novel").update_init_context(
            novel_outline="The hero seeks his father across the winter mountains.",
            novel_language="English",
            persist_dir=persist_dir,
        )
        meta = NovelPlan(
            title="The Search",
            description="A hero searching for his father.",
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

    async def test_plan_stage_falls_back_to_the_plan_variant(self) -> None:
        """Assert an unrouted run plans through the PLAN slot."""
        assert await _planned_titles() == ["PLAN-TIER"]

    async def test_explicit_send_to_outranks_the_plan_fallback(self) -> None:
        """Assert an explicit run group still governs planning, so PLAN stays a fallback and not a must."""
        assert await _planned_titles(PLAN_PROBE_GROUP) == ["TASK-TIER"]

    async def test_debug_workflow_txt_format_exports_chapter_texts(self, tmp_path: Path) -> None:
        """Assert ``export_format='txt'`` skips the EPUB and returns the per-chapter text directory."""
        from fabricatio_core import Event, Task
        from fabricatio_novel.workflows.novel import DebugNovelWorkflow

        namespace = "write_test_txt"
        persist_dir = tmp_path / "persist"
        make_test_role(name="writer_txt").subscribe(Event.quick_instantiate(namespace), DebugNovelWorkflow).dispatch()
        task = Task(name="wf novel texts").update_init_context(
            novel_outline="The lighthouse keeper's daughter charts the reef at low tide.",
            novel_language="English",
            persist_dir=persist_dir,
            export_format=ExportFormat.TXT,
        )
        meta = NovelPlan(
            title="The Search",
            description="A hero searching for his father.",
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
        from fabricatio_core import Event, Task
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
        make_test_role(name="writer_hook").subscribe(Event.quick_instantiate(namespace), DebugNovelWorkflow).dispatch()
        task = Task(name="wf novel hook").update_init_context(
            novel_outline="The clockmaker's apprentice winds the great gear at dawn.",
            novel_language="English",
            persist_dir=persist_dir,
            export_format=ExportFormat.TXT,
        )
        meta = NovelPlan(
            title="The Search",
            description="A hero searching for his father.",
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
        from fabricatio_core import Event, Task
        from fabricatio_novel.actions.illustration import IllustrateNovelStage
        from fabricatio_novel.benchmark.models import StageArtifact
        from fabricatio_novel.capabilities.rag import RAGStyleFetch
        from fabricatio_novel.models.context.novel import RagNovelContext
        from fabricatio_novel.workflows.illustration import RagIllustrationDebugNovelWorkflow

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
        make_test_role(name="writer").subscribe(
            Event.quick_instantiate(namespace), RagIllustrationDebugNovelWorkflow
        ).dispatch()
        task = Task(name="wf novel illustration").update_init_context(
            # The test role's no_cache/no_store keep calls off the persistent cache,
            # so every LLM call pops its seeded Value in order. The illustration
            # proposal itself is outline-independent; the stack below keeps its value
            # first so the steady state self-heals.
            novel_outline="A young tide-cartographer surveys the drowned bells of the Amber Strait.",
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
            # Stacks mirror the workflow's true LLM call order — metadata, bible
            # roster and background, roster spans, chapter/story/scene plan
            # lists, the scene write, and finally the outline-independent
            # illustration proposal — so the run stays deterministic.
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
