"""Tests for the fabricatio-comfyui subpackage."""

from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest
from fabricatio_comfyui import (
    ComfyuiClient,
    ComfyuiExecutionResult,
    ComfyuiNodeRef,
    ComfyuiOutputImage,
)
from fabricatio_comfyui.models.comfyui import (
    HistoryEntry,
    PromptResponse,
    QueueInfo,
    UploadResponse,
)


class TestModels:
    """Model unit tests."""

    def test_node_ref_to_list(self) -> None:
        ref = ComfyuiNodeRef(node_id="3", output_index=0)
        assert ref.to_list() == ["3", 0]

    def test_node_ref_default_index(self) -> None:
        ref = ComfyuiNodeRef(node_id="5")
        assert ref.output_index == 0

    def test_output_image_url_path(self) -> None:
        img = ComfyuiOutputImage(filename="test.png", subfolder="sub", type="output")
        assert "filename=test.png" in img.url_path
        assert "subfolder=sub" in img.url_path
        assert "type=output" in img.url_path

    def test_execution_result_all_images(self) -> None:
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
        result = ComfyuiExecutionResult(prompt_id="abc", status="error", error="CUDA out of memory")
        assert result.succeeded is False
        assert result.error == "CUDA out of memory"

    def test_execution_result_empty(self) -> None:
        result = ComfyuiExecutionResult(prompt_id="abc")
        assert result.all_images == []
        assert result.succeeded is False

    def test_history_entry_from_raw(self) -> None:
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
        entry = HistoryEntry.from_raw({})
        assert entry.status.status_str == "unknown"
        assert entry.status.completed is False
        assert entry.outputs == {}

    def test_history_entry_from_raw_failed(self) -> None:
        raw = {"status": {"status_str": "error", "completed": True, "exception": "CUDA OOM"}, "outputs": {}}
        entry = HistoryEntry.from_raw(raw)
        assert entry.status.status_str == "error"
        assert entry.status.exception == "CUDA OOM"

    def test_queue_info_from_raw(self) -> None:
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
        info = QueueInfo.from_raw({})
        assert info.queue_running == []
        assert info.queue_pending == []

    def test_upload_response_from_raw(self) -> None:
        resp = UploadResponse.from_raw({"name": "test.png", "subfolder": "input", "type": "input"})
        assert resp.name == "test.png"
        assert resp.subfolder == "input"

    def test_prompt_response_fields(self) -> None:
        resp = PromptResponse(prompt_id="uuid-123", number=5)
        assert resp.prompt_id == "uuid-123"
        assert resp.number == 5
        assert resp.node_errors == {}


@pytest.mark.asyncio
async def test_generate_full_flow(tmp_path: Path) -> None:
    """End-to-end flow: queue prompt -> poll history -> download image."""
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

    with (
        patch.object(client, "_post") as mock_post,
        patch.object(client, "_get") as mock_get,
        patch.object(client, "get_image") as mock_img,
    ):
        mock_post.return_value = {"prompt_id": "mock-uuid-123", "number": 1}

        mock_history: Dict[str, Any] = {
            "mock-uuid-123": {
                "status": {"status_str": "completed", "completed": True},
                "outputs": {
                    "9": {"images": [{"filename": "ComfyUI_00001_.png", "subfolder": "", "type": "output"}]}
                },
            }
        }

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
async def test_generate_timeout() -> None:
    """Verify timeout raises when prompt never completes."""
    client = ComfyuiClient()

    with patch.object(client, "_post") as mock_post, patch.object(client, "_get", return_value={}):
        mock_post.return_value = {"prompt_id": "timeout-uuid"}

        with pytest.raises(TimeoutError):
            await client.generate(
                workflow={"3": {"class_type": "KSampler", "inputs": {}}},
                poll_interval=0.05,
                timeout=0.2,
            )


@pytest.mark.asyncio
async def test_upload_image(tmp_path: Path) -> None:
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
    client = ComfyuiClient()

    with patch.object(client, "_post", return_value={"prompt_id": "abc", "number": 3, "node_errors": {}}):
        resp = await client.queue_prompt({"1": {"class_type": "VAELoader", "inputs": {}}})
        assert isinstance(resp, PromptResponse)
        assert resp.prompt_id == "abc"


@pytest.mark.asyncio
async def test_get_history_returns_typed() -> None:
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
    client = ComfyuiClient()

    with patch.object(client, "_get", return_value={}):
        entry = await client.get_history("nonexistent")
        assert entry is None


@pytest.mark.asyncio
async def test_queue_info_typed() -> None:
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
async def test_generate_request_uses_model() -> None:
    """Verify queue_prompt sends a PromptRequest, not a raw dict."""
    client = ComfyuiClient()

    with patch.object(client, "_post", return_value={"prompt_id": "x"}) as mock_post:
        await client.queue_prompt({"1": {"class_type": "KSampler", "inputs": {}}}, client_id="ws-1", front=True)
        call_json = mock_post.call_args.kwargs["json"]
        assert call_json["prompt"] == {"1": {"class_type": "KSampler", "inputs": {}}}
        assert call_json["client_id"] == "ws-1"
        assert call_json["front"] is True
