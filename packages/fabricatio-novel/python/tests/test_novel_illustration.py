"""Post-process ComfyUI illustration tests for fabricatio-novel."""

import asyncio
import base64
from pathlib import Path

import pytest
from fabricatio_comfyui.models import LoraCatalog, LoraEntry, LoraPick, LoraSelection, LoraSpec
from fabricatio_comfyui.models.resolution import Prop
from fabricatio_comfyui.models.specs import SketchSpec
from fabricatio_core import Role
from fabricatio_core.rust import CONFIG, SMOL, TASK
from fabricatio_judge.models.judgement import ImageVerdict
from fabricatio_mock import MockScript, Value, make_test_role
from fabricatio_novel.capabilities.illustration import IllustrateScenes
from fabricatio_novel.config import NovelConfig, novel_config
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.illustration import IllustratedScene
from fabricatio_novel.models.illustration_queue import (
    PendingIllustration,
    SceneIllustrationQueue,
)
from fabricatio_novel.models.novel import Novel
from fabricatio_novel.models.scene import Scene

_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def build_novel_ctx(*scene_titles: str) -> NovelContext:
    """Build a one-chapter novel context whose single story holds the given scenes."""
    ctx = NovelContext.create("The hero seeks his father.", language="English")
    chapter_ctx = ChapterContext(title="Ch1", description="The hero sets out.")
    story_ctx = StoryContext(title="St1", description="The departure.")
    for title in scene_titles:
        story_ctx.child_contexts.append(
            SceneContext(title=title, description=f"{title} description.", expected_word_count=20)
        )
    chapter_ctx.child_contexts.append(story_ctx)
    ctx.child_contexts.append(chapter_ctx)
    return ctx


def build_two_story_novel_ctx() -> NovelContext:
    """Build a one-chapter novel context holding two stories with one, two, and zero scenes split across them."""
    ctx = NovelContext.create("The hero seeks his father.", language="English")
    chapter_ctx = ChapterContext(title="Ch1", description="The hero sets out.")
    for story_title, scene_titles in (("St1", ("S1",)), ("St2", ("S2", "S3"))):
        story_ctx = StoryContext(title=story_title, description=f"The {story_title} leg.")
        for title in scene_titles:
            story_ctx.child_contexts.append(
                SceneContext(title=title, description=f"{title} description.", expected_word_count=20)
            )
        chapter_ctx.child_contexts.append(story_ctx)
    ctx.child_contexts.append(chapter_ctx)
    return ctx


def novel_config_with(**overrides: object) -> NovelConfig:
    """Return a NovelConfig clone carrying the given field overrides.

    The TOML-declared always-on lora chain and the default quality-tag
    render suffix are stripped unless the caller overrides
    ``illustration_always_loras`` / ``illustration_prompt_suffix``
    explicitly, keeping prompt assertions independent of local config
    drift.
    """
    base = {
        **novel_config.model_dump(),
        "illustration_always_loras": [],
        "illustration_prompt_suffix": "",
    }
    return NovelConfig.model_validate({**base, **overrides})


def install_fake_renderer(monkeypatch: pytest.MonkeyPatch, outcomes: list[Path | Exception | None]) -> list[str]:
    """Patch generate_image with a fake 1x1-PNG renderer consuming per-call outcomes.

    Each outcome is a returned path, ``None`` (failed generation), or an exception to raise.
    Records every received prompt in order and returns the prompts list.
    """
    prompts: list[str] = []

    async def fake_generate_image(prompt: str, download_dir: str | Path | None = None, **kwargs: object) -> Path | None:
        outcome = outcomes[len(prompts)]
        prompts.append(prompt)
        if isinstance(outcome, Exception):
            raise outcome
        if outcome is None:
            return None
        assert download_dir is not None
        target = Path(download_dir)
        target.mkdir(parents=True, exist_ok=True)
        path = target / f"img_{len(prompts)}.png"
        path.write_bytes(_PNG_1X1)
        return path

    monkeypatch.setattr(IllustrateScenes, "generate_image", staticmethod(fake_generate_image))
    return prompts


def install_distinct_renderer(monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], list[bytes]]:
    """Patch generate_image with a fake renderer writing a distinct 1x1 PNG per call.

    Returns the received prompts and the distinct PNG bytes in call order, so
    judge-loop tests can pin which attempt's bytes ended up where.
    """
    prompts: list[str] = []
    pngs: list[bytes] = []

    async def fake_generate_image(prompt: str, download_dir: str | Path | None = None, **kwargs: object) -> Path:
        prompts.append(prompt)
        assert download_dir is not None
        target = Path(download_dir)
        target.mkdir(parents=True, exist_ok=True)
        path = target / f"img_{len(prompts)}.png"
        data = _PNG_1X1 + str(len(prompts)).encode()
        path.write_bytes(data)
        pngs.append(data)
        return path

    monkeypatch.setattr(IllustrateScenes, "generate_image", staticmethod(fake_generate_image))
    return prompts, pngs


class _IllustrationProbeRole(Role, IllustrateScenes):
    """Illustration role whose proposals keep the framework's own variant routing.

    ``make_test_role`` composes an ``LLMTestRole``, which pins every completion to the
    dummy group and so cannot tell one variant slot from another; a routing test needs
    the plain resolution ladder instead. ``llm_no_cache``/``llm_no_store`` are set per
    instance, as the workflow tests do, so no probe group can leave a canned completion
    behind in the shared completion cache.
    """


class TestIllustrateNovelPhase:
    """Test suite for the post-process illustration phase."""

    async def test_illustrate_novel_phase_records_prompt_and_image_per_scene(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert every scene gets its proposed prompt recorded and its PNG copied to the canonical name."""
        monkeypatch.setattr(
            "fabricatio_novel.capabilities.illustration.novel_config",
            novel_config_with(),
        )
        ctx = build_novel_ctx("S1", "S2")
        prompts = install_fake_renderer(monkeypatch, [tmp_path / "unused.png"] * 2)
        role = make_test_role(IllustrateScenes, name="illustrator")
        proposals = [
            SketchSpec(prompt="a lone rider at dawn", negative_prompt="text, watermark"),
            SketchSpec(prompt="a stranger at the gate"),
        ]
        with MockScript.from_values(
            *(Value.from_model(p, name=f"sketch {i}") for i, p in enumerate(proposals, start=1))
        ):
            illustrations = await role.illustrate_novel_phase(ctx, persist_dir=tmp_path)

        assert set(illustrations) == {(1, 1), (1, 2)}
        assert set(prompts) == {"a lone rider at dawn", "a stranger at the gate"}
        assert {prompt for prompt, _ in illustrations.values()} == {"a lone rider at dawn", "a stranger at the gate"}
        assert illustrations[(1, 1)][1] == str((tmp_path / "images" / "scene_01_01.png").resolve())
        assert illustrations[(1, 2)][1] == str((tmp_path / "images" / "scene_01_02.png").resolve())
        assert (tmp_path / "images" / "scene_01_01.png").is_file()
        assert (tmp_path / "images" / "scene_01_02.png").is_file()

    async def test_illustrate_novel_phase_defaults_to_the_smol_slot(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert an unrouted illustration proposal rides the ``SMOL`` variant, not the run's ``TASK`` group.

        The writing stages default to ``TASK``, so a proposal answered from the ``TASK`` probe
        would mean illustration followed the writing tier; each slot holds a distinguishable
        sketch, and the render prompt keeps the answering sketch's head.
        """
        ctx = build_novel_ctx("S1")
        install_fake_renderer(monkeypatch, [tmp_path / "unused.png"])
        role = _IllustrationProbeRole(name="illustration_probe", llm_no_cache=True, llm_no_store=True)
        smol_probe = "illustration_smol_probe"
        task_probe = "illustration_task_probe"
        previous = {SMOL: CONFIG.resolve_llm_variant(SMOL), TASK: CONFIG.resolve_llm_variant(TASK)}
        CONFIG.configure_llm_variant(SMOL, smol_probe)
        CONFIG.configure_llm_variant(TASK, task_probe)
        try:
            with (
                MockScript.from_values(
                    Value.from_model(SketchSpec(prompt="the smol sketch"), name="smol sketch"),
                    group=smol_probe,
                ),
                MockScript.from_values(
                    Value.from_model(SketchSpec(prompt="the task sketch"), name="task sketch"),
                    group=task_probe,
                ),
            ):
                illustrations = await role.illustrate_novel_phase(ctx, persist_dir=tmp_path)
        finally:
            CONFIG.configure_llm_variant(SMOL, previous[SMOL])
            CONFIG.configure_llm_variant(TASK, previous[TASK])

        prompts = [prompt for prompt, _ in illustrations.values()]
        assert len(prompts) == 1
        assert prompts[0].startswith("the smol sketch")

    async def test_illustrate_novel_phase_skips_existing_png(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert scenes whose illustration PNG already exists are skipped and only the rest get proposed."""
        ctx = build_novel_ctx("S1", "S2")
        images_dir = tmp_path / "images"
        images_dir.mkdir()
        monkeypatch.setattr(
            "fabricatio_novel.capabilities.illustration.novel_config",
            novel_config_with(),
        )
        (images_dir / "scene_01_01.png").write_bytes(_PNG_1X1)
        prompts = install_fake_renderer(monkeypatch, [tmp_path / "unused.png"])
        role = make_test_role(IllustrateScenes, name="illustrator")
        proposal = SketchSpec(prompt="a stranger at the gate")
        with MockScript.from_values(Value.from_model(proposal, name="sketch 1")):
            illustrations = await role.illustrate_novel_phase(ctx, persist_dir=tmp_path)

        assert set(illustrations) == {(1, 2)}
        assert prompts == ["a stranger at the gate"]
        assert (images_dir / "scene_01_01.png").read_bytes() == _PNG_1X1

    async def test_illustrate_novel_phase_regenerates_when_skip_existing_disabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert illustration_skip_existing=False re-renders scenes whose PNG already exists."""
        monkeypatch.setattr(
            "fabricatio_novel.models.illustration_queue.novel_config",
            novel_config_with(illustration_skip_existing=False),
        )
        ctx = build_novel_ctx("S1", "S2")
        images_dir = tmp_path / "images"
        images_dir.mkdir()
        monkeypatch.setattr(
            "fabricatio_novel.capabilities.illustration.novel_config",
            novel_config_with(),
        )
        (images_dir / "scene_01_01.png").write_bytes(_PNG_1X1)
        prompts = install_fake_renderer(monkeypatch, [tmp_path / "unused.png"] * 2)
        role = make_test_role(IllustrateScenes, name="illustrator")
        proposals = [SketchSpec(prompt="redrawn dawn"), SketchSpec(prompt="redrawn gate")]
        with MockScript.from_values(
            *(Value.from_model(p, name=f"sketch {i}") for i, p in enumerate(proposals, start=1))
        ):
            illustrations = await role.illustrate_novel_phase(ctx, persist_dir=tmp_path)

        assert set(illustrations) == {(1, 1), (1, 2)}
        assert set(prompts) == {"redrawn dawn", "redrawn gate"}

    async def test_illustrate_novel_phase_degrades_when_generation_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert a None render and a raised render each skip the scene without failing the phase."""
        ctx = build_novel_ctx("S1", "S2")
        prompts = install_fake_renderer(monkeypatch, [None, RuntimeError("comfyui down")])
        role = make_test_role(IllustrateScenes, name="illustrator")
        proposals = [
            SketchSpec(prompt="a lone rider at dawn"),
            SketchSpec(prompt="a stranger at the gate"),
        ]
        with MockScript.from_values(
            *(Value.from_model(p, name=f"sketch {i}") for i, p in enumerate(proposals, start=1))
        ):
            illustrations = await role.illustrate_novel_phase(ctx, persist_dir=tmp_path)

        assert illustrations == {}
        assert len(prompts) == 2
        assert not (tmp_path / "images" / "scene_01_01.png").exists()
        assert not (tmp_path / "images" / "scene_01_02.png").exists()

    async def test_illustrate_novel_phase_skips_proposal_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert a failed proposal skips only that scene and the next scene still illustrates."""
        monkeypatch.setattr(
            "fabricatio_novel.capabilities.illustration.novel_config",
            novel_config_with(),
        )
        ctx = build_novel_ctx("S1", "S2")
        prompts = install_fake_renderer(monkeypatch, [tmp_path / "unused.png"])
        role = make_test_role(IllustrateScenes, name="illustrator")
        proposal = SketchSpec(prompt="a stranger at the gate")

        async def fake_propose(model: object, requirement: str, **kwargs: object) -> SketchSpec | None:
            # Key the failure to the S1 requirement so the outcome is deterministic under batching.
            return None if "Title: S1" in requirement else proposal

        monkeypatch.setattr(type(role), "propose", staticmethod(fake_propose))
        illustrations = await role.illustrate_novel_phase(ctx, persist_dir=tmp_path)

        assert set(illustrations) == {(1, 2)}
        assert prompts == ["a stranger at the gate"]

    async def test_illustrate_novel_phase_numbers_scenes_across_stories(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert scene indices keep increasing across stories so names match the EPUB exporter."""
        ctx = build_two_story_novel_ctx()
        prompts = install_fake_renderer(monkeypatch, [tmp_path / "unused.png"] * 3)
        role = make_test_role(IllustrateScenes, name="illustrator")
        proposals = [SketchSpec(prompt=f"scene {i}") for i in range(1, 4)]
        with MockScript.from_values(
            *(Value.from_model(p, name=f"sketch {i}") for i, p in enumerate(proposals, start=1))
        ):
            illustrations = await role.illustrate_novel_phase(ctx, persist_dir=tmp_path)

        assert set(illustrations) == {(1, 1), (1, 2), (1, 3)}
        assert (tmp_path / "images" / "scene_01_01.png").is_file()
        assert (tmp_path / "images" / "scene_01_02.png").is_file()
        assert (tmp_path / "images" / "scene_01_03.png").is_file()
        assert len(prompts) == 3

    async def test_illustrate_novel_phase_renders_concurrently(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert renders for all pending scenes are in flight together, not one-by-one."""
        ctx = build_novel_ctx("S1", "S2")
        barrier = asyncio.Barrier(2)
        seen: list[str] = []

        async def fake_generate_image(prompt: str, download_dir: str | Path | None = None, **kwargs: object) -> Path:
            seen.append(prompt)
            await asyncio.wait_for(barrier.wait(), timeout=5)
            assert download_dir is not None
            target = Path(download_dir)
            target.mkdir(parents=True, exist_ok=True)
            path = target / f"img_{len(seen)}.png"
            path.write_bytes(_PNG_1X1)
            return path

        async def fake_propose(model: object, requirement: object, **kwargs: object) -> SketchSpec:
            return SketchSpec(prompt=f"prompt {len(seen) + 1}")

        monkeypatch.setattr(IllustrateScenes, "generate_image", staticmethod(fake_generate_image))
        monkeypatch.setattr(IllustrateScenes, "propose", staticmethod(fake_propose))
        role = make_test_role(IllustrateScenes, name="illustrator")
        illustrations = await role.illustrate_novel_phase(ctx, persist_dir=tmp_path)

        assert set(illustrations) == {(1, 1), (1, 2)}
        assert len(seen) == 2

    async def test_illustrate_novel_phase_scales_timeout_with_batch_size(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert every render receives ``illustration_timeout_per_image`` x pending renders."""
        ctx = build_novel_ctx("S1", "S2", "S3")
        timeouts: list[float] = []

        async def fake_generate_image(prompt: str, download_dir: str | Path | None = None, **kwargs: object) -> Path:
            received = kwargs["timeout"]
            assert isinstance(received, (int, float))
            timeouts.append(float(received))
            assert download_dir is not None
            target = Path(download_dir)
            target.mkdir(parents=True, exist_ok=True)
            path = target / f"img_{len(timeouts)}.png"
            path.write_bytes(_PNG_1X1)
            return path

        monkeypatch.setattr(IllustrateScenes, "generate_image", staticmethod(fake_generate_image))
        role = make_test_role(IllustrateScenes, name="illustrator")
        proposals = [SketchSpec(prompt=f"dawn {i}") for i in range(3)]
        with MockScript.from_values(
            *(Value.from_model(p, name=f"sketch {i}") for i, p in enumerate(proposals, start=1))
        ):
            illustrations = await role.illustrate_novel_phase(ctx, persist_dir=tmp_path)

        assert set(illustrations) == {(1, 1), (1, 2), (1, 3)}
        assert timeouts == [novel_config.illustration_timeout_per_image * 3] * 3

    async def test_illustrate_novel_phase_timeout_follows_configured_per_image_value(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert a custom ``illustration_timeout_per_image`` scales the batch timeout linearly."""
        monkeypatch.setattr(
            "fabricatio_novel.capabilities.illustration.novel_config",
            novel_config_with(illustration_timeout_per_image=5.0),
        )
        ctx = build_novel_ctx("S1", "S2")
        timeouts: list[float] = []

        async def fake_generate_image(prompt: str, download_dir: str | Path | None = None, **kwargs: object) -> Path:
            received = kwargs["timeout"]
            assert isinstance(received, (int, float))
            timeouts.append(float(received))
            assert download_dir is not None
            target = Path(download_dir)
            target.mkdir(parents=True, exist_ok=True)
            path = target / f"img_{len(timeouts)}.png"
            path.write_bytes(_PNG_1X1)
            return path

        monkeypatch.setattr(IllustrateScenes, "generate_image", staticmethod(fake_generate_image))
        role = make_test_role(IllustrateScenes, name="illustrator")
        proposals = [SketchSpec(prompt="dawn"), SketchSpec(prompt="dusk")]
        with MockScript.from_values(
            *(Value.from_model(p, name=f"sketch {i}") for i, p in enumerate(proposals, start=1))
        ):
            illustrations = await role.illustrate_novel_phase(ctx, persist_dir=tmp_path)

        assert set(illustrations) == {(1, 1), (1, 2)}
        assert timeouts == [10.0, 10.0]

    async def test_illustrate_novel_phase_applies_constraint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert the constraint reaches every proposal requirement, per-call arg winning over scoped."""
        requirements: list[str] = []

        async def fake_propose(model: object, requirement: str, **kwargs: object) -> SketchSpec:
            requirements.append(requirement)
            return SketchSpec(prompt="a lone rider at dawn")

        async def fake_generate_image(prompt: str, download_dir: str | Path | None = None, **kwargs: object) -> Path:
            assert download_dir is not None
            target = Path(download_dir)
            target.mkdir(parents=True, exist_ok=True)
            path = target / "img.png"
            path.write_bytes(_PNG_1X1)
            return path

        monkeypatch.setattr(IllustrateScenes, "propose", staticmethod(fake_propose))
        monkeypatch.setattr(IllustrateScenes, "generate_image", staticmethod(fake_generate_image))

        scoped_role = make_test_role(IllustrateScenes, name="scoped")
        scoped_role.illustration_constraint = "scoped ink style"
        await scoped_role.illustrate_novel_phase(build_novel_ctx("S1"), persist_dir=tmp_path / "scoped")
        assert all("## Style Constraints" in req and "scoped ink style" in req for req in requirements)

        explicit_role = make_test_role(IllustrateScenes, name="explicit")
        explicit_role.illustration_constraint = "scoped ink style"
        await explicit_role.illustrate_novel_phase(
            build_novel_ctx("S1"), persist_dir=tmp_path / "explicit", illustration_constraint="explicit oil"
        )
        assert all("explicit oil" in req and "scoped ink style" not in req for req in requirements[1:])

        plain_role = make_test_role(IllustrateScenes, name="plain")
        await plain_role.illustrate_novel_phase(build_novel_ctx("S1"), persist_dir=tmp_path / "plain")
        assert all("## Style Constraints" not in req for req in requirements[2:])

    async def test_illustrate_novel_phase_scene_knobs_override_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert per-scene SketchSpec mp/prop win over the global illustration config."""
        monkeypatch.setattr(
            "fabricatio_novel.capabilities.illustration.novel_config",
            novel_config_with(illustration_mp=0.75, illustration_prop=Prop.prop_3_4),
        )
        ctx = build_novel_ctx("S1", "S2")
        seen: list[tuple[object, object]] = []

        async def fake_generate_image(prompt: str, download_dir: str | Path | None = None, **kwargs: object) -> Path:
            seen.append((kwargs["prop"], kwargs["mp"]))
            assert download_dir is not None
            target = Path(download_dir)
            target.mkdir(parents=True, exist_ok=True)
            path = target / f"img_{len(seen)}.png"
            path.write_bytes(_PNG_1X1)
            return path

        monkeypatch.setattr(IllustrateScenes, "generate_image", staticmethod(fake_generate_image))
        role = make_test_role(IllustrateScenes, name="illustrator")
        proposals = [
            SketchSpec(prompt="wide dawn", prop=Prop.prop_16_9, mp=1.0),
            SketchSpec(prompt="tall gate"),  # no size: falls back to the global illustration_mp/prop
        ]
        with MockScript.from_values(
            *(Value.from_model(p, name=f"sketch {i}") for i, p in enumerate(proposals, start=1))
        ):
            illustrations = await role.illustrate_novel_phase(ctx, persist_dir=tmp_path)

        assert set(illustrations) == {(1, 1), (1, 2)}
        assert seen == [(Prop.prop_16_9, 1.0), (Prop.prop_3_4, 0.75)]

    async def test_illustrate_novel_phase_clamps_oversized_mp_proposal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert a proposal exceeding the mp ceiling is clamped before rendering."""
        ctx = build_novel_ctx("S1", "S2")
        seen: list[object] = []

        async def fake_generate_image(prompt: str, download_dir: str | Path | None = None, **kwargs: object) -> Path:
            seen.append(kwargs["mp"])
            assert download_dir is not None
            target = Path(download_dir)
            target.mkdir(parents=True, exist_ok=True)
            path = target / f"img_{len(seen)}.png"
            path.write_bytes(_PNG_1X1)
            return path

        monkeypatch.setattr(IllustrateScenes, "generate_image", staticmethod(fake_generate_image))
        role = make_test_role(IllustrateScenes, name="illustrator")
        proposals = [
            SketchSpec(prompt="over budget", mp=6.0),
            SketchSpec(prompt="within budget", mp=0.8),
        ]
        with MockScript.from_values(
            *(Value.from_model(p, name=f"sketch {i}") for i, p in enumerate(proposals, start=1))
        ):
            illustrations = await role.illustrate_novel_phase(ctx, persist_dir=tmp_path)

        assert set(illustrations) == {(1, 1), (1, 2)}
        assert seen == [1.2, 0.8]

    async def test_illustrate_novel_phase_ceiling_follows_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert the clamping ceiling follows the configured illustration_mp_max."""
        monkeypatch.setattr(
            "fabricatio_novel.capabilities.illustration.novel_config",
            novel_config_with(illustration_mp_max=0.5),
        )
        ctx = build_novel_ctx("S1", "S2")
        seen: list[object] = []

        async def fake_generate_image(prompt: str, download_dir: str | Path | None = None, **kwargs: object) -> Path:
            seen.append(kwargs["mp"])
            assert download_dir is not None
            target = Path(download_dir)
            target.mkdir(parents=True, exist_ok=True)
            path = target / f"img_{len(seen)}.png"
            path.write_bytes(_PNG_1X1)
            return path

        monkeypatch.setattr(IllustrateScenes, "generate_image", staticmethod(fake_generate_image))
        role = make_test_role(IllustrateScenes, name="illustrator")
        proposals = [
            SketchSpec(prompt="way over", mp=6.0),
            SketchSpec(prompt="just under", mp=0.4),
        ]
        with MockScript.from_values(
            *(Value.from_model(p, name=f"sketch {i}") for i, p in enumerate(proposals, start=1))
        ):
            illustrations = await role.illustrate_novel_phase(ctx, persist_dir=tmp_path)

        assert set(illustrations) == {(1, 1), (1, 2)}
        assert seen == [0.5, 0.4]

    async def test_illustrate_novel_phase_skips_lora_selection_by_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert the gate keeps catalog selection (and its LLM call) fully off unless opted in."""
        monkeypatch.setattr(
            "fabricatio_novel.capabilities.illustration.novel_config",
            novel_config_with(illustration_choose_loras=False),
        )
        catalog = LoraCatalog(
            entries=[
                LoraEntry(
                    lora_name="pose.safetensors", strength=0.65, effect="poses the subject", trigger_words="xpose"
                )
            ]
        )
        monkeypatch.setattr(LoraCatalog, "from_config", classmethod(lambda cls: catalog))

        def _forbidden(*_args: object, **_kwargs: object) -> list[LoraSpec]:
            raise AssertionError("choose_loras must not run when the gate is off")

        monkeypatch.setattr(IllustrateScenes, "choose_loras", staticmethod(_forbidden))
        seen: list[object] = []
        prompts: list[str] = []

        async def fake_generate_image(prompt: str, download_dir: str | Path | None = None, **kwargs: object) -> Path:
            seen.append(kwargs["loras"])
            prompts.append(prompt)
            assert download_dir is not None
            target = Path(download_dir)
            target.mkdir(parents=True, exist_ok=True)
            path = target / "img.png"
            path.write_bytes(_PNG_1X1)
            return path

        monkeypatch.setattr(IllustrateScenes, "generate_image", staticmethod(fake_generate_image))
        role = make_test_role(IllustrateScenes, name="illustrator")
        with MockScript.from_values(Value.from_model(SketchSpec(prompt="dawn"), name="sketch 1")):
            await role.illustrate_novel_phase(build_novel_ctx("S1"), persist_dir=tmp_path)
        assert seen == [[]]
        assert prompts == ["dawn"]

    async def test_illustrate_novel_phase_chains_always_loras(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert always-on loras ride every render chain and their trigger words activate."""
        monkeypatch.setattr(
            "fabricatio_novel.capabilities.illustration.novel_config",
            novel_config_with(
                illustration_always_loras=[
                    LoraEntry(
                        lora_name="style.safetensors", strength=0.5, effect="style anchor", trigger_words="xstyle"
                    )
                ]
            ),
        )
        ctx = build_novel_ctx("S1")
        seen: list[object] = []
        prompts: list[str] = []

        async def fake_generate_image(prompt: str, download_dir: str | Path | None = None, **kwargs: object) -> Path:
            seen.append(kwargs["loras"])
            prompts.append(prompt)
            assert download_dir is not None
            target = Path(download_dir)
            target.mkdir(parents=True, exist_ok=True)
            path = target / "img.png"
            path.write_bytes(_PNG_1X1)
            return path

        monkeypatch.setattr(IllustrateScenes, "generate_image", staticmethod(fake_generate_image))
        role = make_test_role(IllustrateScenes, name="illustrator")
        with MockScript.from_values(Value.from_model(SketchSpec(prompt="dawn"), name="sketch 1")):
            await role.illustrate_novel_phase(ctx, persist_dir=tmp_path)
        assert seen == [[LoraSpec(lora_name="style.safetensors", strength=0.5)]]
        assert prompts == ["dawn, xstyle"]

    async def test_illustrate_novel_phase_chooses_loras_from_catalog(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert selectable catalog loras resolve per scene and their trigger words augment."""
        monkeypatch.setattr(
            "fabricatio_novel.capabilities.illustration.novel_config",
            novel_config_with(),
        )
        catalog = LoraCatalog(
            entries=[
                LoraEntry(
                    lora_name="pose.safetensors", strength=0.65, effect="poses the subject", trigger_words="xpose"
                )
            ]
        )
        monkeypatch.setattr(LoraCatalog, "from_config", classmethod(lambda cls: catalog))
        seen: list[object] = []
        prompts: list[str] = []

        async def fake_generate_image(prompt: str, download_dir: str | Path | None = None, **kwargs: object) -> Path:
            seen.append(kwargs["loras"])
            prompts.append(prompt)
            assert download_dir is not None
            target = Path(download_dir)
            target.mkdir(parents=True, exist_ok=True)
            path = target / "img.png"
            path.write_bytes(_PNG_1X1)
            return path

        monkeypatch.setattr(IllustrateScenes, "generate_image", staticmethod(fake_generate_image))
        role = make_test_role(IllustrateScenes, name="illustrator")
        with MockScript.from_values(
            Value.from_model(SketchSpec(prompt="dawn"), name="sketch 1"),
            Value.from_model(LoraSelection(picks=[LoraPick(lora_name="pose.safetensors")]), name="lora selection"),
        ):
            await role.illustrate_novel_phase(
                build_novel_ctx("S1"), persist_dir=tmp_path, illustration_choose_loras=True
            )
        assert seen == [[LoraSpec(lora_name="pose.safetensors", strength=0.65)]]
        assert prompts == ["dawn, xpose"]

    async def test_illustrate_novel_phase_chains_always_and_selected_loras(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert picked loras chain after the always loras; both contribute trigger words."""
        monkeypatch.setattr(
            "fabricatio_novel.capabilities.illustration.novel_config",
            novel_config_with(
                illustration_always_loras=[
                    LoraEntry(
                        lora_name="style.safetensors", strength=0.8, effect="style anchor", trigger_words="xstyle"
                    )
                ]
            ),
        )
        catalog = LoraCatalog(
            entries=[
                LoraEntry(
                    lora_name="pose.safetensors", strength=0.65, effect="poses the subject", trigger_words="xpose"
                )
            ]
        )
        monkeypatch.setattr(LoraCatalog, "from_config", classmethod(lambda cls: catalog))
        seen: list[object] = []
        prompts: list[str] = []

        async def fake_generate_image(prompt: str, download_dir: str | Path | None = None, **kwargs: object) -> Path:
            seen.append(kwargs["loras"])
            prompts.append(prompt)
            assert download_dir is not None
            target = Path(download_dir)
            target.mkdir(parents=True, exist_ok=True)
            path = target / "img.png"
            path.write_bytes(_PNG_1X1)
            return path

        monkeypatch.setattr(IllustrateScenes, "generate_image", staticmethod(fake_generate_image))
        role = make_test_role(IllustrateScenes, name="illustrator")
        role.illustration_choose_loras = True
        with MockScript.from_values(
            Value.from_model(SketchSpec(prompt="dawn"), name="sketch 1"),
            Value.from_model(LoraSelection(picks=[LoraPick(lora_name="pose.safetensors")]), name="lora selection"),
        ):
            await role.illustrate_novel_phase(build_novel_ctx("S1"), persist_dir=tmp_path)
        assert seen == [
            [
                LoraSpec(lora_name="style.safetensors", strength=0.8),
                LoraSpec(lora_name="pose.safetensors", strength=0.65),
            ]
        ]
        assert prompts == ["dawn, xstyle, xpose"]

    async def test_illustrate_novel_phase_appends_configured_prompt_suffix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert the configured suffix closes every render prompt after the lora chain."""
        monkeypatch.setattr(
            "fabricatio_novel.capabilities.illustration.novel_config",
            novel_config_with(illustration_prompt_suffix="very detailed"),
        )
        prompts = install_fake_renderer(monkeypatch, [tmp_path / "unused.png"])
        role = make_test_role(IllustrateScenes, name="illustrator")
        with MockScript.from_values(Value.from_model(SketchSpec(prompt="dawn"), name="sketch 1")):
            illustrations = await role.illustrate_novel_phase(build_novel_ctx("S1"), persist_dir=tmp_path)
        assert prompts == ["dawn,very detailed"]
        target = tmp_path / "images" / "scene_01_01.png"
        assert illustrations[(1, 1)] == ("dawn,very detailed", str(target.resolve()))

    def test_illustration_prompt_suffix_defaults_to_quality_tags(self) -> None:
        """Assert the stock suffix is the classic SD quality-tag string."""
        assert NovelConfig.model_validate({}).illustration_prompt_suffix == "best quality,masterpiece,4k,highres"

    async def test_illustrate_novel_phase_skips_judge_by_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert the gate keeps visual judgement (and its vision call) fully off unless opted in."""
        monkeypatch.setattr(
            "fabricatio_novel.capabilities.illustration.novel_config",
            novel_config_with(illustration_judge=False),
        )

        def _forbidden(*_args: object, **_kwargs: object) -> ImageVerdict:
            raise AssertionError("visually_judge must not run when the judge gate is off")

        monkeypatch.setattr(IllustrateScenes, "visually_judge", staticmethod(_forbidden))
        prompts, _pngs = install_distinct_renderer(monkeypatch)
        role = make_test_role(IllustrateScenes, name="illustrator")
        with MockScript.from_values(Value.from_model(SketchSpec(prompt="dawn"), name="sketch 1")):
            illustrations = await role.illustrate_novel_phase(build_novel_ctx("S1"), persist_dir=tmp_path)
        target = tmp_path / "images" / "scene_01_01.png"
        assert prompts == ["dawn"]
        assert illustrations[(1, 1)] == ("dawn", str(target.resolve()))
        assert target.is_file()
        assert not list((tmp_path / "images").glob("*.attempt*"))

    async def test_illustrate_novel_phase_judge_accepts_first_pass(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert a passing first verdict keeps the single render with no archived attempts."""
        monkeypatch.setattr(
            "fabricatio_novel.capabilities.illustration.novel_config",
            novel_config_with(),
        )
        prompts, pngs = install_distinct_renderer(monkeypatch)
        role = make_test_role(IllustrateScenes, name="illustrator")
        role.illustration_judge = True
        verdict = ImageVerdict(issue_to_judge="x", deny_evidence=[], affirm_evidence=["clean"], final_judgement=True)
        with MockScript.from_values(
            Value.from_model(SketchSpec(prompt="dawn"), name="sketch 1"),
            Value.from_model(verdict, name="verdict"),
        ):
            illustrations = await role.illustrate_novel_phase(build_novel_ctx("S1"), persist_dir=tmp_path)
        target = tmp_path / "images" / "scene_01_01.png"
        assert prompts == ["dawn"]
        assert illustrations[(1, 1)] == ("dawn", str(target.resolve()))
        assert target.read_bytes() == pngs[0]
        assert not list((tmp_path / "images").glob("*.attempt*"))

    async def test_illustrate_novel_phase_judge_retries_with_feedback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert a failed verdict archives the attempt, re-proposes with feedback, and re-renders."""
        monkeypatch.setattr(
            "fabricatio_novel.capabilities.illustration.novel_config",
            novel_config_with(),
        )
        prompts, pngs = install_distinct_renderer(monkeypatch)
        role = make_test_role(IllustrateScenes, name="illustrator")
        fail = ImageVerdict(
            issue_to_judge="x",
            deny_evidence=["mangled hands"],
            affirm_evidence=[],
            final_judgement=False,
            glitch_reasons=["broken hands"],
        )
        revised = ImageVerdict(issue_to_judge="x", deny_evidence=[], affirm_evidence=["fixed"], final_judgement=True)
        with MockScript.from_values(
            Value.from_model(SketchSpec(prompt="dawn"), name="sketch 1"),
            Value.from_model(fail, name="failed verdict"),
            Value.from_model(SketchSpec(prompt="dawn, fixed hands"), name="sketch 2"),
            Value.from_model(revised, name="passing verdict"),
        ):
            illustrations = await role.illustrate_novel_phase(
                build_novel_ctx("S1"), persist_dir=tmp_path, illustration_judge=True, illustration_judge_max_tries=3
            )
        target = tmp_path / "images" / "scene_01_01.png"
        attempt = tmp_path / "images" / "scene_01_01.attempt1.png"
        assert prompts == ["dawn", "dawn, fixed hands"]
        assert attempt.is_file()
        assert attempt.read_bytes() == pngs[0]
        assert target.read_bytes() == pngs[1]
        assert illustrations[(1, 1)] == ("dawn, fixed hands", str(target.resolve()))

    async def test_illustrate_novel_phase_judge_keeps_last_after_exhaustion(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert the try budget's final render is kept unjudged when every verdict fails."""
        monkeypatch.setattr(
            "fabricatio_novel.capabilities.illustration.novel_config",
            novel_config_with(),
        )
        prompts, pngs = install_distinct_renderer(monkeypatch)
        role = make_test_role(IllustrateScenes, name="illustrator")
        fail = ImageVerdict(
            issue_to_judge="x",
            deny_evidence=[],
            affirm_evidence=[],
            final_judgement=False,
            coherence_reasons=["wrong hair color"],
        )
        with MockScript.from_values(
            Value.from_model(SketchSpec(prompt="v1"), name="sketch 1"),
            Value.from_model(fail, name="failed verdict"),
            Value.from_model(SketchSpec(prompt="v2"), name="sketch 2"),
        ):
            illustrations = await role.illustrate_novel_phase(
                build_novel_ctx("S1"), persist_dir=tmp_path, illustration_judge=True, illustration_judge_max_tries=2
            )
        target = tmp_path / "images" / "scene_01_01.png"
        assert prompts == ["v1", "v2"]
        assert (tmp_path / "images" / "scene_01_01.attempt1.png").read_bytes() == pngs[0]
        assert target.read_bytes() == pngs[1]
        assert illustrations[(1, 1)][0] == "v2"

    async def test_illustrate_novel_phase_judge_accepts_when_verdict_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert an unavailable judge (``None`` verdict) degrades open: image kept, no retry."""
        monkeypatch.setattr(
            "fabricatio_novel.capabilities.illustration.novel_config",
            novel_config_with(),
        )

        async def _none_verdict(*_args: object, **_kwargs: object) -> None:
            return None

        monkeypatch.setattr(IllustrateScenes, "visually_judge", staticmethod(_none_verdict))
        prompts, pngs = install_distinct_renderer(monkeypatch)
        role = make_test_role(IllustrateScenes, name="illustrator")
        with MockScript.from_values(Value.from_model(SketchSpec(prompt="dawn"), name="sketch 1")):
            illustrations = await role.illustrate_novel_phase(
                build_novel_ctx("S1"), persist_dir=tmp_path, illustration_judge=True
            )
        target = tmp_path / "images" / "scene_01_01.png"
        assert prompts == ["dawn"]
        assert illustrations[(1, 1)] == ("dawn", str(target.resolve()))
        assert target.read_bytes() == pngs[0]
        assert not list((tmp_path / "images").glob("*.attempt*"))


class TestAttachIllustrations:
    """Test suite for attaching rendered illustrations onto the assembled novel."""

    def test_attach_swaps_only_illustrated_scenes(self, tmp_path: Path) -> None:
        """Assert keyed scenes become IllustratedScene outputs and the rest stay plain."""
        role = make_test_role(IllustrateScenes, name="illustrator")
        ctx = build_novel_ctx("S1", "S2")
        ctx.child_contexts[0].child_contexts[0].child_contexts[0].content = "He left."

        novel = role.attach_illustrations(
            ctx, Novel.from_context(ctx), {(1, 1): ("a lone rider at dawn", str(tmp_path / "img.png"))}
        )
        out_scenes = novel.chapter[0].story[0].scenes
        assert isinstance(out_scenes[0], IllustratedScene)
        assert out_scenes[0].illustration_prompt == "a lone rider at dawn"
        assert out_scenes[0].illustration_image == str(tmp_path / "img.png")
        assert out_scenes[0].content == "He left."


class TestPostProcessNovelHook:
    """Test suite for the ``post_process_novel`` integration point."""

    async def test_post_process_novel_is_identity_without_persist_dir(self, tmp_path: Path) -> None:
        """Assert the hook returns the novel untouched when no ``persist_dir`` is passed."""
        role = make_test_role(IllustrateScenes, name="illustrator")
        ctx = build_novel_ctx("S1", "S2")
        novel = Novel.from_context(ctx)

        out = await role.post_process_novel(ctx, novel)

        assert out is novel
        assert not (tmp_path / "images").exists()
        assert type(out.chapter[0].story[0].scenes[0]) is Scene

    async def test_post_process_novel_renders_and_attaches(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert the hook runs the phase and attaches every rendered scene to the novel."""
        monkeypatch.setattr(
            "fabricatio_novel.capabilities.illustration.novel_config",
            novel_config_with(),
        )
        ctx = build_novel_ctx("S1", "S2")
        prompts = install_fake_renderer(monkeypatch, [tmp_path / "unused.png"] * 2)
        role = make_test_role(IllustrateScenes, name="illustrator")
        proposals = [
            SketchSpec(prompt="a lone rider at dawn"),
            SketchSpec(prompt="a stranger at the gate"),
        ]
        novel = Novel.from_context(ctx)
        with MockScript.from_values(
            *(Value.from_model(p, name=f"sketch {i}") for i, p in enumerate(proposals, start=1))
        ):
            out = await role.post_process_novel(ctx, novel, persist_dir=tmp_path)

        assert prompts == ["a lone rider at dawn", "a stranger at the gate"]
        out_scenes = out.chapter[0].story[0].scenes
        assert isinstance(out_scenes[0], IllustratedScene)
        assert out_scenes[0].illustration_prompt == "a lone rider at dawn"
        assert out_scenes[1].illustration_prompt == "a stranger at the gate"
        assert (tmp_path / "images" / "scene_01_01.png").is_file()
        assert (tmp_path / "images" / "scene_01_02.png").is_file()


class TestSceneIllustrationQueue:
    """Test suite for the compiled pending-illustration queue."""

    def test_from_context_collects_scenes_with_keys_targets_and_titles(self, tmp_path: Path) -> None:
        """Assert every scene is queued in walk order with its key, title, and render target."""
        queue = SceneIllustrationQueue.from_context(build_novel_ctx("S1", "S2"), persist_dir=tmp_path, constraint="")

        assert queue.images_dir == tmp_path / "images"
        assert queue.images_dir.is_dir()
        assert [entry.key for entry in queue.entries] == [(1, 1), (1, 2)]
        assert [entry.scene_title for entry in queue.entries] == ["S1", "S2"]
        assert [entry.target for entry in queue.entries] == [
            tmp_path / "images" / "scene_01_01.png",
            tmp_path / "images" / "scene_01_02.png",
        ]
        assert all(isinstance(entry, PendingIllustration) for entry in queue.entries)

    def test_from_context_numbers_scenes_across_stories(self, tmp_path: Path) -> None:
        """Assert scene keys keep increasing across stories, matching the EPUB naming."""
        queue = SceneIllustrationQueue.from_context(build_two_story_novel_ctx(), persist_dir=tmp_path, constraint="")
        assert [entry.key for entry in queue.entries] == [(1, 1), (1, 2), (1, 3)]

    def test_from_context_skips_existing_png_when_enabled(self, tmp_path: Path) -> None:
        """Assert scenes whose PNG exists drop out of the queue while skip-existing is on (default)."""
        images_dir = tmp_path / "images"
        images_dir.mkdir()
        (images_dir / "scene_01_01.png").write_bytes(_PNG_1X1)
        queue = SceneIllustrationQueue.from_context(build_novel_ctx("S1", "S2"), persist_dir=tmp_path, constraint="")
        assert [entry.key for entry in queue.entries] == [(1, 2)]

    def test_from_context_keeps_existing_png_when_skip_disabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert illustration_skip_existing=False queues scenes whose PNG already exists."""
        monkeypatch.setattr(
            "fabricatio_novel.models.illustration_queue.novel_config",
            novel_config_with(illustration_skip_existing=False),
        )
        images_dir = tmp_path / "images"
        images_dir.mkdir()
        (images_dir / "scene_01_01.png").write_bytes(_PNG_1X1)
        queue = SceneIllustrationQueue.from_context(build_novel_ctx("S1", "S2"), persist_dir=tmp_path, constraint="")
        assert [entry.key for entry in queue.entries] == [(1, 1), (1, 2)]

    def test_from_context_renders_requirement_from_template_vars(self, tmp_path: Path) -> None:
        """Assert the requirement renders the shared template with the scene variables."""
        queue = SceneIllustrationQueue.from_context(
            build_novel_ctx("S1"), persist_dir=tmp_path, constraint="watercolor, muted palette"
        )
        requirement = queue.entries[0].requirement
        assert "Title: S1" in requirement
        assert "Description: S1 description." in requirement
        assert "Ch1" in requirement
        assert "St1" in requirement
        assert "watercolor, muted palette" in requirement

    def test_from_context_omits_empty_sections_from_requirement(self, tmp_path: Path) -> None:
        """Assert guarded variables (constraint, novel title) leave their sections out when empty."""
        queue = SceneIllustrationQueue.from_context(build_novel_ctx("S1"), persist_dir=tmp_path, constraint="")
        requirement = queue.entries[0].requirement
        assert "## Style Constraints" not in requirement
        assert "## Novel" not in requirement
