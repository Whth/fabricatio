"""Post-process ComfyUI illustration tests for fabricatio-novel."""

import asyncio
import base64
from pathlib import Path

import pytest
from _support import IllustrationRole
from fabricatio_comfyui.models import LoraCatalog, LoraEntry, LoraPick, LoraSelection, LoraSpec
from fabricatio_comfyui.models.resolution import Prop
from fabricatio_comfyui.models.specs import SketchSpec
from fabricatio_mock.models.mock_router import Value, return_mixed_router_usage
from fabricatio_mock.utils import install_router_usage
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
        story_ctx.scene_context.append(
            SceneContext(title=title, description=f"{title} description.", expected_word_count=20)
        )
    chapter_ctx.story_context.append(story_ctx)
    ctx.chapter_context.append(chapter_ctx)
    return ctx


def build_two_story_novel_ctx() -> NovelContext:
    """Build a one-chapter novel context holding two stories with one, two, and zero scenes split across them."""
    ctx = NovelContext.create("The hero seeks his father.", language="English")
    chapter_ctx = ChapterContext(title="Ch1", description="The hero sets out.")
    for story_title, scene_titles in (("St1", ("S1",)), ("St2", ("S2", "S3"))):
        story_ctx = StoryContext(title=story_title, description=f"The {story_title} leg.")
        for title in scene_titles:
            story_ctx.scene_context.append(
                SceneContext(title=title, description=f"{title} description.", expected_word_count=20)
            )
        chapter_ctx.story_context.append(story_ctx)
    ctx.chapter_context.append(chapter_ctx)
    return ctx


def novel_config_with(**overrides: object) -> NovelConfig:
    """Return a NovelConfig clone carrying the given field overrides.

    The TOML-declared always-on lora chain is stripped unless the caller
    overrides ``illustration_always_loras`` explicitly, keeping prompt
    assertions independent of local config drift.
    """
    base = {**novel_config.model_dump(), "illustration_always_loras": []}
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


class TestIllustrateNovelPhase:
    """Test suite for the post-process illustration phase."""

    async def test_illustrate_novel_phase_records_prompt_and_image_per_scene(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert every scene gets its proposed prompt recorded and its PNG copied to the canonical name."""
        ctx = build_novel_ctx("S1", "S2")
        prompts = install_fake_renderer(monkeypatch, [tmp_path / "unused.png"] * 2)
        role = IllustrationRole(name="illustrator")
        proposals = [
            SketchSpec(prompt="a lone rider at dawn", negative_prompt="text, watermark"),
            SketchSpec(prompt="a stranger at the gate"),
        ]
        with install_router_usage(*return_mixed_router_usage(*(Value(p, "model") for p in proposals))):
            illustrations = await role.illustrate_novel_phase(ctx, persist_dir=tmp_path)

        assert set(illustrations) == {(1, 1), (1, 2)}
        assert set(prompts) == {"a lone rider at dawn", "a stranger at the gate"}
        assert {prompt for prompt, _ in illustrations.values()} == {"a lone rider at dawn", "a stranger at the gate"}
        assert illustrations[(1, 1)][1] == str((tmp_path / "images" / "scene_01_01.png").resolve())
        assert illustrations[(1, 2)][1] == str((tmp_path / "images" / "scene_01_02.png").resolve())
        assert (tmp_path / "images" / "scene_01_01.png").is_file()
        assert (tmp_path / "images" / "scene_01_02.png").is_file()

    async def test_illustrate_novel_phase_skips_existing_png(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert scenes whose illustration PNG already exists are skipped and only the rest get proposed."""
        ctx = build_novel_ctx("S1", "S2")
        images_dir = tmp_path / "images"
        images_dir.mkdir()
        (images_dir / "scene_01_01.png").write_bytes(_PNG_1X1)
        prompts = install_fake_renderer(monkeypatch, [tmp_path / "unused.png"])
        role = IllustrationRole(name="illustrator")
        proposal = SketchSpec(prompt="a stranger at the gate")
        with install_router_usage(*return_mixed_router_usage(Value(proposal, "model"))):
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
        (images_dir / "scene_01_01.png").write_bytes(_PNG_1X1)
        prompts = install_fake_renderer(monkeypatch, [tmp_path / "unused.png"] * 2)
        role = IllustrationRole(name="illustrator")
        proposals = [SketchSpec(prompt="redrawn dawn"), SketchSpec(prompt="redrawn gate")]
        with install_router_usage(*return_mixed_router_usage(*(Value(p, "model") for p in proposals))):
            illustrations = await role.illustrate_novel_phase(ctx, persist_dir=tmp_path)

        assert set(illustrations) == {(1, 1), (1, 2)}
        assert set(prompts) == {"redrawn dawn", "redrawn gate"}

    async def test_illustrate_novel_phase_degrades_when_generation_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert a None render and a raised render each skip the scene without failing the phase."""
        ctx = build_novel_ctx("S1", "S2")
        prompts = install_fake_renderer(monkeypatch, [None, RuntimeError("comfyui down")])
        role = IllustrationRole(name="illustrator")
        proposals = [
            SketchSpec(prompt="a lone rider at dawn"),
            SketchSpec(prompt="a stranger at the gate"),
        ]
        with install_router_usage(*return_mixed_router_usage(*(Value(p, "model") for p in proposals))):
            illustrations = await role.illustrate_novel_phase(ctx, persist_dir=tmp_path)

        assert illustrations == {}
        assert len(prompts) == 2
        assert not (tmp_path / "images" / "scene_01_01.png").exists()
        assert not (tmp_path / "images" / "scene_01_02.png").exists()

    async def test_illustrate_novel_phase_skips_proposal_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert a failed proposal skips only that scene and the next scene still illustrates."""
        ctx = build_novel_ctx("S1", "S2")
        prompts = install_fake_renderer(monkeypatch, [tmp_path / "unused.png"])
        role = IllustrationRole(name="illustrator")
        proposal = SketchSpec(prompt="a stranger at the gate")

        async def fake_propose(model: object, requirement: str, **kwargs: object) -> SketchSpec | None:
            # Key the failure to the S1 requirement so the outcome is deterministic under batching.
            return None if "Title: S1" in requirement else proposal

        monkeypatch.setattr(IllustrationRole, "propose", staticmethod(fake_propose))
        illustrations = await role.illustrate_novel_phase(ctx, persist_dir=tmp_path)

        assert set(illustrations) == {(1, 2)}
        assert prompts == ["a stranger at the gate"]

    async def test_illustrate_novel_phase_numbers_scenes_across_stories(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert scene indices keep increasing across stories so names match the EPUB exporter."""
        ctx = build_two_story_novel_ctx()
        prompts = install_fake_renderer(monkeypatch, [tmp_path / "unused.png"] * 3)
        role = IllustrationRole(name="illustrator")
        proposals = [SketchSpec(prompt=f"scene {i}") for i in range(1, 4)]
        with install_router_usage(*return_mixed_router_usage(*(Value(p, "model") for p in proposals))):
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
        role = IllustrationRole(name="illustrator")
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
        role = IllustrationRole(name="illustrator")
        proposals = [SketchSpec(prompt=f"dawn {i}") for i in range(3)]
        with install_router_usage(*return_mixed_router_usage(*(Value(p, "model") for p in proposals))):
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
        role = IllustrationRole(name="illustrator")
        proposals = [SketchSpec(prompt="dawn"), SketchSpec(prompt="dusk")]
        with install_router_usage(*return_mixed_router_usage(*(Value(p, "model") for p in proposals))):
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

        scoped_role = IllustrationRole(name="scoped", illustration_constraint="scoped ink style")
        await scoped_role.illustrate_novel_phase(build_novel_ctx("S1"), persist_dir=tmp_path / "scoped")
        assert all("## Style Constraints" in req and "scoped ink style" in req for req in requirements)

        explicit_role = IllustrationRole(name="explicit", illustration_constraint="scoped ink style")
        await explicit_role.illustrate_novel_phase(
            build_novel_ctx("S1"), persist_dir=tmp_path / "explicit", illustration_constraint="explicit oil"
        )
        assert all("explicit oil" in req and "scoped ink style" not in req for req in requirements[1:])

        plain_role = IllustrationRole(name="plain")
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
        role = IllustrationRole(name="illustrator")
        proposals = [
            SketchSpec(prompt="wide dawn", prop=Prop.prop_16_9, mp=1.0),
            SketchSpec(prompt="tall gate"),  # no size: falls back to the global illustration_mp/prop
        ]
        with install_router_usage(*return_mixed_router_usage(*(Value(p, "model") for p in proposals))):
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
        role = IllustrationRole(name="illustrator")
        proposals = [
            SketchSpec(prompt="over budget", mp=6.0),
            SketchSpec(prompt="within budget", mp=0.8),
        ]
        with install_router_usage(*return_mixed_router_usage(*(Value(p, "model") for p in proposals))):
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
        role = IllustrationRole(name="illustrator")
        proposals = [
            SketchSpec(prompt="way over", mp=6.0),
            SketchSpec(prompt="just under", mp=0.4),
        ]
        with install_router_usage(*return_mixed_router_usage(*(Value(p, "model") for p in proposals))):
            illustrations = await role.illustrate_novel_phase(ctx, persist_dir=tmp_path)

        assert set(illustrations) == {(1, 1), (1, 2)}
        assert seen == [0.5, 0.4]

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
        role = IllustrationRole(name="illustrator")
        with install_router_usage(*return_mixed_router_usage(Value(SketchSpec(prompt="dawn"), "model"))):
            await role.illustrate_novel_phase(ctx, persist_dir=tmp_path)
        assert seen == [[LoraSpec(lora_name="style.safetensors", strength=0.5)]]
        assert prompts == ["dawn, xstyle"]

    async def test_illustrate_novel_phase_chooses_loras_from_catalog(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert selectable catalog loras resolve per scene and their trigger words augment."""
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
        role = IllustrationRole(name="illustrator")
        with install_router_usage(
            *return_mixed_router_usage(
                Value(SketchSpec(prompt="dawn"), "model"),
                Value(LoraSelection(picks=[LoraPick(lora_name="pose.safetensors")]), "model"),
            )
        ):
            await role.illustrate_novel_phase(build_novel_ctx("S1"), persist_dir=tmp_path)
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
        role = IllustrationRole(name="illustrator")
        with install_router_usage(
            *return_mixed_router_usage(
                Value(SketchSpec(prompt="dawn"), "model"),
                Value(LoraSelection(picks=[LoraPick(lora_name="pose.safetensors")]), "model"),
            )
        ):
            await role.illustrate_novel_phase(build_novel_ctx("S1"), persist_dir=tmp_path)
        assert seen == [
            [
                LoraSpec(lora_name="style.safetensors", strength=0.8),
                LoraSpec(lora_name="pose.safetensors", strength=0.65),
            ]
        ]
        assert prompts == ["dawn, xstyle, xpose"]


class TestAttachIllustrations:
    """Test suite for attaching rendered illustrations onto the assembled novel."""

    def test_attach_swaps_only_illustrated_scenes(self, tmp_path: Path) -> None:
        """Assert keyed scenes become IllustratedScene outputs and the rest stay plain."""
        role = IllustrationRole(name="illustrator")
        ctx = build_novel_ctx("S1", "S2")
        ctx.chapter_context[0].story_context[0].scene_context[0].content = "He left."

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
        role = IllustrationRole(name="illustrator")
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
        ctx = build_novel_ctx("S1", "S2")
        prompts = install_fake_renderer(monkeypatch, [tmp_path / "unused.png"] * 2)
        role = IllustrationRole(name="illustrator")
        proposals = [
            SketchSpec(prompt="a lone rider at dawn"),
            SketchSpec(prompt="a stranger at the gate"),
        ]
        novel = Novel.from_context(ctx)
        with install_router_usage(*return_mixed_router_usage(*(Value(p, "model") for p in proposals))):
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
