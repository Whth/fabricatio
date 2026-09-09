"""Tests for the fabricatio-comfyui subpackage."""

import asyncio
import threading
from pathlib import Path
from typing import cast
from unittest.mock import patch

import httpx
import pytest
from fabricatio_comfyui.capabilities.comfyui import UseComfyUI
from fabricatio_comfyui.capabilities.loras import ChooseLoras
from fabricatio_comfyui.config import comfyui_config
from fabricatio_comfyui.http_client import ComfyUIHttpClient, get_comfyui_client
from fabricatio_comfyui.models.anima import AnimaGraph
from fabricatio_comfyui.models.catalog import LoraCatalog, LoraEntry, LoraPick, LoraSelection
from fabricatio_comfyui.models.comfyui import (
    ExecutionResult,
    HistoryEntry,
    OutputImage,
    PromptResponse,
    QueueInfo,
    UploadResponse,
)


def replace(obj: object, **updates: object) -> object:
    """Pydantic stand-in for ``dataclasses.replace`` — frozen copy with field overrides."""
    return obj.model_copy(update=updates)  # ty: ignore[unresolved-attribute]


from fabricatio_comfyui.models.graph import Graph, LoraSpec, NodeRef
from fabricatio_comfyui.models.resolution import Prop, resolve_canvas
from fabricatio_comfyui.models.specs import SketchSpec
from pydantic import ValidationError


def _node_payload(raw: dict[str, object], node_id: str) -> dict[str, object]:
    """Narrow the raw API-format graph to one node's mutable payload."""
    return cast("dict[str, object]", raw[node_id])


class TestFactories:
    """Cached-factory and bundled-template construction paths."""

    @pytest.mark.asyncio
    async def test_comfyui_client_is_shared(self) -> None:
        """The cached factory hands out one shared instance per base URL."""
        assert get_comfyui_client(comfyui_config.base_url) is get_comfyui_client(comfyui_config.base_url)

    @pytest.mark.asyncio
    async def test_client_factory_caches_per_url(self) -> None:
        """get_comfyui_client returns the same client per (loop, URL) pair, distinct per URL."""
        other = "http://127.0.0.1:9999"

        url = comfyui_config.base_url
        assert get_comfyui_client(url) is get_comfyui_client(url)
        assert get_comfyui_client(other) is not get_comfyui_client(url)

    @pytest.mark.asyncio
    async def test_client_factory_scoped_to_event_loop(self) -> None:
        """Identity holds within one loop; another loop gets a distinct pool instance."""
        url = comfyui_config.base_url
        first = get_comfyui_client(url)
        assert get_comfyui_client(url) is first  # cached within this loop

        # A different event loop must not inherit this loop's client: run the
        # factory on its own loop in a side thread.
        seen: list[object] = []

        def side_loop() -> None:
            async def grab() -> None:
                seen.append(get_comfyui_client(url))

            asyncio.run(grab())

        worker = threading.Thread(target=side_loop)
        worker.start()
        worker.join()
        assert seen[0] is not first

    def test_default_builds_full_graph(self) -> None:
        """default() builds all eleven nodes in Python, no JSON asset."""
        api = Graph.default().to_api()
        assert len(api) == 11
        assert all(not name.startswith("lora_") for name in api)


# ======================================================================
# Graph tests — the Python-initialised typed graph and its wire format
# ======================================================================


class TestGraph:
    """Graph is initialised in Python and serializes to exact wire format."""

    def test_typed_node_access(self) -> None:
        """Nodes are reachable through typed fields, not lookups."""
        graph = Graph.default()
        assert graph.loader.class_type == "CheckpointLoaderSimple"
        assert graph.loader.inputs.ckpt_name == "catTowerNoobaiXL_v15Vpred.safetensors"
        assert graph.latent.inputs.width == 768
        assert graph.latent.inputs.height == 512
        assert graph.latent.inputs.batch_size == 1
        assert graph.positive.class_type == "CLIPTextEncode"
        assert graph.negative.class_type == "CLIPTextEncode"
        assert graph.preview.inputs.images.node_id == "refine_decode"
        assert graph.sampler_base.class_type == "KSamplerAdvanced"
        assert graph.sampler_refine.class_type == "KSamplerAdvanced"

    def test_default_sampler_settings(self) -> None:
        """The bundled template samples with euler on the simple schedule."""
        graph = Graph.default()
        for sampler in (graph.sampler_base, graph.sampler_refine):
            assert sampler.inputs.sampler_name == "euler"
            assert sampler.inputs.scheduler == "simple"

    def test_node_ref_serializes_to_api_tuple(self) -> None:
        """NodeRef serializes to the API pair form."""
        ref = NodeRef(node_id="sampler_base", output_index=1)
        assert ref.model_dump() == ("sampler_base", 1)

    def test_node_ref_first_factory(self) -> None:
        """NodeRef.first points at the source node's first output."""
        assert NodeRef.first("sampler_base").model_dump() == ("sampler_base", 0)

    def test_with_checkpoint(self) -> None:
        """with_checkpoint updates the loader's ckpt_name."""
        graph = Graph.default().with_checkpoint("model_v2.safetensors")
        assert graph.loader.inputs.ckpt_name == "model_v2.safetensors"

    def test_with_prompts(self) -> None:
        """with_positive_prompt / with_negative_prompt set the typed nodes."""
        graph = Graph.default().with_positive_prompt("a landscape").with_negative_prompt("blurry")
        assert graph.positive.inputs.text == "a landscape"
        assert graph.negative.inputs.text == "blurry"

    def test_with_resolution(self) -> None:
        """with_resolution updates the latent canvas dimensions."""
        graph = Graph.default().with_resolution(width=1024, height=768)
        assert graph.latent.inputs.width == 1024
        assert graph.latent.inputs.height == 768

    def test_with_resolution_partial(self) -> None:
        """with_resolution only updates the provided dimension."""
        graph = Graph.default().with_resolution(height=640)
        assert graph.latent.inputs.width == 768  # unchanged
        assert graph.latent.inputs.height == 640

    def test_with_sampler_updates_both_stages(self) -> None:
        """with_sampler aligns the base and refine samplers."""
        graph = Graph.default().with_sampler(seed=999, steps=30, cfg=7.5)
        for sampler in (graph.sampler_base, graph.sampler_refine):
            assert sampler.inputs.noise_seed == 999
            assert sampler.inputs.steps == 30
            assert sampler.inputs.cfg == 7.5

    def test_with_sampler_partial(self) -> None:
        """with_sampler only updates the provided parameters."""
        graph = Graph.default()
        original_steps = graph.sampler_base.inputs.steps
        graph.with_sampler(cfg=12.0)
        assert graph.sampler_base.inputs.cfg == 12.0
        assert graph.sampler_base.inputs.steps == original_steps

    def test_mutators_chain(self) -> None:
        """with_* builders return self, so calls chain."""
        graph = Graph.default()
        result = graph.with_checkpoint("x.safetensors").with_positive_prompt("chained")
        assert result is graph

    def test_mutators_validate_assignment(self) -> None:
        """The typed contract holds for the whole lifetime, not just at load."""
        graph = Graph.default()
        with pytest.raises(ValidationError):
            graph.with_resolution(width=cast("int", "abc"))
        with pytest.raises(ValidationError):
            graph.with_sampler(steps=cast("int", "twenty"))
        with pytest.raises(ValidationError):
            graph.with_checkpoint(cast("str", 123))
        with pytest.raises(ValidationError):
            graph.positive.inputs.text = cast("str", None)

    def test_mutators_accept_typed_knobs(self) -> None:
        """Legitimate typed values pass assignment validation."""
        graph = Graph.default()
        graph.with_checkpoint("x.safetensors").with_resolution(width=1024, height=768)
        graph.with_sampler(seed=42, steps=20, cfg=7.0)
        assert graph.loader.inputs.ckpt_name == "x.safetensors"
        assert graph.latent.inputs.width == 1024
        assert graph.sampler_base.inputs.noise_seed == 42

    def test_with_loras(self) -> None:
        """LoRAs chain into the model/CLIP path of the bundled graph."""
        graph = Graph.default().with_lora("a.safetensors", strength=0.5).with_lora("b.safetensors")
        api = graph.to_api()
        lora0 = cast("dict[str, object]", api["lora_0"])
        lora1 = cast("dict[str, object]", api["lora_1"])
        assert lora0["class_type"] == "LoraLoader"
        inputs0 = cast("dict[str, object]", lora0["inputs"])
        assert inputs0["model"] == ("loader", 0)
        assert inputs0["clip"] == ("loader", 1)
        assert inputs0["lora_name"] == "a.safetensors"
        assert inputs0["strength_model"] == 0.5
        inputs1 = cast("dict[str, object]", lora1["inputs"])
        assert inputs1["model"] == ("lora_0", 0)
        assert inputs1["clip"] == ("lora_0", 1)
        for name in ("sampler_base", "sampler_refine"):
            inputs = cast("dict[str, object]", cast("dict[str, object]", api[name])["inputs"])
            assert inputs["model"] == ("lora_1", 0)
        for name in ("positive", "negative"):
            inputs = cast("dict[str, object]", cast("dict[str, object]", api[name])["inputs"])
            assert inputs["clip"] == ("lora_1", 1)

    def test_unknown_input_key_rejected(self) -> None:
        """A node input outside the known shape fails loudly at load."""
        raw = Graph.default().to_api()
        _node_payload(raw, "loader").setdefault("inputs", {})["bogus_knob"] = 1
        with pytest.raises(ValidationError):
            Graph.model_validate(raw)

    def test_wrong_class_type_rejected(self) -> None:
        """A class_type outside the literal union fails loudly at load."""
        raw = Graph.default().to_api()
        _node_payload(raw, "loader")["class_type"] = "KSampler"
        with pytest.raises(ValidationError):
            Graph.model_validate(raw)

    def test_missing_node_rejected(self) -> None:
        """A missing node id fails loudly at load."""
        raw = Graph.default().to_api()
        del raw["sampler_refine"]
        with pytest.raises(ValidationError):
            Graph.model_validate(raw)

    def test_unknown_node_id_rejected(self) -> None:
        """An unexpected extra node id fails loudly at load."""
        raw = Graph.default().to_api()
        raw["999"] = {"class_type": "PreviewImage", "inputs": {"images": ["15", 0]}, "_meta": {"title": "x"}}
        with pytest.raises(ValidationError):
            Graph.model_validate(raw)


class TestAnimaGraph:
    """The anima template keeps model filenames as placeholders and serializes exactly."""

    def test_default(self) -> None:
        """Defaults hold placeholder model tokens and the anima wire shape."""
        graph = AnimaGraph.default()
        assert graph.loader.class_type == "CheckpointLoaderSimple"
        assert graph.loader.inputs.ckpt_name == "<anima_checkpoint>"
        assert graph.clip.class_type == "CLIPLoader"
        assert graph.clip.inputs.clip_name == "<anima_clip>"
        assert graph.vae.class_type == "VAELoader"
        assert graph.vae.inputs.vae_name == "<anima_vae>"
        assert graph.latent.inputs.width == 1344
        assert graph.latent.inputs.height == 1024
        assert graph.sampler.inputs.sampler_name == "er_sde"
        assert graph.sampler.inputs.scheduler == "simple"
        assert graph.sampler.inputs.steps == 32
        assert graph.sampler.inputs.cfg == 7.0
        assert graph.positive.inputs.clip.node_id == "clip"
        assert graph.sampler.inputs.model.node_id == "loader"
        assert graph.decode.inputs.vae.node_id == "vae"
        assert graph.preview.inputs.images.node_id == "decode"
        api = graph.to_api()
        assert all(not name.startswith("lora_") for name in api)

    def test_with_builders(self) -> None:
        """The typed builders resolve the model placeholders and knobs."""
        graph = (
            AnimaGraph.default()
            .with_checkpoint("anima-ckpt.safetensors")
            .with_clip("anima-clip.safetensors")
            .with_vae("anima-vae.safetensors")
            .with_positive_prompt("a cat")
            .with_resolution(width=1024, height=1024)
            .with_sampler(seed=7, steps=25, cfg=8.0)
        )
        assert graph.loader.inputs.ckpt_name == "anima-ckpt.safetensors"
        assert graph.clip.inputs.clip_name == "anima-clip.safetensors"
        assert graph.vae.inputs.vae_name == "anima-vae.safetensors"
        assert graph.positive.inputs.text == "a cat"
        assert graph.latent.inputs.width == 1024
        assert graph.sampler.inputs.noise_seed == 7
        assert graph.sampler.inputs.steps == 25
        assert graph.sampler.inputs.cfg == 8.0

    def test_with_loras(self) -> None:
        """LoRAs chain between the anima loaders and the sampler, leaving decode untouched."""
        graph = (
            AnimaGraph.default()
            .with_checkpoint("ckpt.safetensors")
            .with_clip("clip.safetensors")
            .with_vae("vae.safetensors")
            .with_lora("anima-lora.safetensors")
        )
        api = graph.to_api()
        lora = cast("dict[str, object]", api["lora_0"])
        assert lora["class_type"] == "LoraLoader"
        inputs = cast("dict[str, object]", lora["inputs"])
        assert inputs["model"] == ("loader", 0)
        assert inputs["clip"] == ("clip", 0)
        assert inputs["lora_name"] == "anima-lora.safetensors"
        sampler_inputs = cast("dict[str, object]", cast("dict[str, object]", api["sampler"])["inputs"])
        assert sampler_inputs["model"] == ("lora_0", 0)
        positive_inputs = cast("dict[str, object]", cast("dict[str, object]", api["positive"])["inputs"])
        assert positive_inputs["clip"] == ("lora_0", 1)
        decode_inputs = cast("dict[str, object]", cast("dict[str, object]", api["decode"])["inputs"])
        assert decode_inputs["vae"] == ("vae", 0)
        with pytest.raises(ValidationError):
            graph.with_lora(cast("str", 123))

    def test_mutators_validate_assignment(self) -> None:
        """The typed contract holds for the whole lifetime, not just at load."""
        graph = AnimaGraph.default()
        with pytest.raises(ValidationError):
            graph.with_checkpoint(cast("str", 123))
        with pytest.raises(ValidationError):
            graph.sampler.inputs.steps = cast("int", "twenty")


# ======================================================================
# Model tests
# ======================================================================


class TestModels:
    """Model unit tests."""

    def test_output_image_url_path(self) -> None:
        """Output image URL path encodes all fields."""
        img = OutputImage(filename="test.png", subfolder="sub", type="output")
        assert "filename=test.png" in img.url_path()
        assert "subfolder=sub" in img.url_path()
        assert "type=output" in img.url_path()

    def test_execution_result_all_images(self) -> None:
        """Flatten images from multiple output nodes."""
        result = ExecutionResult(
            prompt_id="abc",
            outputs={
                "9": [OutputImage(filename="img1.png"), OutputImage(filename="img2.png")],
                "12": [OutputImage(filename="img3.png")],
            },
            status="completed",
        )
        assert len(result.all_images()) == 3
        assert result.succeeded() is True

    def test_execution_result_succeeded_with_success_status(self) -> None:
        """ComfyUI returns status_str='success' (not 'completed') — succeeded must accept it."""
        result = ExecutionResult(
            prompt_id="abc",
            outputs={"9": [OutputImage(filename="img.png")]},
            status="success",
        )
        assert result.succeeded() is True

    def test_execution_result_failed(self) -> None:
        """Failed result exposes error message."""
        result = ExecutionResult(prompt_id="abc", status="error", error="CUDA out of memory")
        assert result.succeeded() is False
        assert result.error == "CUDA out of memory"

    def test_execution_result_empty(self) -> None:
        """Empty result yields no images and not succeeded."""
        result = ExecutionResult(prompt_id="abc")
        assert result.all_images() == []
        assert result.succeeded() is False

    def test_execution_result_from_history(self) -> None:
        """from_history builds a result from a history entry."""
        entry = HistoryEntry.from_raw(
            {
                "status": {"status_str": "completed", "completed": True},
                "outputs": {"9": {"images": [{"filename": "img.png", "subfolder": "", "type": "output"}]}},
            },
        )
        result = ExecutionResult.from_history("pid-1", entry)
        assert result.prompt_id == "pid-1"
        assert result.status == "completed"
        assert result.error is None
        assert [img.filename for img in result.all_images()] == ["img.png"]

    def test_execution_result_from_history_failed(self) -> None:
        """from_history carries the exception message on failure."""
        entry = HistoryEntry.from_raw(
            {"status": {"status_str": "error", "completed": True, "exception": "CUDA OOM"}, "outputs": {}},
        )
        result = ExecutionResult.from_history("pid-1", entry)
        assert result.succeeded() is False
        assert result.error == "CUDA OOM"

    def test_history_entry_from_raw(self) -> None:
        """Parse history entry from raw API response."""
        raw = {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {"9": {"images": [{"filename": "img.png", "subfolder": "", "type": "output"}]}},
        }
        entry = HistoryEntry.from_raw(raw)
        assert entry.status.status_str == "completed"
        assert entry.status.completed is True
        assert "9" in entry.outputs
        assert entry.outputs["9"].images[0].filename == "img.png"

    def test_history_entry_from_raw_empty(self) -> None:
        """Empty raw dict defaults to unknown status with no outputs."""
        entry = HistoryEntry.from_raw({})
        assert entry.status.status_str == "unknown"
        assert entry.status.completed is False
        assert entry.outputs == {}

    def test_history_entry_from_raw_failed(self) -> None:
        """Failed history entry carries exception string."""
        raw = {"status": {"status_str": "error", "completed": True, "exception": "CUDA OOM"}, "outputs": {}}
        entry = HistoryEntry.from_raw(raw)
        assert entry.status.status_str == "error"
        assert entry.status.exception == "CUDA OOM"

    def test_queue_info_from_raw(self) -> None:
        """Parse queue info with running and pending entries."""
        raw = {
            "queue_running": [[1, "pid-1", {}, {}, []]],
            "queue_pending": [[2, "pid-2", {}, {}, ["node1"]]],
        }
        info = QueueInfo.from_raw(raw)
        assert len(info.queue_running) == 1
        assert info.queue_running[0].prompt_id == "pid-1"
        assert len(info.queue_pending) == 1
        assert info.queue_pending[0].outputs_to_execute == ["node1"]

    def test_queue_info_from_raw_empty(self) -> None:
        """Empty raw dict yields empty queue lists."""
        info = QueueInfo.from_raw({})
        assert info.queue_running == []
        assert info.queue_pending == []

    def test_upload_response_from_raw(self) -> None:
        """Parse upload response fields from raw dict."""
        resp = UploadResponse.from_raw({"name": "test.png", "subfolder": "input", "type": "input"})
        assert resp.name == "test.png"
        assert resp.subfolder == "input"

    def test_prompt_response_fields(self) -> None:
        """PromptResponse carries id, number, and default empty errors."""
        resp = PromptResponse(prompt_id="uuid-123", number=5)
        assert resp.prompt_id == "uuid-123"
        assert resp.number == 5
        assert resp.node_errors == {}


# ======================================================================
# Resolution tests — Prop presets and the megapixel canvas resolver
# ======================================================================


class TestResolve:
    """Prop parsing and megapixel -> canvas resolution."""

    def test_full_knobs_1mp_square(self) -> None:
        """1.0 MP at 1:1 resolves to the canonical 1024x1024 canvas."""
        assert resolve_canvas(mp=1.0, prop=Prop.prop_1_1, base=(768, 512)) == (1024, 1024)

    def test_no_knobs_keeps_template_canvas(self) -> None:
        """No knobs returns the template base untouched."""
        assert resolve_canvas(base=(768, 512)) == (768, 512)
        assert resolve_canvas(base=(1344, 1024)) == (1344, 1024)

    def test_prop_only_keeps_template_area(self) -> None:
        """A ratio alone re-sizes the template's own pixel area."""
        assert resolve_canvas(prop="prop_16_9", base=(768, 512)) == (832, 448)
        assert resolve_canvas(prop=Prop.prop_16_9, base=(768, 512)) == (832, 448)

    def test_mp_only_keeps_template_ratio(self) -> None:
        """A budget alone scales the template's own aspect ratio."""
        assert resolve_canvas(mp=0.25, base=(768, 512)) == (640, 384)

    def test_anima_budget_at_4_3_keeps_legacy_canvas(self) -> None:
        """4:3 at the anima canvas budget snaps back to the legacy 1344x1024 canvas."""
        assert resolve_canvas(prop=Prop.prop_4_3, base=(1344, 1024)) == (1344, 1024)

    def test_snap_half_up(self) -> None:
        """Dimensions exactly on a grid half snap up to the next multiple."""
        assert resolve_canvas(base=(1056, 1056)) == (1088, 1088)

    def test_min_dimension_clamp(self) -> None:
        """Degenerate budgets clamp both sides to the 64px floor."""
        assert resolve_canvas(mp=1e-6, prop=Prop.prop_1_1, base=(768, 512)) == (64, 64)

    def test_mp_must_be_positive(self) -> None:
        """Non-positive budgets are loud errors."""
        with pytest.raises(ValueError, match="mp must be positive"):
            resolve_canvas(mp=0.0, base=(768, 512))
        with pytest.raises(ValueError, match="mp must be positive"):
            resolve_canvas(mp=-1.0, base=(768, 512))

    def test_scale_divides_the_budget_off_the_base_canvas(self) -> None:
        """An upscaling template carries mp / scale**2 on its base canvas."""
        # Two-pass template: base 448x448, upscaled 2.3x -> ~1030x1030 ~= 1.06 MP final.
        assert resolve_canvas(mp=1.0, prop=Prop.prop_1_1, base=(768, 512), scale=2.3) == (448, 448)
        assert resolve_canvas(mp=1.5, prop=Prop.prop_3_2, base=(768, 512), scale=2.3) == (640, 448)

    def test_scale_default_one_keeps_latent_budget(self) -> None:
        """Without a scale factor the base canvas is the whole budget (anima path)."""
        assert resolve_canvas(mp=1.0, prop=Prop.prop_1_1, base=(1344, 1024)) == (1024, 1024)

    def test_scale_ignored_without_budget(self) -> None:
        """Scale only reshapes a given budget; no-knob and prop-only calls ignore it."""
        assert resolve_canvas(base=(768, 512), scale=2.3) == (768, 512)
        assert resolve_canvas(prop="prop_16_9", base=(768, 512), scale=2.3) == (832, 448)

    def test_scale_must_be_positive(self) -> None:
        """Non-positive scale factors are loud errors when a budget is given."""
        with pytest.raises(ValueError, match="scale must be positive"):
            resolve_canvas(mp=1.0, base=(768, 512), scale=0.0)
        with pytest.raises(ValueError, match="scale must be positive"):
            resolve_canvas(mp=1.0, base=(768, 512), scale=-2.0)

    def test_unknown_prop_is_loud(self) -> None:
        """Unknown ratio spellings raise the enum's ValueError."""
        with pytest.raises(ValueError, match="not a valid Prop"):
            resolve_canvas(prop="7:4", base=(768, 512))

    def test_prop_members_and_values(self) -> None:
        """auto() makes the member name the value; value lookup fetches members."""
        assert Prop.prop_9_16.value == "prop_9_16"
        assert Prop("prop_16_9") is Prop.prop_16_9
        assert Prop("prop_9_21") is Prop.prop_9_21


# ======================================================================
# Client tests
# ======================================================================


@pytest.mark.asyncio
async def test_generate_flow(tmp_path: Path) -> None:
    """End-to-end flow via the high-level capability: generate -> poll -> download."""
    client = get_comfyui_client(comfyui_config.base_url)

    mock_history: dict[str, object] = {
        "mock-uuid-123": {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {"9": {"images": [{"filename": "ComfyUI_00001_.png", "subfolder": "", "type": "output"}]}},
        },
    }

    with (
        patch.object(client, "_post") as mock_post,
        patch.object(client, "_get") as mock_get,
        patch.object(client, "get_image") as mock_img,
    ):
        mock_post.return_value = {"prompt_id": "mock-uuid-123", "number": 1}

        async def get_side_effect(path: str, **kwargs: object) -> object:
            if path.startswith("/history/"):
                return mock_history
            return {}

        mock_get.side_effect = get_side_effect
        mock_img.return_value = b"fake-image-bytes"

        path = await UseComfyUI().generate_image(
            prompt="a mountain landscape",
            download_dir=tmp_path,
            seed=42,
            steps=20,
        )

        assert path is not None
        assert path == tmp_path / "ComfyUI_00001_.png"
        assert path.read_bytes() == b"fake-image-bytes"
        mock_img.assert_called_once()


@pytest.mark.asyncio
async def test_generate_image_config_download_dir(tmp_path: Path) -> None:
    """download_dir falls back to comfyui_config.download_dir when not passed."""
    client = get_comfyui_client(comfyui_config.base_url)
    mock_history: dict[str, object] = {
        "mock-uuid-123": {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {"9": {"images": [{"filename": "ComfyUI_00001_.png", "subfolder": "", "type": "output"}]}},
        },
    }

    with (
        patch(
            "fabricatio_comfyui.capabilities.comfyui.comfyui_config",
            replace(comfyui_config, download_dir=str(tmp_path)),
        ),
        patch.object(client, "_post", return_value={"prompt_id": "mock-uuid-123", "number": 1}),
        patch.object(client, "_get", return_value=mock_history),
        patch.object(client, "get_image", return_value=b"fake-image-bytes"),
    ):
        path = await UseComfyUI().generate_image(prompt="a mountain landscape", seed=42)

    assert path is not None
    assert path == tmp_path / "ComfyUI_00001_.png"
    assert path.read_bytes() == b"fake-image-bytes"


@pytest.mark.asyncio
async def test_generate_image_class_download_dir(tmp_path: Path) -> None:
    """A class-level download_dir on the capability beats the global config."""
    client = get_comfyui_client(comfyui_config.base_url)
    mock_history: dict[str, object] = {
        "mock-uuid-123": {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {"9": {"images": [{"filename": "ComfyUI_00001_.png", "subfolder": "", "type": "output"}]}},
        },
    }

    class ScopedRole(UseComfyUI):
        download_dir: str = str(tmp_path)

    with (
        patch(
            "fabricatio_comfyui.capabilities.comfyui.comfyui_config",
            replace(comfyui_config, download_dir=str(tmp_path / "global")),
        ),
        patch.object(client, "_post", return_value={"prompt_id": "mock-uuid-123", "number": 1}),
        patch.object(client, "_get", return_value=mock_history),
        patch.object(client, "get_image", return_value=b"fake-image-bytes"),
    ):
        path = await ScopedRole().generate_image(prompt="a mountain landscape", seed=42)

    assert path is not None
    assert path == tmp_path / "ComfyUI_00001_.png"
    assert not (tmp_path / "global").exists()


@pytest.mark.asyncio
async def test_generate_image_instance_download_dir(tmp_path: Path) -> None:
    """A per-instance scoped download_dir on the capability beats the global config."""
    client = get_comfyui_client(comfyui_config.base_url)
    mock_history: dict[str, object] = {
        "mock-uuid-123": {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {"9": {"images": [{"filename": "ComfyUI_00001_.png", "subfolder": "", "type": "output"}]}},
        },
    }
    role = UseComfyUI(download_dir=str(tmp_path))

    with (
        patch(
            "fabricatio_comfyui.capabilities.comfyui.comfyui_config",
            replace(comfyui_config, download_dir=str(tmp_path / "global")),
        ),
        patch.object(client, "_post", return_value={"prompt_id": "mock-uuid-123", "number": 1}),
        patch.object(client, "_get", return_value=mock_history),
        patch.object(client, "get_image", return_value=b"fake-image-bytes"),
    ):
        path = await role.generate_image(prompt="a mountain landscape", seed=42)

    assert path is not None
    assert path == tmp_path / "ComfyUI_00001_.png"
    assert not (tmp_path / "global").exists()


@pytest.mark.asyncio
async def test_generate_image_requires_download_dir() -> None:
    """Missing download dir (param and config) is a loud misuse error, not a silent None."""
    with (
        patch(
            "fabricatio_comfyui.capabilities.comfyui.comfyui_config",
            replace(comfyui_config, download_dir=None),
        ),
        pytest.raises(ValueError, match="download directory"),
    ):
        await UseComfyUI().generate_image(prompt="a cat")


@pytest.mark.asyncio
async def test_generate_image_list_prompts(tmp_path: Path) -> None:
    """A list of prompts yields one downloaded path per prompt, in order."""
    client = get_comfyui_client(comfyui_config.base_url)
    histories = [
        {
            "pid-1": {
                "status": {"status_str": "completed", "completed": True},
                "outputs": {"9": {"images": [{"filename": "ComfyUI_00001_.png", "subfolder": "", "type": "output"}]}},
            },
        },
        {
            "pid-2": {
                "status": {"status_str": "completed", "completed": True},
                "outputs": {"9": {"images": [{"filename": "ComfyUI_00002_.png", "subfolder": "", "type": "output"}]}},
            },
        },
    ]
    with (
        patch.object(
            client, "_post", side_effect=[{"prompt_id": "pid-1", "number": 1}, {"prompt_id": "pid-2", "number": 1}]
        ),
        patch.object(client, "_get", side_effect=histories),
        patch.object(client, "get_image", return_value=b"fake-image-bytes"),
    ):
        paths = await UseComfyUI().generate_image(["a mountain", "a river"], download_dir=tmp_path)
        assert await UseComfyUI().generate_image([], download_dir=tmp_path) == []

    assert paths == [tmp_path / "ComfyUI_00001_.png", tmp_path / "ComfyUI_00002_.png"]
    assert paths[0] is not None
    assert paths[1] is not None
    assert paths[0].read_bytes() == paths[1].read_bytes() == b"fake-image-bytes"


@pytest.mark.asyncio
async def test_generate_image_list_mixed_failure(tmp_path: Path) -> None:
    """A failed generation in a list yields None at its index, keeping correspondence."""
    client = get_comfyui_client(comfyui_config.base_url)
    histories = [
        {
            "pid-1": {
                "status": {"status_str": "completed", "completed": True},
                "outputs": {"9": {"images": [{"filename": "ok.png", "subfolder": "", "type": "output"}]}},
            },
        },
        {
            "pid-2": {
                "status": {"status_str": "error", "completed": True, "exception": "CUDA out of memory"},
                "outputs": {},
            },
        },
    ]
    with (
        patch.object(
            client, "_post", side_effect=[{"prompt_id": "pid-1", "number": 1}, {"prompt_id": "pid-2", "number": 1}]
        ),
        patch.object(client, "_get", side_effect=histories),
        patch.object(client, "get_image", return_value=b"fake-image-bytes"),
    ):
        paths = await UseComfyUI().generate_image(["a mountain", "a river"], download_dir=tmp_path)

    assert paths == [tmp_path / "ok.png", None]
    assert paths[0] is not None
    assert paths[0].read_bytes() == b"fake-image-bytes"


@pytest.mark.asyncio
async def test_generate_image_returns_none_on_failure(tmp_path: Path) -> None:
    """Failed generation yields None from the seal, without downloading anything."""
    client = get_comfyui_client(comfyui_config.base_url)
    failed_history: dict[str, object] = {
        "fail-uuid": {
            "status": {"status_str": "error", "completed": True, "exception": "CUDA out of memory"},
            "outputs": {},
        },
    }

    with (
        patch.object(client, "_post", return_value={"prompt_id": "fail-uuid", "number": 1}),
        patch.object(client, "_get", return_value=failed_history),
        patch.object(client, "get_image") as mock_img,
    ):
        path = await UseComfyUI().generate_image(prompt="a cat", download_dir=tmp_path)

    assert path is None
    mock_img.assert_not_called()


@pytest.mark.asyncio
async def test_generate_applies_knobs_to_bundled_graph() -> None:
    """Generate builds the internal graph and applies every knob."""
    client = ComfyUIHttpClient.create(None)

    captured: dict[str, object] = {}

    async def post_side_effect(path: str, **kwargs: object) -> dict[str, object]:
        captured["path"] = path
        captured.update(cast("dict[str, object]", kwargs.get("json_data") or {}))
        return {"prompt_id": "pid-1", "number": 1}

    completed: dict[str, object] = {
        "pid-1": {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {},
        },
    }

    with (
        patch.object(client, "_post", side_effect=post_side_effect),
        patch.object(client, "_get", return_value=completed),
    ):
        await client.generate(
            prompt="a cat",
            negative_prompt="ugly",
            prop=Prop.prop_1_1,
            mp=1.0,
            seed=42,
            steps=20,
            cfg=7.0,
            checkpoint="custom.safetensors",
            front=True,
        )

    assert captured["path"] == "/prompt"
    prompt = cast("dict[str, object]", captured["prompt"])
    assert cast("dict[str, object]", prompt["loader"])["inputs"]["ckpt_name"] == "custom.safetensors"
    assert cast("dict[str, object]", prompt["positive"])["inputs"]["text"] == "a cat"
    assert cast("dict[str, object]", prompt["negative"])["inputs"]["text"] == "ugly"
    # mp budgets the FINAL image; the two-pass template upscales the base canvas
    # by 2.3 before the refine pass, so the base latent carries mp / 2.3**2.
    assert cast("dict[str, object]", prompt["latent"])["inputs"]["width"] == 448
    assert cast("dict[str, object]", prompt["latent"])["inputs"]["height"] == 448
    assert cast("dict[str, object]", prompt["sampler_base"])["inputs"]["noise_seed"] == 42
    assert cast("dict[str, object]", prompt["sampler_base"])["inputs"]["steps"] == 20
    assert cast("dict[str, object]", prompt["sampler_base"])["inputs"]["cfg"] == 7.0
    assert captured["front"] is True
    assert captured["client_id"] == client.client_id()


@pytest.mark.asyncio
async def test_generate_applies_config_size_defaults() -> None:
    """[ext.comfyui] mp/prop default the canvas when no size knobs are passed."""
    client = ComfyUIHttpClient.create(None)
    captured: dict[str, object] = {}

    async def post_side_effect(path: str, **kwargs: object) -> dict[str, object]:
        captured.update(cast("dict[str, object]", kwargs.get("json_data") or {}))
        return {"prompt_id": "pid-1", "number": 1}

    completed: dict[str, object] = {
        "pid-1": {"status": {"status_str": "completed", "completed": True}, "outputs": {}},
    }
    sized_config = replace(comfyui_config, mp=1.5, prop="prop_3_2")
    with (
        patch("fabricatio_comfyui.http_client.comfyui_config", sized_config),
        patch.object(client, "_post", side_effect=post_side_effect),
        patch.object(client, "_get", return_value=completed),
    ):
        await client.generate("a cat")

    prompt = cast("dict[str, object]", captured["prompt"])
    assert cast("dict[str, object]", prompt["latent"])["inputs"]["width"] == 640
    assert cast("dict[str, object]", prompt["latent"])["inputs"]["height"] == 448


@pytest.mark.asyncio
async def test_generate_per_call_size_beats_config_defaults() -> None:
    """Per-call prop/mp knobs win over [ext.comfyui] mp/prop defaults."""
    client = ComfyUIHttpClient.create(None)
    captured: dict[str, object] = {}

    async def post_side_effect(path: str, **kwargs: object) -> dict[str, object]:
        captured.update(cast("dict[str, object]", kwargs.get("json_data") or {}))
        return {"prompt_id": "pid-1", "number": 1}

    completed: dict[str, object] = {
        "pid-1": {"status": {"status_str": "completed", "completed": True}, "outputs": {}},
    }
    sized_config = replace(comfyui_config, mp=1.5, prop="prop_3_2")
    with (
        patch("fabricatio_comfyui.http_client.comfyui_config", sized_config),
        patch.object(client, "_post", side_effect=post_side_effect),
        patch.object(client, "_get", return_value=completed),
    ):
        await client.generate("a cat", prop=Prop.prop_1_1, mp=1.0)

    prompt = cast("dict[str, object]", captured["prompt"])
    assert cast("dict[str, object]", prompt["latent"])["inputs"]["width"] == 448
    assert cast("dict[str, object]", prompt["latent"])["inputs"]["height"] == 448


@pytest.mark.asyncio
async def test_generate_anima_workflow_keeps_full_budget() -> None:
    """The single-pass anima template has no upscale, so mp sizes the latent directly."""
    client = ComfyUIHttpClient.create(None)
    captured: dict[str, object] = {}

    async def post_side_effect(path: str, **kwargs: object) -> dict[str, object]:
        captured.update(cast("dict[str, object]", kwargs.get("json_data") or {}))
        return {"prompt_id": "pid-1", "number": 1}

    completed: dict[str, object] = {
        "pid-1": {"status": {"status_str": "completed", "completed": True}, "outputs": {}},
    }
    sized_config = replace(
        comfyui_config,
        workflow="anima",
        anima_checkpoint="ckpt.safetensors",
        anima_clip="clip.safetensors",
        anima_vae="vae.safetensors",
        mp=1.0,
    )
    with (
        patch("fabricatio_comfyui.http_client.comfyui_config", sized_config),
        patch.object(client, "_post", side_effect=post_side_effect),
        patch.object(client, "_get", return_value=completed),
    ):
        await client.generate("a cat")

    prompt = cast("dict[str, object]", captured["prompt"])
    assert cast("dict[str, object]", prompt["latent"])["inputs"]["width"] == 1152
    assert cast("dict[str, object]", prompt["latent"])["inputs"]["height"] == 896


@pytest.mark.asyncio
async def test_generate_mp_only_keeps_template_ratio() -> None:
    """A megapixel knob alone sizes the template's own 3:2 ratio."""
    client = ComfyUIHttpClient.create(None)
    captured: dict[str, object] = {}

    async def post_side_effect(path: str, **kwargs: object) -> dict[str, object]:
        captured.update(cast("dict[str, object]", kwargs.get("json_data") or {}))
        return {"prompt_id": "pid-1", "number": 1}

    completed: dict[str, object] = {
        "pid-1": {"status": {"status_str": "completed", "completed": True}, "outputs": {}},
    }
    with (
        patch.object(client, "_post", side_effect=post_side_effect),
        patch.object(client, "_get", return_value=completed),
    ):
        await client.generate("a cat", mp=0.25)

    prompt = cast("dict[str, object]", captured["prompt"])
    assert cast("dict[str, object]", prompt["latent"])["inputs"]["width"] == 256
    assert cast("dict[str, object]", prompt["latent"])["inputs"]["height"] == 192


@pytest.mark.asyncio
async def test_generate_rejects_unknown_config_prop() -> None:
    """An unparseable [ext.comfyui] prop fails loudly at canvas resolution."""
    client = ComfyUIHttpClient.create(None)
    bad_config = replace(comfyui_config, mp=1.0, prop="7:4")
    with (
        patch("fabricatio_comfyui.http_client.comfyui_config", bad_config),
        pytest.raises(ValueError, match="not a valid Prop"),
    ):
        await client.generate("a cat")


@pytest.mark.asyncio
async def test_generate_returns_typed_result() -> None:
    """Generate returns an ExecutionResult, not a raw dict."""
    client = ComfyUIHttpClient.create(None)
    mock_history: dict[str, object] = {
        "pid-1": {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {"9": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}},
        },
    }
    with (
        patch.object(client, "_post", return_value={"prompt_id": "pid-1", "number": 1}),
        patch.object(client, "_get", return_value=mock_history),
    ):
        results = await client.generate("hi")
        assert len(results) == 1
        result = results[0]
        assert isinstance(result, ExecutionResult)
        assert result.prompt_id == "pid-1"
        assert result.succeeded() is True


@pytest.mark.asyncio
async def test_generate_batch_prompts() -> None:
    """Generate accepts a prompt list and returns one result per prompt, in order."""
    client = ComfyUIHttpClient.create(None)
    mock_history: dict[str, object] = {
        "pid-1": {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {"9": {"images": [{"filename": "a.png", "subfolder": "", "type": "output"}]}},
        },
        "pid-2": {
            "status": {"status_str": "error", "completed": True, "exception": "boom"},
            "outputs": {},
        },
    }
    with (
        patch.object(
            client,
            "_post",
            side_effect=[{"prompt_id": "pid-1", "number": 1}, {"prompt_id": "pid-2", "number": 1}],
        ),
        patch.object(client, "_get", return_value=mock_history),
    ):
        results = await client.generate(["first", "second"])

    assert [r.prompt_id for r in results] == ["pid-1", "pid-2"]
    assert results[0].succeeded() is True
    assert results[1].succeeded() is False


@pytest.mark.asyncio
async def test_generate_anima_workflow_resolves_models() -> None:
    """The anima workflow submits the configured checkpoint/CLIP/VAE names."""
    client = ComfyUIHttpClient.create(None)
    captured: dict[str, object] = {}

    async def post_side_effect(path: str, **kwargs: object) -> dict[str, object]:
        captured.update(cast("dict[str, object]", kwargs.get("json_data") or {}))
        return {"prompt_id": "pid-1", "number": 1}

    completed: dict[str, object] = {
        "pid-1": {"status": {"status_str": "completed", "completed": True}, "outputs": {}},
    }
    anima_config = replace(
        comfyui_config,
        workflow="anima",
        anima_checkpoint="anima-ckpt.safetensors",
        anima_clip="anima-clip.safetensors",
        anima_vae="anima-vae.safetensors",
    )
    with (
        patch("fabricatio_comfyui.http_client.comfyui_config", anima_config),
        patch.object(client, "_post", side_effect=post_side_effect),
        patch.object(client, "_get", return_value=completed),
    ):
        await client.generate("a cat")

    prompt = cast("dict[str, object]", captured["prompt"])
    assert cast("dict[str, object]", prompt["loader"])["inputs"]["ckpt_name"] == "anima-ckpt.safetensors"
    assert cast("dict[str, object]", prompt["clip"])["inputs"]["clip_name"] == "anima-clip.safetensors"
    assert cast("dict[str, object]", prompt["vae"])["inputs"]["vae_name"] == "anima-vae.safetensors"
    assert cast("dict[str, object]", prompt["sampler"])["inputs"]["steps"] == 32


@pytest.mark.asyncio
async def test_generate_anima_workflow_checkpoint_override() -> None:
    """A per-call checkpoint wins over the anima config key."""
    client = ComfyUIHttpClient.create(None)
    captured: dict[str, object] = {}

    async def post_side_effect(path: str, **kwargs: object) -> dict[str, object]:
        captured.update(cast("dict[str, object]", kwargs.get("json_data") or {}))
        return {"prompt_id": "pid-1", "number": 1}

    completed: dict[str, object] = {
        "pid-1": {"status": {"status_str": "completed", "completed": True}, "outputs": {}},
    }
    anima_config = replace(
        comfyui_config,
        workflow="anima",
        anima_checkpoint="anima-ckpt.safetensors",
        anima_clip="anima-clip.safetensors",
        anima_vae="anima-vae.safetensors",
    )
    with (
        patch("fabricatio_comfyui.http_client.comfyui_config", anima_config),
        patch.object(client, "_post", side_effect=post_side_effect),
        patch.object(client, "_get", return_value=completed),
    ):
        await client.generate("a cat", checkpoint="override.safetensors")

    prompt = cast("dict[str, object]", captured["prompt"])
    assert cast("dict[str, object]", prompt["loader"])["inputs"]["ckpt_name"] == "override.safetensors"


@pytest.mark.asyncio
async def test_generate_anima_workflow_requires_models() -> None:
    """Anima generation fails loudly while any model filename is unset."""
    client = ComfyUIHttpClient.create(None)
    missing_ckpt = replace(comfyui_config, workflow="anima")
    missing_clip = replace(
        comfyui_config,
        workflow="anima",
        anima_checkpoint="anima-ckpt.safetensors",
    )
    with (
        patch("fabricatio_comfyui.http_client.comfyui_config", missing_ckpt),
        pytest.raises(ValueError, match="anima_checkpoint"),
    ):
        await client.generate("a cat")
    with (
        patch("fabricatio_comfyui.http_client.comfyui_config", missing_clip),
        pytest.raises(ValueError, match="anima_clip"),
    ):
        await client.generate("a cat")


@pytest.mark.asyncio
async def test_generate_applies_loras() -> None:
    """A loras list chains LoraLoader nodes into the submitted graph."""
    client = ComfyUIHttpClient.create(None)
    captured: dict[str, object] = {}

    async def post_side_effect(path: str, **kwargs: object) -> dict[str, object]:
        captured.update(cast("dict[str, object]", kwargs.get("json_data") or {}))
        return {"prompt_id": "pid-1", "number": 1}

    completed: dict[str, object] = {
        "pid-1": {"status": {"status_str": "completed", "completed": True}, "outputs": {}},
    }
    with (
        patch.object(client, "_post", side_effect=post_side_effect),
        patch.object(client, "_get", return_value=completed),
    ):
        await client.generate(
            "a cat",
            loras=[
                LoraSpec(lora_name="a.safetensors", strength=0.5),
                LoraSpec(lora_name="b.safetensors"),
            ],
        )

    prompt = cast("dict[str, object]", captured["prompt"])
    lora0_inputs = cast("dict[str, object]", cast("dict[str, object]", prompt["lora_0"])["inputs"])
    assert lora0_inputs["lora_name"] == "a.safetensors"
    assert lora0_inputs["strength_model"] == 0.5
    sampler_inputs = cast("dict[str, object]", cast("dict[str, object]", prompt["sampler_base"])["inputs"])
    assert sampler_inputs["model"] == ("lora_1", 0)


@pytest.mark.asyncio
async def test_generate_anima_workflow_applies_loras() -> None:
    """Anima generation chains loras after resolving its model filenames."""
    client = ComfyUIHttpClient.create(None)
    captured: dict[str, object] = {}

    async def post_side_effect(path: str, **kwargs: object) -> dict[str, object]:
        captured.update(cast("dict[str, object]", kwargs.get("json_data") or {}))
        return {"prompt_id": "pid-1", "number": 1}

    completed: dict[str, object] = {
        "pid-1": {"status": {"status_str": "completed", "completed": True}, "outputs": {}},
    }
    anima_config = replace(
        comfyui_config,
        workflow="anima",
        anima_checkpoint="anima-ckpt.safetensors",
        anima_clip="anima-clip.safetensors",
        anima_vae="anima-vae.safetensors",
    )
    with (
        patch("fabricatio_comfyui.http_client.comfyui_config", anima_config),
        patch.object(client, "_post", side_effect=post_side_effect),
        patch.object(client, "_get", return_value=completed),
    ):
        await client.generate("a cat", loras=[LoraSpec(lora_name="anima-lora.safetensors", strength=0.8)])

    prompt = cast("dict[str, object]", captured["prompt"])
    lora_inputs = cast("dict[str, object]", cast("dict[str, object]", prompt["lora_0"])["inputs"])
    assert lora_inputs["lora_name"] == "anima-lora.safetensors"
    assert lora_inputs["strength_model"] == 0.8
    sampler_inputs = cast("dict[str, object]", cast("dict[str, object]", prompt["sampler"])["inputs"])
    assert sampler_inputs["model"] == ("lora_0", 0)
    positive_inputs = cast("dict[str, object]", cast("dict[str, object]", prompt["positive"])["inputs"])
    assert positive_inputs["clip"] == ("lora_0", 1)


@pytest.mark.asyncio
async def test_generate_timeout(tmp_path: Path) -> None:
    """Verify timeout raises when polling fails to complete."""
    client = get_comfyui_client(comfyui_config.base_url)
    with (
        patch.object(client, "_post", return_value={"prompt_id": "timeout-uuid"}),
        patch.object(client, "_get", return_value={}),
        pytest.raises(TimeoutError),
    ):
        await UseComfyUI().generate_image(prompt="anything", download_dir=tmp_path, timeout=0.2)


@pytest.mark.asyncio
async def test_generate_interrupts_on_cancellation() -> None:
    """Cancelling generate interrupts the server-side job before propagating."""
    client = ComfyUIHttpClient.create(None)
    calls: list[str] = []

    async def post_side_effect(path: str, **kwargs: object) -> dict[str, object]:
        calls.append(path)
        return {"prompt_id": "pid-1", "number": 1}

    with (
        patch.object(client, "_post", side_effect=post_side_effect),
        patch.object(client, "_get", side_effect=asyncio.CancelledError),
        pytest.raises(asyncio.CancelledError),
    ):
        await client.generate("a cat")

    assert calls == ["/prompt", "/interrupt"]


@pytest.mark.asyncio
async def test_generate_cancel_cleanup_failure_keeps_cancellation() -> None:
    """A failed interrupt must not mask the cancellation."""
    client = ComfyUIHttpClient.create(None)

    async def post_side_effect(path: str, **kwargs: object) -> dict[str, object]:
        if path == "/prompt":
            return {"prompt_id": "pid-1", "number": 1}
        raise httpx.ConnectError("server down")

    with (
        patch.object(client, "_post", side_effect=post_side_effect),
        patch.object(client, "_get", side_effect=asyncio.CancelledError),
        pytest.raises(asyncio.CancelledError),
    ):
        await client.generate("a cat")


@pytest.mark.asyncio
async def test_download_images_returns_paths(tmp_path: Path) -> None:
    """download_images returns the local path of every downloaded image."""
    client = ComfyUIHttpClient.create(None)
    result = ExecutionResult(
        prompt_id="pid",
        outputs={"9": [OutputImage(filename="a.png"), OutputImage(filename="b.png")]},
    )
    with patch.object(client, "get_image", return_value=b"png-bytes"):
        paths = await client.download_images(result, tmp_path)
    assert paths == [tmp_path / "a.png", tmp_path / "b.png"]
    assert all(p.read_bytes() == b"png-bytes" for p in paths)


@pytest.mark.asyncio
async def test_download_first_image(tmp_path: Path) -> None:
    """download_first_image downloads the first image and returns its local path."""
    client = ComfyUIHttpClient.create(None)
    result = ExecutionResult(prompt_id="pid", outputs={"9": [OutputImage(filename="out.png")]})
    with patch.object(client, "get_image", return_value=b"png-bytes"):
        path = await client.download_first_image(result, tmp_path)
    assert path is not None
    assert path == tmp_path / "out.png"
    assert path.read_bytes() == b"png-bytes"


@pytest.mark.asyncio
async def test_download_first_image_empty(tmp_path: Path) -> None:
    """download_first_image returns None when the result holds no images."""
    client = ComfyUIHttpClient.create(None)
    with patch.object(client, "get_image") as mock_img:
        path = await client.download_first_image(ExecutionResult(prompt_id="pid"), tmp_path)
    assert path is None
    mock_img.assert_not_called()


@pytest.mark.asyncio
async def test_upload_image(tmp_path: Path) -> None:
    """Upload a local image file and verify the typed response."""
    client = ComfyUIHttpClient.create(None)

    with patch.object(client, "_upload") as mock_upload:
        mock_upload.return_value = {"name": "test.png", "subfolder": "input"}

        fake_img = tmp_path / "test.png"
        fake_img.write_bytes(b"fake-png-content")

        result = await client.upload_image(fake_img)
        assert result.name == "test.png"
        assert isinstance(result, UploadResponse)
        mock_upload.assert_called_once()


@pytest.mark.asyncio
async def test_get_history_returns_typed() -> None:
    """get_history returns a HistoryEntry for a known prompt id."""
    client = ComfyUIHttpClient.create(None)

    raw = {
        "pid-1": {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {"9": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}},
        },
    }
    with patch.object(client, "_get", return_value=raw):
        entry = await client.get_history("pid-1")
        assert isinstance(entry, HistoryEntry)
        assert entry.status.status_str == "completed"


@pytest.mark.asyncio
async def test_get_history_missing() -> None:
    """get_history returns None for a nonexistent prompt id."""
    client = ComfyUIHttpClient.create(None)

    with patch.object(client, "_get", return_value={}):
        entry = await client.get_history("nonexistent")
        assert entry is None


@pytest.mark.asyncio
async def test_queue_info_typed() -> None:
    """get_queue_info returns a typed QueueInfo object."""
    client = ComfyUIHttpClient.create(None)

    raw = {"queue_running": [], "queue_pending": [[1, "pid", {}, {}, []]]}
    with patch.object(client, "_get", return_value=raw):
        info = await client.get_queue_info()
        assert isinstance(info, QueueInfo)
        assert len(info.queue_pending) == 1


@pytest.mark.asyncio
async def test_client_id_uses_base_url() -> None:
    """client_id is derived from the configured base_url."""
    c1 = ComfyUIHttpClient.create(None)
    c2 = ComfyUIHttpClient.create(None)
    assert c1.client_id() == c2.client_id()
    assert c1.client_id() == comfyui_config.base_url.rstrip("/").lower()


@pytest.mark.asyncio
async def test_wait_for_completion_polling() -> None:
    """wait_for_completion uses HTTP polling."""
    client = ComfyUIHttpClient.create(None)

    raw = {
        "pid-1": {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {},
        },
    }
    with patch.object(client, "_get", return_value=raw):
        result = await client.wait_for_completion("pid-1", poll_interval=0.01, timeout=5.0)
        assert result.prompt_id == "pid-1"
        assert result.status == "completed"


# ======================================================================
# Integration tests (require live ComfyUI server at 127.0.0.1:8188)
# ======================================================================


def _comfyui_available() -> bool:
    """Check if ComfyUI server is reachable."""
    import httpx

    try:
        r = httpx.get("http://127.0.0.1:8188/system_stats", timeout=3.0)
        return r.status_code == 200
    except httpx.RequestError:
        return False


def _first_checkpoint() -> str | None:
    """Return the first available checkpoint filename on the live server, or None."""
    import httpx

    try:
        r = httpx.get("http://127.0.0.1:8188/models/checkpoints", timeout=3.0)
        if r.status_code != 200:
            return None
        models = r.json()
        return models[0] if models else None
    except httpx.RequestError:
        return None


_requires_comfyui = pytest.mark.skipif(not _comfyui_available(), reason="ComfyUI server not running")
_requires_checkpoint = pytest.mark.skipif(
    _first_checkpoint() is None,
    reason="No checkpoints installed on ComfyUI server",
)


@pytest.mark.asyncio
@_requires_comfyui
@_requires_checkpoint
async def test_integration_generate(tmp_path: Path) -> None:
    """Integration: generate via the bundled workflow against a real server."""
    client = get_comfyui_client(comfyui_config.base_url)
    results = await client.generate(
        prompt="a cute cat",
        checkpoint=_first_checkpoint(),
        timeout=180.0,
    )
    assert len(results) == 1
    assert results[0].succeeded() is True
    assert len(results[0].all_images()) >= 1


@pytest.mark.asyncio
@_requires_comfyui
@_requires_checkpoint
async def test_integration_generate_with_download(tmp_path: Path) -> None:
    """Integration: end-to-end generate with download against a real server."""
    path = await UseComfyUI().generate_image(
        prompt="a cute cat",
        checkpoint=_first_checkpoint(),
        download_dir=tmp_path,
        timeout=180.0,
    )

    assert path is not None
    assert path.stat().st_size > 0


class TestSketchSpec:
    """The propose-able generation spec bundles prompt, negative prompt, and canvas."""

    def test_prop_value_coercion(self) -> None:
        """``prop_16_9``-style member values coerce natively; ``"16:9"`` spellings are not accepted."""
        assert SketchSpec(prompt="a cat", prop="prop_16_9").prop is Prop.prop_16_9
        with pytest.raises(ValidationError):
            SketchSpec(prompt="a cat", prop="16:9")

    def test_defaults_keep_fallback_chain(self) -> None:
        """Size fields default to None so generation falls back to config and template."""
        spec = SketchSpec(prompt="a cat")
        assert spec.negative_prompt == ""
        assert spec.prop is None
        assert spec.mp is None

    def test_rejects_unknown_prop_and_nonpositive_mp(self) -> None:
        """Unknown aspect presets and non-positive budgets fail validation loudly."""
        with pytest.raises(ValidationError):
            SketchSpec.model_validate({"prompt": "a cat", "prop": "prop_3_7"})
        with pytest.raises(ValidationError):
            SketchSpec(prompt="a cat", mp=0)
        with pytest.raises(ValidationError):
            SketchSpec(prompt="a cat", mp=-2.0)

    def test_json_round_trip_preserves_spec(self) -> None:
        """model_dump_json emits member-value prop ("prop_3_2") that revalidates to the same spec."""
        spec = SketchSpec(prompt="a lone rider at dawn", negative_prompt="text", prop="prop_3_2", mp=1.5)
        assert SketchSpec.model_validate_json(spec.model_dump_json()) == spec


# ======================================================================
# LoRA catalog — manual declaration + LLM selection
# ======================================================================


def _catalog() -> LoraCatalog:
    return LoraCatalog(
        entries=[
            LoraEntry(
                lora_name="detail.safetensors",
                strength=0.7,
                effect="Adds fine detail and crisp lineart.",
                trigger_words="detailed lineart",
            ),
            LoraEntry(lora_name="soft.safetensors", strength=0.8, effect="Softens lighting."),
        ]
    )


class TestLoraCatalog:
    """Manual catalog declaration, loud resolution, and trigger-word augmentation."""

    def test_resolve_falls_strength_back_to_recommendation(self) -> None:
        """Missing strengths fall back to each entry's recommendation; overrides win."""
        specs = _catalog().resolve(
            [LoraPick(lora_name="detail.safetensors"), LoraPick(lora_name="soft.safetensors", strength=0.5)]
        )
        assert specs == [
            LoraSpec(lora_name="detail.safetensors", strength=0.7),
            LoraSpec(lora_name="soft.safetensors", strength=0.5),
        ]

    def test_resolve_unknown_name_raises(self) -> None:
        """A pick naming an undeclared LoRA raises instead of wiring a bogus node."""
        with pytest.raises(ValueError, match="Unknown LoRA"):
            _catalog().resolve([LoraPick(lora_name="nope.safetensors")])

    def test_augment_appends_trigger_words_in_chain_order(self) -> None:
        """Trigger words append in chain order; entries without triggers contribute nothing."""
        specs = _catalog().resolve([LoraPick(lora_name="soft.safetensors"), LoraPick(lora_name="detail.safetensors")])
        assert _catalog().augment("a cat", specs) == "a cat, detailed lineart"

    def test_augmented_prompt_noop_without_triggers(self) -> None:
        """An entry without trigger words leaves the prompt untouched."""
        entry = LoraEntry(lora_name="soft.safetensors", strength=0.8, effect="Softens lighting.")
        assert entry.augmented_prompt("a cat") == "a cat"

    def test_brief_lists_every_entry(self) -> None:
        """The brief names every declared entry for the LLM to choose from."""
        brief = _catalog().brief()
        assert "detail.safetensors" in brief
        assert "soft.safetensors" in brief


class TestChooseLoras:
    """LLM selection resolves strictly against the catalog."""

    @pytest.mark.asyncio
    async def test_choose_loras_resolves_selection(self) -> None:
        """Role under test with a mocked LLM."""
        role = ChooseLoras()
        payload = LoraSelection(picks=[LoraPick(lora_name="detail.safetensors", strength=0.9)])

        async def fake_aask_validate(_self: object, **kwargs: object) -> LoraSelection:
            return payload

        with patch.object(ChooseLoras, "aask_validate", new=fake_aask_validate):
            specs = await role.choose_loras("a knight in ornate armor", catalog=_catalog())
        assert specs == [LoraSpec(lora_name="detail.safetensors", strength=0.9)]

    @pytest.mark.asyncio
    async def test_choose_loras_empty_catalog_short_circuits(self) -> None:
        """Role under test against an empty catalog."""
        role = ChooseLoras()
        assert await role.choose_loras("anything", catalog=LoraCatalog()) == []

    @pytest.mark.asyncio
    async def test_choose_loras_forwards_send_to(self) -> None:
        """The send_to routing group reaches the selection proposal."""
        role = ChooseLoras()
        seen: dict[str, object] = {}

        async def fake_propose(_self: object, *_args: object, **kwargs: object) -> LoraSelection:
            seen.update(kwargs)
            return LoraSelection(picks=[])

        with patch.object(ChooseLoras, "propose", new=fake_propose):
            specs = await role.choose_loras("a knight", catalog=_catalog(), send_to="custom")
        assert seen.get("send_to") == "custom"
        assert specs == []
