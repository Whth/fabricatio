"""Per-scene ComfyUI illustration tests for fabricatio-novel."""

import base64
import dataclasses
from pathlib import Path

import pytest
from _support import IllustrationRole
from fabricatio_mock.models.mock_router import Value, return_mixed_router_usage
from fabricatio_mock.utils import install_router_usage
from fabricatio_novel.capabilities.illustration import IllustrateScenes
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.illustration import IllustratedSceneContext
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.illustration import IllustratedScene, SceneIllustration
from fabricatio_novel.models.novel import Novel

_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def build_novel_ctx(*scene_titles: str, illustrated: bool = True) -> NovelContext:
    """Build a one-chapter novel context whose single story holds the given scenes."""
    ctx = NovelContext.create("The hero seeks his father.", language="English")
    chapter_ctx = ChapterContext(title="Ch1", description="The hero sets out.")
    story_ctx = StoryContext(title="St1", description="The departure.")
    for title in scene_titles:
        scene: SceneContext
        if illustrated:
            scene = IllustratedSceneContext(title=title, description=f"{title} description.", expected_word_count=20)
        else:
            scene = SceneContext(title=title, description=f"{title} description.", expected_word_count=20)
        story_ctx.scene_context.append(scene)
    chapter_ctx.story_context.append(story_ctx)
    ctx.chapter_context.append(chapter_ctx)
    return ctx


def install_fake_renderer(monkeypatch: pytest.MonkeyPatch, outcomes: list[Path | None | Exception]) -> list[str]:
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


class TestIllustrateScenes:
    """Test suite for the per-scene illustration phase."""

    async def test_illustrate_scenes_records_prompt_and_image_per_scene(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert every illustrated-channel scene gets its proposed prompt and rendered image."""
        ctx = build_novel_ctx("S1", "S2")
        prompts = install_fake_renderer(monkeypatch, [tmp_path / "unused.png"] * 2)
        role = IllustrationRole(name="illustrator")
        proposals = [
            SceneIllustration(prompt="a lone rider at dawn", negative_prompt="text, watermark"),
            SceneIllustration(prompt="a stranger at the gate"),
        ]
        with install_router_usage(*return_mixed_router_usage(*(Value(p, "model") for p in proposals))):
            count = await role.illustrate_scenes_phase(ctx, persist_dir=tmp_path)

        scenes = ctx.chapter_context[0].story_context[0].scene_context
        assert count == 2
        assert prompts == ["a lone rider at dawn", "a stranger at the gate"]
        assert isinstance(scenes[0], IllustratedSceneContext)
        assert scenes[0].illustration_prompt == "a lone rider at dawn"
        assert scenes[0].illustration_image == str((tmp_path / "images" / "img_1.png").resolve())
        assert Path(scenes[0].illustration_image).is_file()
        assert scenes[1].illustration_prompt == "a stranger at the gate"
        assert Path(scenes[1].illustration_image).is_file()

    async def test_illustrate_scenes_skips_plain_scene_contexts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert plain scene contexts are never illustrated: the channel is opt-in by tree type."""
        ctx = build_novel_ctx("S1", "S2", illustrated=False)
        prompts = install_fake_renderer(monkeypatch, [])
        role = IllustrationRole(name="illustrator")

        async def fail_propose(model: object, requirement: object, **kwargs: object) -> SceneIllustration | None:
            raise AssertionError("plain scene contexts must not reach the proposal call")

        monkeypatch.setattr(IllustrationRole, "propose", staticmethod(fail_propose))
        count = await role.illustrate_scenes_phase(ctx, persist_dir=tmp_path)

        assert count == 0
        assert prompts == []

    async def test_illustrate_scenes_skips_already_illustrated_scenes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert scenes carrying an image are skipped and only the rest get proposed."""
        ctx = build_novel_ctx("S1", "S2")
        scenes = ctx.chapter_context[0].story_context[0].scene_context
        assert isinstance(scenes[0], IllustratedSceneContext)
        scenes[0].set_illustration("kept prompt", str(tmp_path / "kept.png"))
        prompts = install_fake_renderer(monkeypatch, [tmp_path / "unused.png"])
        role = IllustrationRole(name="illustrator")
        proposal = SceneIllustration(prompt="a stranger at the gate")
        with install_router_usage(*return_mixed_router_usage(Value(proposal, "model"))):
            count = await role.illustrate_scenes_phase(ctx, persist_dir=tmp_path)

        assert count == 1
        assert prompts == ["a stranger at the gate"]
        assert scenes[0].illustration_prompt == "kept prompt"
        assert scenes[1].illustration_prompt == "a stranger at the gate"

    async def test_illustrate_scenes_regenerates_when_skip_existing_disabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert illustration_skip_existing=False re-illustrates scenes that already carry an image."""
        monkeypatch.setattr(
            "fabricatio_novel.capabilities.illustration.novel_config",
            dataclasses.replace(novel_config, illustration_skip_existing=False),
        )
        ctx = build_novel_ctx("S1", "S2")
        scenes = ctx.chapter_context[0].story_context[0].scene_context
        assert isinstance(scenes[0], IllustratedSceneContext)
        scenes[0].set_illustration("kept prompt", str(tmp_path / "kept.png"))
        prompts = install_fake_renderer(monkeypatch, [tmp_path / "unused.png"] * 2)
        role = IllustrationRole(name="illustrator")
        proposals = [SceneIllustration(prompt="redrawn dawn"), SceneIllustration(prompt="redrawn gate")]
        with install_router_usage(*return_mixed_router_usage(*(Value(p, "model") for p in proposals))):
            count = await role.illustrate_scenes_phase(ctx, persist_dir=tmp_path)

        assert count == 2
        assert prompts == ["redrawn dawn", "redrawn gate"]
        assert scenes[0].illustration_prompt == "redrawn dawn"

    async def test_illustrate_scenes_degrades_when_generation_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert a None render and a raised render each skip the scene without failing the phase."""
        ctx = build_novel_ctx("S1", "S2")
        prompts = install_fake_renderer(monkeypatch, [None, RuntimeError("comfyui down")])
        role = IllustrationRole(name="illustrator")
        proposals = [
            SceneIllustration(prompt="a lone rider at dawn"),
            SceneIllustration(prompt="a stranger at the gate"),
        ]
        with install_router_usage(*return_mixed_router_usage(*(Value(p, "model") for p in proposals))):
            count = await role.illustrate_scenes_phase(ctx, persist_dir=tmp_path)

        scenes = ctx.chapter_context[0].story_context[0].scene_context
        assert count == 0
        assert len(prompts) == 2
        assert isinstance(scenes[0], IllustratedSceneContext)
        assert scenes[0].illustration_image == ""
        assert scenes[1].illustration_image == ""

    async def test_illustrate_scenes_skips_proposal_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert a failed proposal skips only that scene and the next scene still illustrates."""
        ctx = build_novel_ctx("S1", "S2")
        prompts = install_fake_renderer(monkeypatch, [tmp_path / "unused.png"])
        role = IllustrationRole(name="illustrator")
        proposal = SceneIllustration(prompt="a stranger at the gate")
        propose_calls = [0, 1]

        async def fake_propose(model: object, requirement: object, **kwargs: object) -> SceneIllustration | None:
            return [None, proposal][propose_calls.pop(0)]

        monkeypatch.setattr(IllustrationRole, "propose", staticmethod(fake_propose))
        count = await role.illustrate_scenes_phase(ctx, persist_dir=tmp_path)

        scenes = ctx.chapter_context[0].story_context[0].scene_context
        assert count == 1
        assert prompts == ["a stranger at the gate"]
        assert isinstance(scenes[0], IllustratedSceneContext)
        assert scenes[0].illustration_image == ""
        assert scenes[1].illustration_prompt == "a stranger at the gate"


class TestMaterializeIllustrated:
    """Test suite for swapping illustrated outputs into the assembled novel."""

    def test_materialize_swaps_only_illustrated_scenes(self, tmp_path: Path) -> None:
        """Assert illustrated contexts become IllustratedScene outputs and plain scenes stay put."""
        role = IllustrationRole(name="illustrator")
        ctx = build_novel_ctx("S1", "S2", illustrated=False)
        scenes = ctx.chapter_context[0].story_context[0].scene_context
        scenes[0].content = "He left."
        illustrated = IllustratedSceneContext.model_validate(scenes[0].model_dump())
        illustrated.set_illustration("a lone rider at dawn", str(tmp_path / "img.png"))
        ctx.chapter_context[0].story_context[0].scene_context[0] = illustrated

        novel = role.materialize_illustrated(ctx, Novel.from_context(ctx))
        out_scenes = novel.chapter[0].story[0].scenes
        assert isinstance(out_scenes[0], IllustratedScene)
        assert out_scenes[0].illustration_prompt == "a lone rider at dawn"
        assert out_scenes[0].illustration_image == str(tmp_path / "img.png")
        assert out_scenes[0].content == "He left."
        assert type(out_scenes[1]) is not IllustratedScene
