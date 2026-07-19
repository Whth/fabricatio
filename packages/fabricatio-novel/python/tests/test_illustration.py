"""Tests for the illustration pipeline models and helpers."""

import pytest
from fabricatio_comfyui.models.workflow import Workflow
from fabricatio_novel.capabilities.illustration import _apply_constrain_to_workflow
from fabricatio_novel.models.illustration import FrameAspect, IllustrationConstrain

# ---------------------------------------------------------------------------
# FrameAspect enum
# ---------------------------------------------------------------------------


class TestFrameAspect:
    """Tests for the FrameAspect StrEnum — values must match ComfyUI tokens."""

    def test_all_values_verbatim(self) -> None:
        """Each FrameAspect value is the exact ComfyUI ResolutionSelector token."""
        assert FrameAspect.SQUARE.value == "square"
        assert FrameAspect.PHOTO.value == "photo"
        assert FrameAspect.PORTRAIT_PHOTO.value == "portrait photo"
        assert FrameAspect.PORTRAIT_STANDARD.value == "portrait standard"
        assert FrameAspect.STANDARD.value == "standard"
        assert FrameAspect.WIDESCREEN_PORTRAIT.value == "widescreen portrait"
        assert FrameAspect.WIDESCREEN.value == "widescreen"
        assert FrameAspect.ULTRAWIDE.value == "ultrawide"

    def test_ratio_method(self) -> None:
        """Each FrameAspect exposes a numeric (w, h) ratio for the literal-dimension fallback."""
        assert FrameAspect.SQUARE.ratio == (1, 1)
        assert FrameAspect.PHOTO.ratio == (3, 2)
        assert FrameAspect.PORTRAIT_PHOTO.ratio == (2, 3)
        assert FrameAspect.PORTRAIT_STANDARD.ratio == (3, 4)
        assert FrameAspect.STANDARD.ratio == (5, 4)
        assert FrameAspect.WIDESCREEN_PORTRAIT.ratio == (9, 16)
        assert FrameAspect.WIDESCREEN.ratio == (16, 9)
        assert FrameAspect.ULTRAWIDE.ratio == (21, 9)

    def test_member_count(self) -> None:
        """Exactly 8 ComfyUI tokens exposed."""
        assert len(FrameAspect) == 8


# ---------------------------------------------------------------------------
# IllustrationConstrain model
# ---------------------------------------------------------------------------


class TestIllustrationConstrain:
    """Tests for the typed IllustrationConstrain Pydantic model."""

    def test_construction(self) -> None:
        """Constrain stores aspect_ratio, megapixels, and prompt verbatim."""
        c = IllustrationConstrain(
            aspect_ratio=FrameAspect.PORTRAIT_STANDARD,
            megapixels=1.7,
            prompt="best quality, 1girl, silver hair",
        )
        assert c.aspect_ratio is FrameAspect.PORTRAIT_STANDARD
        assert c.megapixels == 1.7
        assert c.prompt == "best quality, 1girl, silver hair"

    def test_default_megapixels(self) -> None:
        """Megapixels defaults to 1.0 when omitted."""
        c = IllustrationConstrain(aspect_ratio=FrameAspect.SQUARE, prompt="x")
        assert c.megapixels == 1.0

    def test_megapixels_must_be_non_negative(self) -> None:
        """Negative megapixels are rejected by pydantic."""
        with pytest.raises(ValueError):
            IllustrationConstrain(aspect_ratio=FrameAspect.SQUARE, megapixels=-0.5, prompt="x")

    def test_json_dump_uses_enum_value(self) -> None:
        """model_dump_json writes the enum's .value string (not the member name)."""
        c = IllustrationConstrain(aspect_ratio=FrameAspect.WIDESCREEN_PORTRAIT, megapixels=2.0, prompt="p")
        dumped = c.model_dump_json()
        assert '"aspect_ratio":"widescreen portrait"' in dumped
        assert "WIDESCREEN_PORTRAIT" not in dumped  # not the python name

    def test_json_schema_includes_enum_tokens(self) -> None:
        """The JSON schema (used to drive LLM proposals) lists all 8 enum values."""
        schema = IllustrationConstrain.model_json_schema()
        enum_def = schema["$defs"]["FrameAspect"]
        assert set(enum_def["enum"]) == {e.value for e in FrameAspect}


# ---------------------------------------------------------------------------
# FrameAspect.to_dimensions
# ---------------------------------------------------------------------------


class TestFrameAspectDimensions:
    """Tests for enum-owned literal pixel dimension calculation."""

    def test_widescreen_one_megapixel(self) -> None:
        """1.0 MP at widescreen produces aligned dimensions near 1332x748."""
        w, h = FrameAspect.WIDESCREEN.to_dimensions(1.0)
        assert w % 8 == 0
        assert h % 8 == 0
        assert 1328 <= w <= 1340
        assert 744 <= h <= 752

    def test_square_two_megapixel(self) -> None:
        """2.0 MP at square produces equal, aligned dimensions near 1416px."""
        w, h = FrameAspect.SQUARE.to_dimensions(2.0)
        assert w == h
        assert w % 8 == 0
        assert 1412 <= w <= 1420

    def test_minimum_dim_floor(self) -> None:
        """Very small megapixel targets still produce at least 64x64."""
        w, h = FrameAspect.SQUARE.to_dimensions(0.001)
        assert w >= 64
        assert h >= 64


# ---------------------------------------------------------------------------
# _apply_constrain_to_workflow
# ---------------------------------------------------------------------------


def _wf_with_resolution_selector() -> Workflow:
    """A workflow with ResolutionSelector + EmptyLatentImage + CLIPTextEncode."""
    wf = Workflow.new()
    wf.add("CLIPTextEncode", inputs={"text": "old positive", "clip": ["fake", 1]})
    wf.add(
        "ResolutionSelector",
        inputs={"aspect_ratio": "widescreen", "megapixels": 1.0},
    )
    wf.add(
        "EmptyLatentImage",
        inputs={"width": ["2", 0], "height": ["2", 1], "batch_size": 1},
    )
    return wf


def _wf_with_empty_latent_only() -> Workflow:
    """A workflow with only CLIPTextEncode + EmptyLatentImage (no ResolutionSelector)."""
    wf = Workflow.new()
    wf.add("CLIPTextEncode", inputs={"text": "old positive", "clip": ["fake", 1]})
    wf.add("EmptyLatentImage", inputs={"width": 512, "height": 512, "batch_size": 1})
    return wf


class TestApplyConstrainToWorkflow:
    """Tests for the helper that drives a workflow from a Constrain."""

    def test_resolution_selector_path(self) -> None:
        """Constrain values land on the ResolutionSelector and CLIPTextEncode."""
        wf = _wf_with_resolution_selector()
        constrain = IllustrationConstrain(
            aspect_ratio=FrameAspect.PORTRAIT_STANDARD, megapixels=1.7, prompt="best quality"
        )
        _apply_constrain_to_workflow(wf, constrain)
        selector = wf.by_type("ResolutionSelector")[0]
        assert selector.inputs["aspect_ratio"] == "portrait standard"
        assert selector.inputs["megapixels"] == 1.7
        clip = wf.by_type("CLIPTextEncode")[0]
        assert clip.inputs["text"] == "best quality"

    def test_fallback_path_no_resolution_selector(self) -> None:
        """Without a ResolutionSelector, the helper falls back to set_resolution."""
        wf = _wf_with_empty_latent_only()
        constrain = IllustrationConstrain(
            aspect_ratio=FrameAspect.PORTRAIT_STANDARD, megapixels=1.7, prompt="best quality"
        )
        _apply_constrain_to_workflow(wf, constrain)
        latent = wf.by_type("EmptyLatentImage")[0]
        # Literal dims derived from 3:4 ratio at 1.7MP, both multiples of 8
        w, h = latent.inputs["width"], latent.inputs["height"]
        assert isinstance(w, int)
        assert isinstance(h, int)
        assert w % 8 == 0
        assert h % 8 == 0
        # 3:4 ratio preserved (w/h == 0.75)
        assert abs(w / h - 0.75) < 0.01
        # Positive prompt still set on CLIPTextEncode
        clip = wf.by_type("CLIPTextEncode")[0]
        assert clip.inputs["text"] == "best quality"
