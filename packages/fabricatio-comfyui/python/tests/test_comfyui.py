"""Tests for the fabricatio-comfyui subpackage."""

import json
from pathlib import Path
from typing import Any, ClassVar, Dict
from unittest.mock import patch

import pytest
from fabricatio_comfyui.capabilities.comfyui import Comfyui
from fabricatio_comfyui.config import comfyui_config
from fabricatio_comfyui.http_client import ComfyuiHTTPClient
from fabricatio_comfyui.models.comfyui import (
    ComfyuiExecutionResult,
    ComfyuiNodeRef,
    ComfyuiOutputImage,
    HistoryEntry,
    PromptResponse,
    QueueInfo,
    UploadResponse,
)
from fabricatio_comfyui.models.workflow import (
    RESOLUTION_SELECTOR_ASPECT_RATIOS,
    FrameAspect,
    Node,
    Workflow,
)

# ======================================================================
# Workflow tests
# ======================================================================


class TestWorkflow:
    """Workflow and Node unit tests."""

    DEMO_JSON: ClassVar[Dict[str, Any]] = {
        "42": {
            "inputs": {"ckpt_name": "catTowerNoobaiXL_v15Vpred.safetensors"},
            "class_type": "CheckpointLoaderSimple",
            "_meta": {"title": "Load Checkpoint"},
        },
        "46": {
            "inputs": {"vae_name": "sdxl_vae.safetensors"},
            "class_type": "VAELoader",
            "_meta": {"title": "Load VAE"},
        },
        "49": {
            "inputs": {"width": ["79", 0], "height": ["79", 1], "batch_size": 1},
            "class_type": "EmptyLatentImage",
            "_meta": {"title": "Empty Latent Image"},
        },
        "50": {
            "inputs": {"text": "positive prompt", "clip": ["65", 1]},
            "class_type": "CLIPTextEncode",
            "_meta": {"title": "CLIP Text Encode (Prompt)"},
        },
        "51": {
            "inputs": {"text": "negative prompt", "clip": ["65", 1]},
            "class_type": "CLIPTextEncode",
            "_meta": {"title": "CLIP Text Encode (Prompt)"},
        },
        "79": {
            "inputs": {"aspect_ratio": "9:16", "megapixels": 1},
            "class_type": "ResolutionSelector",
            "_meta": {"title": "Resolution Selector"},
        },
        "85": {
            "inputs": {
                "add_noise": "enable",
                "noise_seed": 123456,
                "steps": 25,
                "cfg": 8,
                "sampler_name": "euler",
                "scheduler": "simple",
                "start_at_step": 0,
                "end_at_step": 999,
                "return_with_leftover_noise": "disable",
                "model": ["65", 0],
                "positive": ["50", 0],
                "negative": ["51", 0],
                "latent_image": ["49", 0],
            },
            "class_type": "KSamplerAdvanced",
            "_meta": {"title": "KSampler (Advanced)"},
        },
    }

    def test_from_api_preserves_structure(self) -> None:
        """from_api round-trips the demo JSON exactly."""
        wf = Workflow.from_api(self.DEMO_JSON)
        assert wf.to_api() == self.DEMO_JSON

    def test_from_api_preserves_node_ids(self) -> None:
        """from_api keeps original node IDs."""
        wf = Workflow.from_api(self.DEMO_JSON)
        assert wf.node_ids == ["42", "46", "49", "50", "51", "79", "85"]

    def test_from_api_preserves_node_references(self) -> None:
        """from_api preserves [node_id, output_index] references in inputs."""
        wf = Workflow.from_api(self.DEMO_JSON)
        node = wf.get("49")
        assert node.inputs["width"] == ["79", 0]
        assert node.inputs["height"] == ["79", 1]

    def test_from_api_preserves_title(self) -> None:
        """from_api preserves _meta.title as Node.title."""
        wf = Workflow.from_api(self.DEMO_JSON)
        assert wf.get("42").title == "Load Checkpoint"

    def test_from_file(self, tmp_path: Path) -> None:
        """from_file loads from a .json file."""
        p = tmp_path / "test.json"
        p.write_text(json.dumps(self.DEMO_JSON), encoding="utf-8")
        wf = Workflow.from_file(p)
        assert wf.to_api() == self.DEMO_JSON

    def test_default(self) -> None:
        """default() loads the bundled demo workflow."""
        wf = Workflow.default()
        assert len(wf.nodes) > 0
        assert wf.to_api() is not None

    def test_add(self) -> None:
        """Add creates a node with auto-incremented ID."""
        wf = Workflow.new()
        n1 = wf.add("KSampler", title="Sampler", inputs={"seed": 42})
        n2 = wf.add("VAEDecode")
        assert n1.id == "1"
        assert n2.id == "2"
        assert len(wf.nodes) == 2

    def test_add_to_loaded_workflow(self) -> None:
        """Add on a loaded workflow uses the next available ID."""
        wf = Workflow.from_api(self.DEMO_JSON)
        new_node = wf.add("SaveImage")
        assert new_node.id == "86"  # max existing is 85

    def test_get(self) -> None:
        """Get returns the correct node."""
        wf = Workflow.from_api(self.DEMO_JSON)
        node = wf.get("42")
        assert node.type == "CheckpointLoaderSimple"

    def test_get_missing(self) -> None:
        """Get raises KeyError for missing node."""
        wf = Workflow.from_api(self.DEMO_JSON)
        with pytest.raises(KeyError):
            wf.get("999")

    def test_by_type(self) -> None:
        """by_type finds all nodes of a given type."""
        wf = Workflow.from_api(self.DEMO_JSON)
        clip_nodes = wf.by_type("CLIPTextEncode")
        assert len(clip_nodes) == 2
        assert clip_nodes[0].id == "50"
        assert clip_nodes[1].id == "51"

    def test_remove(self) -> None:
        """Remove removes the node and disconnects references."""
        wf = Workflow.from_api(self.DEMO_JSON)
        wf.remove("79")  # ResolutionSelector
        assert "79" not in wf.node_ids
        # Node 49 had references to 79 — those should be gone
        node_49 = wf.get("49")
        assert "width" not in node_49.inputs
        assert "height" not in node_49.inputs

    def test_set_checkpoint(self) -> None:
        """set_checkpoint updates the checkpoint name."""
        wf = Workflow.from_api(self.DEMO_JSON)
        wf.set_checkpoint("new_model.safetensors")
        assert wf.get("42").inputs["ckpt_name"] == "new_model.safetensors"

    def test_set_checkpoint_specific_node(self) -> None:
        """set_checkpoint with node_id targets a specific node."""
        wf = Workflow.from_api(self.DEMO_JSON)
        wf.set_checkpoint("model_v2.safetensors", node_id="42")
        assert wf.get("42").inputs["ckpt_name"] == "model_v2.safetensors"

    def test_set_checkpoint_missing(self) -> None:
        """set_checkpoint raises if no matching node exists."""
        wf = Workflow.new()
        with pytest.raises(KeyError, match="No node with type"):
            wf.set_checkpoint("model.safetensors")

    def test_set_positive_prompt(self) -> None:
        """set_positive_prompt updates the first CLIPTextEncode node."""
        wf = Workflow.from_api(self.DEMO_JSON)
        wf.set_positive_prompt("a beautiful landscape")
        assert wf.get("50").inputs["text"] == "a beautiful landscape"

    def test_set_negative_prompt(self) -> None:
        """set_negative_prompt updates the second CLIPTextEncode node."""
        wf = Workflow.from_api(self.DEMO_JSON)
        wf.set_negative_prompt("bad quality, blurry")
        assert wf.get("51").inputs["text"] == "bad quality, blurry"

    def test_set_sampler_ksampler_advanced(self) -> None:
        """set_sampler updates KSamplerAdvanced parameters."""
        wf = Workflow.from_api(self.DEMO_JSON)
        wf.set_sampler(seed=999, steps=30, cfg=7.5, sampler_name="ddim")
        node = wf.get("85")
        assert node.inputs["noise_seed"] == 999
        assert node.inputs["steps"] == 30
        assert node.inputs["cfg"] == 7.5
        assert node.inputs["sampler_name"] == "ddim"

    def test_set_sampler_partial_update(self) -> None:
        """set_sampler only updates provided parameters."""
        wf = Workflow.from_api(self.DEMO_JSON)
        original_steps = wf.get("85").inputs["steps"]
        wf.set_sampler(cfg=12.0)
        assert wf.get("85").inputs["cfg"] == 12.0
        assert wf.get("85").inputs["steps"] == original_steps

    def test_set_resolution(self) -> None:
        """set_resolution updates EmptyLatentImage dimensions."""
        wf = Workflow.new()
        wf.add("EmptyLatentImage", inputs={"width": 512, "height": 512, "batch_size": 1})
        wf.set_resolution(width=1024, height=768)
        node = wf.by_type("EmptyLatentImage")[0]
        assert node.inputs["width"] == 1024
        assert node.inputs["height"] == 768

    def test_set_chart_proportion_updates_selector(self) -> None:
        """set_chart_proportion updates ResolutionSelector inputs."""
        wf = Workflow.from_api(self.DEMO_JSON)
        wf.set_chart_proportion(aspect_ratio="16:9 (Widescreen)", megapixels=2.0, multiple=16)
        node = wf.get("79")
        assert node.inputs["aspect_ratio"] == "16:9 (Widescreen)"
        assert node.inputs["megapixels"] == 2.0
        assert node.inputs["multiple"] == 16
        # EmptyLatentImage node refs to ResolutionSelector must be preserved
        assert wf.get("49").inputs["width"] == ["79", 0]
        assert wf.get("49").inputs["height"] == ["79", 1]

    def test_set_chart_proportion_partial(self) -> None:
        """set_chart_proportion only updates provided parameters."""
        wf = Workflow.from_api(self.DEMO_JSON)
        original_megapixels = wf.get("79").inputs["megapixels"]
        wf.set_chart_proportion(aspect_ratio="1:1 (Square)")
        node = wf.get("79")
        assert node.inputs["aspect_ratio"] == "1:1 (Square)"
        assert node.inputs["megapixels"] == original_megapixels
        assert "multiple" not in node.inputs

    def test_set_chart_proportion_by_node_id(self) -> None:
        """set_chart_proportion with explicit node_id."""
        wf = Workflow.from_api(self.DEMO_JSON)
        wf.set_chart_proportion(aspect_ratio="3:2 (Photo)", node_id="79")
        assert wf.get("79").inputs["aspect_ratio"] == "3:2 (Photo)"

    def test_set_chart_proportion_wrong_type_raises(self) -> None:
        """set_chart_proportion with node_id that is not a ResolutionSelector."""
        wf = Workflow.from_api(self.DEMO_JSON)
        with pytest.raises(KeyError, match="not ResolutionSelector"):
            wf.set_chart_proportion(aspect_ratio="1:1 (Square)", node_id="42")

    def test_set_chart_proportion_missing_raises(self) -> None:
        """set_chart_proportion raises KeyError when no ResolutionSelector exists."""
        wf = Workflow.new()
        wf.add("EmptyLatentImage", inputs={"width": 512, "height": 512, "batch_size": 1})
        with pytest.raises(KeyError, match="No ResolutionSelector"):
            wf.set_chart_proportion(aspect_ratio="1:1 (Square)")

    def test_set_chart_proportion_invalid_aspect_ratio_raises(self) -> None:
        """set_chart_proportion rejects aspect_ratio values outside the live server's enum."""
        from fabricatio_comfyui.models.workflow import RESOLUTION_SELECTOR_ASPECT_RATIOS

        wf = Workflow.from_api(self.DEMO_JSON)
        with pytest.raises(ValueError, match="Invalid aspect_ratio"):
            wf.set_chart_proportion(aspect_ratio="bogus")
        # Sanity: the constant matches the live server's enum of 8 values.
        assert "16:9 (Widescreen)" in RESOLUTION_SELECTOR_ASPECT_RATIOS
        assert len(RESOLUTION_SELECTOR_ASPECT_RATIOS) == 8

    def test_node_connect(self) -> None:
        """Node.connect wires inputs to source node outputs."""
        wf = Workflow.new()
        src = wf.add("CheckpointLoaderSimple")
        dst = wf.add("CLIPTextEncode")
        dst.connect("clip", src, output_index=1)
        assert dst.inputs["clip"] == [src.id, 1]

    def test_node_get_ref(self) -> None:
        """Node.get_ref returns the NodeRef."""
        wf = Workflow.from_api(self.DEMO_JSON)
        node = wf.get("49")
        ref = node.get_ref("width")
        assert ref is not None
        assert ref.node_id == "79"
        assert ref.output_index == 0

    def test_node_get_ref_literal(self) -> None:
        """Node.get_ref returns None for literal inputs."""
        wf = Workflow.from_api(self.DEMO_JSON)
        node = wf.get("49")
        assert node.get_ref("batch_size") is None

    def test_node_to_api(self) -> None:
        """Node.to_api serializes to ComfyUI API format."""
        node = Node(id="1", type="KSampler", inputs={"seed": 42, "model": ["2", 0]}, title="Sampler")
        d = node.to_api()
        assert d == {
            "inputs": {"seed": 42, "model": ["2", 0]},
            "class_type": "KSampler",
            "_meta": {"title": "Sampler"},
        }

    def test_node_to_api_no_title(self) -> None:
        """Node.to_api omits _meta when title is empty."""
        node = Node(id="1", type="VAEDecode")
        d = node.to_api()
        assert "_meta" not in d

    def test_repr(self) -> None:
        """Repr includes node ID and type."""
        node = Node(id="42", type="CheckpointLoaderSimple", title="Load Checkpoint")
        assert "42" in repr(node)
        assert "CheckpointLoaderSimple" in repr(node)
        assert "Load Checkpoint" in repr(node)

    def test_workflow_repr(self) -> None:
        """Workflow repr includes node count."""
        wf = Workflow.from_api(self.DEMO_JSON)
        assert "7 nodes" in repr(wf)


# ======================================================================
# FrameAspect tests (moved from fabricatio-novel)
# ======================================================================


class TestFrameAspect:
    """Tests for the FrameAspect StrEnum — values must match ComfyUI tokens."""

    def test_all_values_verbatim(self) -> None:
        """Each FrameAspect value is the exact ComfyUI ResolutionSelector token."""
        assert FrameAspect.SQUARE.value == "1:1 (Square)"
        assert FrameAspect.PHOTO.value == "3:2 (Photo)"
        assert FrameAspect.PORTRAIT_PHOTO.value == "2:3 (Portrait Photo)"
        assert FrameAspect.PORTRAIT_STANDARD.value == "3:4 (Portrait Standard)"
        assert FrameAspect.STANDARD.value == "4:3 (Standard)"
        assert FrameAspect.WIDESCREEN_PORTRAIT.value == "9:16 (Portrait Widescreen)"
        assert FrameAspect.WIDESCREEN.value == "16:9 (Widescreen)"
        assert FrameAspect.ULTRAWIDE.value == "21:9 (Ultrawide)"

    def test_ratio_method(self) -> None:
        """Each FrameAspect exposes a numeric (w, h) ratio for the literal-dimension fallback."""
        assert FrameAspect.SQUARE.ratio == (1, 1)
        assert FrameAspect.PHOTO.ratio == (3, 2)
        assert FrameAspect.PORTRAIT_PHOTO.ratio == (2, 3)
        assert FrameAspect.PORTRAIT_STANDARD.ratio == (3, 4)
        assert FrameAspect.STANDARD.ratio == (4, 3)
        assert FrameAspect.WIDESCREEN_PORTRAIT.ratio == (9, 16)
        assert FrameAspect.WIDESCREEN.ratio == (16, 9)
        assert FrameAspect.ULTRAWIDE.ratio == (21, 9)

    def test_member_count(self) -> None:
        """Exactly 8 ComfyUI tokens exposed."""
        assert len(FrameAspect) == 8

    def test_matches_resolution_selector_enum(self) -> None:
        """FrameAspect values exactly match RESOLUTION_SELECTOR_ASPECT_RATIOS."""
        enum_values = {m.value for m in FrameAspect}
        server_values = set(RESOLUTION_SELECTOR_ASPECT_RATIOS)
        assert enum_values == server_values, (
            f"FrameAspect mismatch: missing {enum_values - server_values}, extra {server_values - enum_values}"
        )


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


# ======================================================================
# Model tests
# ======================================================================


class TestModels:
    """Model unit tests."""

    def test_node_ref_to_list(self) -> None:
        """Convert node reference to ComfyUI link list."""
        ref = ComfyuiNodeRef(node_id="3", output_index=0)
        assert ref.to_list() == ["3", 0]

    def test_node_ref_default_index(self) -> None:
        """Node reference defaults to output index 0."""
        ref = ComfyuiNodeRef(node_id="5")
        assert ref.output_index == 0

    def test_output_image_url_path(self) -> None:
        """Output image URL path encodes all fields."""
        img = ComfyuiOutputImage(filename="test.png", subfolder="sub", type="output")
        assert "filename=test.png" in img.url_path
        assert "subfolder=sub" in img.url_path
        assert "type=output" in img.url_path

    def test_execution_result_all_images(self) -> None:
        """Flatten images from multiple output nodes."""
        result = ComfyuiExecutionResult(
            prompt_id="abc",
            outputs={
                "9": [ComfyuiOutputImage(filename="img1.png"), ComfyuiOutputImage(filename="img2.png")],
                "12": [ComfyuiOutputImage(filename="img3.png")],
            },
            status="completed",
        )
        assert len(result.all_images) == 3
        assert result.succeeded is True

    def test_execution_result_succeeded_with_success_status(self) -> None:
        """ComfyUI returns status_str='success' (not 'completed') — succeeded must accept it."""
        result = ComfyuiExecutionResult(
            prompt_id="abc",
            outputs={"9": [ComfyuiOutputImage(filename="img.png")]},
            status="success",
        )
        assert result.succeeded is True

    def test_execution_result_failed(self) -> None:
        """Failed result exposes error message."""
        result = ComfyuiExecutionResult(prompt_id="abc", status="error", error="CUDA out of memory")
        assert result.succeeded is False
        assert result.error == "CUDA out of memory"

    def test_execution_result_empty(self) -> None:
        """Empty result yields no images and not succeeded."""
        result = ComfyuiExecutionResult(prompt_id="abc")
        assert result.all_images == []
        assert result.succeeded is False

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
# Client tests
# ======================================================================


@pytest.mark.asyncio
async def test_generate_flow(tmp_path: Path) -> None:
    """End-to-end flow: queue prompt -> poll history -> download."""
    client = ComfyuiHTTPClient.create(None)
    workflow = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 42,
                "steps": 20,
                "model": ComfyuiNodeRef(node_id="4").to_list(),
                "positive": ComfyuiNodeRef(node_id="6").to_list(),
                "negative": ComfyuiNodeRef(node_id="7").to_list(),
                "latent_image": ComfyuiNodeRef(node_id="5").to_list(),
            },
        },
    }

    mock_history: Dict[str, Any] = {
        "mock-uuid-123": {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {"9": {"images": [{"filename": "ComfyUI_00001_.png", "subfolder": "", "type": "output"}]}},
        }
    }

    with (
        patch.object(client, "post") as mock_post,
        patch.object(client, "get") as mock_get,
        patch.object(client, "get_image") as mock_img,
    ):
        mock_post.return_value = {"prompt_id": "mock-uuid-123", "number": 1}

        async def get_side_effect(path: str, **kwargs: Any) -> Any:
            if path.startswith("/history/"):
                return mock_history
            return {}

        mock_get.side_effect = get_side_effect
        mock_img.return_value = b"fake-image-bytes"

        result = await client.generate(workflow=workflow, download_dir=tmp_path)

        assert result.prompt_id == "mock-uuid-123"
        assert result.succeeded is True
        assert len(result.all_images) == 1
        assert result.all_images[0].filename == "ComfyUI_00001_.png"
        mock_img.assert_called_once()


@pytest.mark.asyncio
async def test_generate_accepts_workflow() -> None:
    """queue_prompt accepts a Workflow and converts it to dict."""
    wf = Workflow.from_api({"3": {"class_type": "KSampler", "inputs": {"seed": 42}, "_meta": {"title": "Sampler"}}})

    client = ComfyuiHTTPClient.create(None)

    with patch.object(client, "post") as mock_post:
        mock_post.return_value = {"prompt_id": "pid-1", "number": 1}

        await client.queue_prompt(wf)
        call_json = mock_post.call_args.kwargs["json_data"]
        assert call_json["prompt"]["3"]["class_type"] == "KSampler"


@pytest.mark.asyncio
async def test_generate_timeout() -> None:
    """Verify timeout raises when polling fails to complete."""
    client = ComfyuiHTTPClient.create(None)

    with (
        patch.object(client, "post", return_value={"prompt_id": "timeout-uuid"}),
        patch.object(client, "get", return_value={}),
        pytest.raises(TimeoutError),
    ):
        await client.generate(
            workflow={"3": {"class_type": "KSampler", "inputs": {}}},
            timeout=0.2,
        )


@pytest.mark.asyncio
async def test_upload_image(tmp_path: Path) -> None:
    """Upload a local image file and verify the typed response."""
    client = ComfyuiHTTPClient.create(None)

    with patch.object(client, "upload") as mock_upload:
        mock_upload.return_value = {"name": "test.png", "subfolder": "input"}

        fake_img = tmp_path / "test.png"
        fake_img.write_bytes(b"fake-png-content")

        result = await client.upload_image(fake_img)
        assert result.name == "test.png"
        assert isinstance(result, UploadResponse)
        mock_upload.assert_called_once()


@pytest.mark.asyncio
async def test_queue_returns_typed() -> None:
    """queue_prompt returns a PromptResponse, not a raw dict."""
    client = ComfyuiHTTPClient.create(None)

    with patch.object(client, "post", return_value={"prompt_id": "abc", "number": 3, "node_errors": {}}):
        resp = await client.queue_prompt({"1": {"class_type": "VAELoader", "inputs": {}}})
        assert isinstance(resp, PromptResponse)
        assert resp.prompt_id == "abc"


@pytest.mark.asyncio
async def test_queue_accepts_workflow() -> None:
    """queue_prompt accepts a Workflow and auto-injects client_id."""
    client = ComfyuiHTTPClient.create(None)
    wf = Workflow.from_api({"1": {"class_type": "VAELoader", "inputs": {}}})

    with patch.object(client, "post", return_value={"prompt_id": "abc", "number": 1}) as mock_post:
        await client.queue_prompt(wf, front=True)
        call_json = mock_post.call_args.kwargs["json_data"]
        assert call_json["prompt"] == {"1": {"class_type": "VAELoader", "inputs": {}}}
        assert call_json["client_id"] == client.client_id
        assert call_json["front"] is True


@pytest.mark.asyncio
async def test_get_history_returns_typed() -> None:
    """get_history returns a HistoryEntry for a known prompt id."""
    client = ComfyuiHTTPClient.create(None)

    raw = {
        "pid-1": {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {"9": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}},
        }
    }
    with patch.object(client, "get", return_value=raw):
        entry = await client.get_history("pid-1")
        assert isinstance(entry, HistoryEntry)
        assert entry.status.status_str == "completed"


@pytest.mark.asyncio
async def test_get_history_missing() -> None:
    """get_history returns None for a nonexistent prompt id."""
    client = ComfyuiHTTPClient.create(None)

    with patch.object(client, "get", return_value={}):
        entry = await client.get_history("nonexistent")
        assert entry is None


@pytest.mark.asyncio
async def test_queue_info_typed() -> None:
    """get_queue_info returns a typed QueueInfo object."""
    client = ComfyuiHTTPClient.create(None)

    raw = {"queue_running": [], "queue_pending": [[1, "pid", {}, {}, []]]}
    with patch.object(client, "get", return_value=raw):
        info = await client.get_queue_info()
        assert isinstance(info, QueueInfo)
        assert len(info.queue_pending) == 1


@pytest.mark.asyncio
async def test_client_id_uses_base_url() -> None:
    """client_id is derived from the configured base_url."""
    c1 = ComfyuiHTTPClient.create(None)
    c2 = ComfyuiHTTPClient.create(None)
    assert c1.client_id == c2.client_id
    assert c1.client_id == comfyui_config.base_url.rstrip("/").lower()


@pytest.mark.asyncio
async def test_wait_for_completion_polling() -> None:
    """wait_for_completion uses HTTP polling."""
    client = ComfyuiHTTPClient.create(None)

    raw = {
        "pid-1": {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {},
        }
    }
    with patch.object(client, "get", return_value=raw):
        result = await client.wait_for_completion("pid-1", poll_interval=0.01, timeout=5.0)
        assert result.prompt_id == "pid-1"
        assert result.status == "completed"


# ======================================================================
# Batch capability tests (via Comfyui mixin)
# ======================================================================


class _BatchRole(Comfyui):
    """Concrete role for testing batch Comfyui methods."""


@pytest.mark.asyncio
async def test_generate_batch_flow(tmp_path: Path) -> None:
    """Batch acomfyui_generate: queue 3 workflows, poll 3, download all."""
    role = _BatchRole()
    workflows = [{"3": {"class_type": "KSampler", "inputs": {"seed": i}}} for i in range(3)]

    mock_history: Dict[str, Any] = {
        f"pid-{i}": {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {"9": {"images": [{"filename": f"out_{i}.png", "subfolder": "", "type": "output"}]}},
        }
        for i in range(3)
    }

    client = ComfyuiHTTPClient.create(None)
    with (
        patch.object(client, "post") as mock_post,
        patch.object(client, "get") as mock_get,
        patch.object(client, "download_images") as mock_dl,
    ):
        mock_post.side_effect = [{"prompt_id": f"pid-{i}", "number": i} for i in range(3)]

        async def get_side_effect(path: str, **_: Any) -> Any:
            if path.startswith("/history/"):
                return mock_history
            return {}

        mock_get.side_effect = get_side_effect
        mock_dl.return_value = None

        results = await role.acomfyui_generate(
            workflows,
            download_dir=[str(tmp_path / f"ch{i}") for i in range(3)],
        )

        assert len(results) == 3
        for i, r in enumerate(results):
            assert r.prompt_id == f"pid-{i}"
            assert r.succeeded is True
        assert mock_post.call_count == 3
        assert mock_dl.call_count == 3


@pytest.mark.asyncio
async def test_queue_batch() -> None:
    """Batch acomfyui_queue: submit 3 workflows, return 3 PromptResponse."""
    role = _BatchRole()
    workflows = [{"1": {"class_type": "VAELoader", "inputs": {}}} for _ in range(3)]

    client = ComfyuiHTTPClient.create(None)
    with patch.object(client, "post") as mock_post:
        mock_post.side_effect = [{"prompt_id": f"pid-{i}", "number": i, "node_errors": {}} for i in range(3)]
        responses = await role.acomfyui_queue(workflows)

        assert len(responses) == 3
        for i, resp in enumerate(responses):
            assert isinstance(resp, PromptResponse)
            assert resp.prompt_id == f"pid-{i}"
        assert mock_post.call_count == 3


@pytest.mark.asyncio
async def test_retrieve_batch() -> None:
    """Batch acomfyui_retrieve: poll 3 prompt_ids, return 3 results."""
    role = _BatchRole()

    client = ComfyuiHTTPClient.create(None)
    raw = {
        "pid-0": {"status": {"status_str": "completed", "completed": True}, "outputs": {}},
        "pid-1": {"status": {"status_str": "completed", "completed": True}, "outputs": {}},
        "pid-2": {"status": {"status_str": "completed", "completed": True}, "outputs": {}},
    }
    with patch.object(client, "get") as mock_get:

        async def get_side_effect(path: str, **_: Any) -> Any:
            if path.startswith("/history/"):
                return raw
            return {}

        mock_get.side_effect = get_side_effect

        results = await role.acomfyui_retrieve(["pid-0", "pid-1", "pid-2"], poll_interval=0.01, timeout=5.0)

        assert len(results) == 3
        for i, r in enumerate(results):
            assert r.prompt_id == f"pid-{i}"
            assert r.status == "completed"


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
    _first_checkpoint() is None, reason="No checkpoints installed on ComfyUI server"
)


def _fresh_client() -> "ComfyuiHTTPClient":
    """Build an uncached client bound to the current pytest-asyncio event loop.

    ``ComfyuiHTTPClient.create`` is ``@lru_cache``-backed; reusing it across the
    separate event loops pytest-asyncio spins up per test raises
    ``RuntimeError: Event loop is closed`` from httpx. Integration tests build a
    fresh client and call :meth:`aclose` to keep the connection pool per-loop.
    """
    import httpx
    from fabricatio_core.utils import first_available

    return ComfyuiHTTPClient(
        source=httpx.AsyncClient(
            base_url=first_available((None, comfyui_config.base_url)).rstrip("/"),
            timeout=httpx.Timeout(comfyui_config.timeout),
        ),
    )


@pytest.mark.asyncio
@_requires_comfyui
@_requires_checkpoint
async def test_integration_queue_and_history(tmp_path: Path) -> None:
    """Integration: queue a valid workflow, poll history, verify result structure."""
    # Minimal valid txt2img workflow; uses first available checkpoint on the live server.
    wf = Workflow.from_api(
        {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": _first_checkpoint()},
            },
            "2": {"class_type": "EmptyLatentImage", "inputs": {"width": 64, "height": 64, "batch_size": 1}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "test", "clip": ["1", 1]}},
            "4": {"class_type": "CLIPTextEncode", "inputs": {"text": "bad", "clip": ["1", 1]}},
            "5": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["1", 0],
                    "positive": ["3", 0],
                    "negative": ["4", 0],
                    "latent_image": ["2", 0],
                    "seed": 1,
                    "steps": 1,
                    "cfg": 7.0,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                },
            },
            "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
            "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "test"}},
        }
    )

    client = _fresh_client()
    try:
        resp = await client.queue_prompt(wf)
        assert resp.prompt_id, "Expected a non-empty prompt_id"

        result = await client.wait_for_completion(resp.prompt_id, poll_interval=0.5, timeout=120.0)
        assert result.prompt_id == resp.prompt_id
        assert result.status in ("completed", "success")
    finally:
        await client.source.aclose()


@pytest.mark.asyncio
@_requires_comfyui
@_requires_checkpoint
async def test_integration_generate_with_download(tmp_path: Path) -> None:
    """Integration: end-to-end generate with a simple txt2img workflow."""
    wf = Workflow.from_api(
        {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": _first_checkpoint()},
            },
            "2": {"class_type": "EmptyLatentImage", "inputs": {"width": 256, "height": 256, "batch_size": 1}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "a cute cat", "clip": ["1", 1]}},
            "4": {"class_type": "CLIPTextEncode", "inputs": {"text": "bad quality", "clip": ["1", 1]}},
            "5": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["1", 0],
                    "positive": ["3", 0],
                    "negative": ["4", 0],
                    "latent_image": ["2", 0],
                    "seed": 42,
                    "steps": 5,
                    "cfg": 7.0,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                },
            },
            "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
            "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "test"}},
        }
    )

    client = _fresh_client()
    try:
        result = await client.generate(wf, download_dir=tmp_path, timeout=120.0)
    finally:
        await client.source.aclose()

    assert result.succeeded is True

    # Verify image was downloaded to disk
    downloaded = list(tmp_path.glob("*.png"))
    assert len(downloaded) >= 1
    assert downloaded[0].stat().st_size > 0
