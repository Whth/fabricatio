"""Tests for the fabricatio-comfyui subpackage."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, ClassVar, Dict
from unittest.mock import AsyncMock, patch

import pytest
from fabricatio_comfyui import (
    ComfyNode,
    ComfyuiClient,
    ComfyuiExecutionResult,
    ComfyuiNodeRef,
    ComfyuiOutputImage,
    WorkflowBuilder,
)
from fabricatio_comfyui.models.comfyui import (
    HistoryEntry,
    PromptResponse,
    QueueInfo,
    UploadResponse,
)


# ======================================================================
# WorkflowBuilder tests
# ======================================================================


class TestWorkflowBuilder:
    """WorkflowBuilder and ComfyNode unit tests."""

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

    def test_from_json_preserves_structure(self) -> None:
        """from_json round-trips the demo JSON exactly."""
        wb = WorkflowBuilder.from_json(self.DEMO_JSON)
        result = wb.to_dict()
        assert result == self.DEMO_JSON

    def test_from_json_preserves_node_ids(self) -> None:
        """from_json keeps original node IDs."""
        wb = WorkflowBuilder.from_json(self.DEMO_JSON)
        assert wb.node_ids == ["42", "46", "49", "50", "51", "79", "85"]

    def test_from_json_preserves_node_references(self) -> None:
        """from_json preserves [node_id, output_index] references in inputs."""
        wb = WorkflowBuilder.from_json(self.DEMO_JSON)
        node = wb.get_node("49")
        assert node.inputs["width"] == ["79", 0]
        assert node.inputs["height"] == ["79", 1]

    def test_from_json_preserves_meta(self) -> None:
        """from_json preserves _meta dicts."""
        wb = WorkflowBuilder.from_json(self.DEMO_JSON)
        assert wb.get_node("42").meta == {"title": "Load Checkpoint"}

    def test_from_file(self, tmp_path: Path) -> None:
        """from_file loads from a .json file."""
        p = tmp_path / "test.json"
        p.write_text(json.dumps(self.DEMO_JSON), encoding="utf-8")
        wb = WorkflowBuilder.from_file(p)
        assert wb.to_dict() == self.DEMO_JSON

    def test_add_node(self) -> None:
        """add_node creates a node with auto-incremented ID."""
        wb = WorkflowBuilder()
        n1 = wb.add_node("KSampler", title="Sampler", inputs={"seed": 42})
        n2 = wb.add_node("VAEDecode")
        assert n1.node_id == "1"
        assert n2.node_id == "2"
        assert len(wb.nodes) == 2

    def test_add_node_to_loaded_workflow(self) -> None:
        """add_node on a loaded workflow uses the next available ID."""
        wb = WorkflowBuilder.from_json(self.DEMO_JSON)
        new_node = wb.add_node("SaveImage")
        assert new_node.node_id == "86"  # max existing is 85

    def test_get_node(self) -> None:
        """get_node returns the correct node."""
        wb = WorkflowBuilder.from_json(self.DEMO_JSON)
        node = wb.get_node("42")
        assert node.class_type == "CheckpointLoaderSimple"

    def test_get_node_missing(self) -> None:
        """get_node raises KeyError for missing node."""
        wb = WorkflowBuilder.from_json(self.DEMO_JSON)
        with pytest.raises(KeyError):
            wb.get_node("999")

    def test_nodes_by_type(self) -> None:
        """nodes_by_type finds all nodes of a given class_type."""
        wb = WorkflowBuilder.from_json(self.DEMO_JSON)
        clip_nodes = wb.nodes_by_type("CLIPTextEncode")
        assert len(clip_nodes) == 2
        assert clip_nodes[0].node_id == "50"
        assert clip_nodes[1].node_id == "51"

    def test_remove_node(self) -> None:
        """remove_node removes the node and disconnects references."""
        wb = WorkflowBuilder.from_json(self.DEMO_JSON)
        wb.remove_node("79")  # ResolutionSelector
        assert "79" not in wb.node_ids
        # Node 49 had references to 79 — those should be gone
        node_49 = wb.get_node("49")
        assert "width" not in node_49.inputs
        assert "height" not in node_49.inputs

    def test_set_checkpoint(self) -> None:
        """set_checkpoint updates the checkpoint name."""
        wb = WorkflowBuilder.from_json(self.DEMO_JSON)
        wb.set_checkpoint("new_model.safetensors")
        assert wb.get_node("42").inputs["ckpt_name"] == "new_model.safetensors"

    def test_set_checkpoint_specific_node(self) -> None:
        """set_checkpoint with node_id targets a specific node."""
        wb = WorkflowBuilder.from_json(self.DEMO_JSON)
        wb.set_checkpoint("model_v2.safetensors", node_id="42")
        assert wb.get_node("42").inputs["ckpt_name"] == "model_v2.safetensors"

    def test_set_checkpoint_missing(self) -> None:
        """set_checkpoint raises if no matching node exists."""
        wb = WorkflowBuilder()
        with pytest.raises(KeyError, match="No node with class_type"):
            wb.set_checkpoint("model.safetensors")

    def test_set_positive_prompt(self) -> None:
        """set_positive_prompt updates the first CLIPTextEncode node."""
        wb = WorkflowBuilder.from_json(self.DEMO_JSON)
        wb.set_positive_prompt("a beautiful landscape")
        assert wb.get_node("50").inputs["text"] == "a beautiful landscape"

    def test_set_negative_prompt(self) -> None:
        """set_negative_prompt updates the second CLIPTextEncode node."""
        wb = WorkflowBuilder.from_json(self.DEMO_JSON)
        wb.set_negative_prompt("bad quality, blurry")
        assert wb.get_node("51").inputs["text"] == "bad quality, blurry"

    def test_set_sampler_ksampler_advanced(self) -> None:
        """set_sampler updates KSamplerAdvanced parameters."""
        wb = WorkflowBuilder.from_json(self.DEMO_JSON)
        wb.set_sampler(seed=999, steps=30, cfg=7.5, sampler_name="ddim")
        node = wb.get_node("85")
        assert node.inputs["noise_seed"] == 999
        assert node.inputs["steps"] == 30
        assert node.inputs["cfg"] == 7.5
        assert node.inputs["sampler_name"] == "ddim"

    def test_set_sampler_partial_update(self) -> None:
        """set_sampler only updates provided parameters."""
        wb = WorkflowBuilder.from_json(self.DEMO_JSON)
        original_steps = wb.get_node("85").inputs["steps"]
        wb.set_sampler(cfg=12.0)
        assert wb.get_node("85").inputs["cfg"] == 12.0
        assert wb.get_node("85").inputs["steps"] == original_steps

    def test_set_resolution(self) -> None:
        """set_resolution updates EmptyLatentImage dimensions."""
        wb = WorkflowBuilder()
        wb.add_node("EmptyLatentImage", inputs={"width": 512, "height": 512, "batch_size": 1})
        wb.set_resolution(width=1024, height=768)
        node = wb.nodes_by_type("EmptyLatentImage")[0]
        assert node.inputs["width"] == 1024
        assert node.inputs["height"] == 768

    def test_comfy_node_connect(self) -> None:
        """ComfyNode.connect wires inputs to source node outputs."""
        wb = WorkflowBuilder()
        src = wb.add_node("CheckpointLoaderSimple")
        dst = wb.add_node("CLIPTextEncode")
        dst.connect("clip", src, output_index=1)
        assert dst.inputs["clip"] == [src.node_id, 1]

    def test_comfy_node_get_ref(self) -> None:
        """ComfyNode.get_ref returns the node reference tuple."""
        wb = WorkflowBuilder.from_json(self.DEMO_JSON)
        node = wb.get_node("49")
        ref = node.get_ref("width")
        assert ref == ("79", 0)

    def test_comfy_node_get_ref_literal(self) -> None:
        """ComfyNode.get_ref returns None for literal inputs."""
        wb = WorkflowBuilder.from_json(self.DEMO_JSON)
        node = wb.get_node("49")
        assert node.get_ref("batch_size") is None

    def test_comfy_node_to_dict(self) -> None:
        """ComfyNode.to_dict serializes to API format."""
        node = ComfyNode(
            node_id="1",
            class_type="KSampler",
            inputs={"seed": 42, "model": ["2", 0]},
            meta={"title": "Sampler"},
        )
        d = node.to_dict()
        assert d == {
            "inputs": {"seed": 42, "model": ["2", 0]},
            "class_type": "KSampler",
            "_meta": {"title": "Sampler"},
        }

    def test_comfy_node_to_dict_no_meta(self) -> None:
        """ComfyNode.to_dict omits _meta when empty."""
        node = ComfyNode(node_id="1", class_type="VAEDecode")
        d = node.to_dict()
        assert "_meta" not in d

    def test_repr(self) -> None:
        """Repr includes node ID and class type."""
        node = ComfyNode("42", "CheckpointLoaderSimple", meta={"title": "Load Checkpoint"})
        assert "42" in repr(node)
        assert "CheckpointLoaderSimple" in repr(node)
        assert "Load Checkpoint" in repr(node)

    def test_builder_repr(self) -> None:
        """WorkflowBuilder repr includes node count."""
        wb = WorkflowBuilder.from_json(self.DEMO_JSON)
        assert "7 nodes" in repr(wb)


# ======================================================================
# Model tests (kept from original)
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
async def test_generate_ws_flow(tmp_path: Path) -> None:
    """End-to-end flow via WebSocket: queue prompt -> WS wait -> history -> download."""
    client = ComfyuiClient()
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

    mock_ws = AsyncMock()
    # WS recv returns executing messages, then the final one with node=None
    mock_ws.recv = AsyncMock(
        side_effect=[
            json.dumps({"type": "executing", "data": {"node": "3", "prompt_id": "mock-uuid-123"}}),
            json.dumps({"type": "executing", "data": {"node": None, "prompt_id": "mock-uuid-123"}}),
        ]
    )
    mock_ws.ping = AsyncMock()

    mock_history: Dict[str, Any] = {
        "mock-uuid-123": {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {"9": {"images": [{"filename": "ComfyUI_00001_.png", "subfolder": "", "type": "output"}]}},
        }
    }

    with (
        patch.object(client, "_post") as mock_post,
        patch.object(client, "_get") as mock_get,
        patch.object(client, "get_image") as mock_img,
        patch.object(client, "_ensure_ws", return_value=mock_ws),
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
async def test_generate_accepts_workflow_builder(tmp_path: Path) -> None:
    """generate() accepts a WorkflowBuilder and converts it to dict."""
    wb = WorkflowBuilder.from_json(
        {"3": {"class_type": "KSampler", "inputs": {"seed": 42}, "_meta": {"title": "Sampler"}}}
    )

    client = ComfyuiClient()
    mock_ws = AsyncMock()
    mock_ws.recv = AsyncMock(
        side_effect=[
            json.dumps({"type": "executing", "data": {"node": None, "prompt_id": "pid-1"}}),
        ]
    )
    mock_ws.ping = AsyncMock()

    with (
        patch.object(client, "_post") as mock_post,
        patch.object(client, "_get", return_value={}),
        patch.object(client, "_ensure_ws", return_value=mock_ws),
    ):
        mock_post.return_value = {"prompt_id": "pid-1", "number": 1}

        await client.generate(workflow=wb)
        call_json = mock_post.call_args.kwargs["json_data"]
        assert call_json["prompt"]["3"]["class_type"] == "KSampler"


@pytest.mark.asyncio
async def test_generate_ws_fallback_to_polling(tmp_path: Path) -> None:
    """generate() falls back to HTTP polling when WebSocket fails."""
    client = ComfyuiClient()
    workflow = {"3": {"class_type": "KSampler", "inputs": {"seed": 42}}}

    mock_history: Dict[str, Any] = {
        "pid-fallback": {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {"9": {"images": [{"filename": "img.png", "subfolder": "", "type": "output"}]}},
        }
    }

    with (
        patch.object(client, "_post") as mock_post,
        patch.object(client, "_get") as mock_get,
        patch.object(client, "get_image", return_value=b"img"),
        patch.object(client, "_ensure_ws", side_effect=OSError("Connection refused")),
    ):
        mock_post.return_value = {"prompt_id": "pid-fallback", "number": 1}

        async def get_side_effect(path: str, **kwargs: Any) -> Any:
            if path.startswith("/history/"):
                return mock_history
            return {}

        mock_get.side_effect = get_side_effect

        result = await client.generate(workflow=workflow, download_dir=tmp_path)
        assert result.succeeded is True


@pytest.mark.asyncio
async def test_generate_timeout() -> None:
    """Verify timeout raises when WS and polling both fail to complete."""
    client = ComfyuiClient()

    mock_ws = AsyncMock()
    # WS recv never returns a completion message
    mock_ws.recv = AsyncMock(side_effect=asyncio.TimeoutError)
    mock_ws.ping = AsyncMock()

    with (
        patch.object(client, "_post", return_value={"prompt_id": "timeout-uuid"}),
        patch.object(client, "_get", return_value={}),
        patch.object(client, "_ensure_ws", return_value=mock_ws),
        pytest.raises(TimeoutError),
    ):
        await client.generate(
            workflow={"3": {"class_type": "KSampler", "inputs": {}}},
            timeout=0.2,
        )


@pytest.mark.asyncio
async def test_upload_image(tmp_path: Path) -> None:
    """Upload a local image file and verify the typed response."""
    client = ComfyuiClient()

    with patch.object(client, "_upload") as mock_upload:
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
    client = ComfyuiClient()

    with patch.object(client, "_post", return_value={"prompt_id": "abc", "number": 3, "node_errors": {}}):
        resp = await client.queue_prompt({"1": {"class_type": "VAELoader", "inputs": {}}})
        assert isinstance(resp, PromptResponse)
        assert resp.prompt_id == "abc"


@pytest.mark.asyncio
async def test_queue_accepts_workflow_builder() -> None:
    """queue_prompt accepts a WorkflowBuilder and auto-injects client_id."""
    client = ComfyuiClient()
    wb = WorkflowBuilder.from_json({"1": {"class_type": "VAELoader", "inputs": {}}})

    with patch.object(client, "_post", return_value={"prompt_id": "abc", "number": 1}) as mock_post:
        await client.queue_prompt(wb, front=True)
        call_json = mock_post.call_args.kwargs["json_data"]
        assert call_json["prompt"] == {"1": {"class_type": "VAELoader", "inputs": {}}}
        assert call_json["client_id"] == client.client_id
        assert call_json["front"] is True


@pytest.mark.asyncio
async def test_get_history_returns_typed() -> None:
    """get_history returns a HistoryEntry for a known prompt id."""
    client = ComfyuiClient()

    raw = {
        "pid-1": {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {"9": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}},
        }
    }
    with patch.object(client, "_get", return_value=raw):
        entry = await client.get_history("pid-1")
        assert isinstance(entry, HistoryEntry)
        assert entry.status.status_str == "completed"


@pytest.mark.asyncio
async def test_get_history_missing() -> None:
    """get_history returns None for a nonexistent prompt id."""
    client = ComfyuiClient()

    with patch.object(client, "_get", return_value={}):
        entry = await client.get_history("nonexistent")
        assert entry is None


@pytest.mark.asyncio
async def test_queue_info_typed() -> None:
    """get_queue_info returns a typed QueueInfo object."""
    client = ComfyuiClient()

    raw = {"queue_running": [], "queue_pending": [[1, "pid", {}, {}, []]]}
    with patch.object(client, "_get", return_value=raw):
        info = await client.get_queue_info()
        assert isinstance(info, QueueInfo)
        assert len(info.queue_pending) == 1


@pytest.mark.asyncio
async def test_context_manager() -> None:
    """Verify async with opens and closes the client."""
    client = ComfyuiClient()
    async with client:
        assert client._http is not None
    assert client._http is None


@pytest.mark.asyncio
async def test_client_id_unique() -> None:
    """Each client instance gets a unique client_id."""
    c1 = ComfyuiClient()
    c2 = ComfyuiClient()
    assert c1.client_id != c2.client_id
    assert len(c1.client_id) == 36  # UUID4 format


@pytest.mark.asyncio
async def test_wait_for_completion_polling() -> None:
    """wait_for_completion uses HTTP polling (Method 1 extended)."""
    client = ComfyuiClient()

    raw = {
        "pid-1": {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {},
        }
    }
    with patch.object(client, "_get", return_value=raw):
        result = await client.wait_for_completion("pid-1", poll_interval=0.01, timeout=5.0)
        assert result.prompt_id == "pid-1"
        assert result.status == "completed"
