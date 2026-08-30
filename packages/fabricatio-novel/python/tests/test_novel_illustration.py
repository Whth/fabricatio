"""Post-process ComfyUI illustration tests for fabricatio-novel."""

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
from fabricatio_novel.models.context.novel import NovelContext
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.illustration import IllustratedScene, SceneIllustration
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
            SceneIllustration(prompt="a lone rider at dawn", negative_prompt="text, watermark"),
            SceneIllustration(prompt="a stranger at the gate"),
        ]
        with install_router_usage(*return_mixed_router_usage(*(Value(p, "model") for p in proposals))):
            illustrations = await role.illustrate_novel_phase(ctx, persist_dir=tmp_path)

        assert set(illustrations) == {(1, 1), (1, 2)}
        assert prompts == ["a lone rider at dawn", "a stranger at the gate"]
        assert [prompt for prompt, _ in illustrations.values()] == ["a lone rider at dawn", "a stranger at the gate"]
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
        proposal = SceneIllustration(prompt="a stranger at the gate")
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
            "fabricatio_novel.capabilities.illustration.novel_config",
            dataclasses.replace(novel_config, illustration_skip_existing=False),
        )
        ctx = build_novel_ctx("S1", "S2")
        images_dir = tmp_path / "images"
        images_dir.mkdir()
        (images_dir / "scene_01_01.png").write_bytes(_PNG_1X1)
        prompts = install_fake_renderer(monkeypatch, [tmp_path / "unused.png"] * 2)
        role = IllustrationRole(name="illustrator")
        proposals = [SceneIllustration(prompt="redrawn dawn"), SceneIllustration(prompt="redrawn gate")]
        with install_router_usage(*return_mixed_router_usage(*(Value(p, "model") for p in proposals))):
            illustrations = await role.illustrate_novel_phase(ctx, persist_dir=tmp_path)

        assert set(illustrations) == {(1, 1), (1, 2)}
        assert prompts == ["redrawn dawn", "redrawn gate"]

    async def test_illustrate_novel_phase_degrades_when_generation_fails(
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
        proposal = SceneIllustration(prompt="a stranger at the gate")
        propose_calls = [0, 1]

        async def fake_propose(model: object, requirement: object, **kwargs: object) -> SceneIllustration | None:
            return [None, proposal][propose_calls.pop(0)]

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
        proposals = [SceneIllustration(prompt=f"scene {i}") for i in range(1, 4)]
        with install_router_usage(*return_mixed_router_usage(*(Value(p, "model") for p in proposals))):
            illustrations = await role.illustrate_novel_phase(ctx, persist_dir=tmp_path)

        assert set(illustrations) == {(1, 1), (1, 2), (1, 3)}
        assert (tmp_path / "images" / "scene_01_01.png").is_file()
        assert (tmp_path / "images" / "scene_01_02.png").is_file()
        assert (tmp_path / "images" / "scene_01_03.png").is_file()
        assert len(prompts) == 3


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
            SceneIllustration(prompt="a lone rider at dawn"),
            SceneIllustration(prompt="a stranger at the gate"),
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
