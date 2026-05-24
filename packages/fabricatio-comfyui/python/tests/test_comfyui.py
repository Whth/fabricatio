"""Tests for the fabricatio-comfyui subpackage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict
from unittest.mock import patch

import pytest
from fabricatio_comfyui import (
    ComfyuiExecutionResult,
    ComfyuiNodeRef,
    ComfyuiOutputImage,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestModels:
    """Model unit tests."""

    def test_node_ref_to_list(self) -> None:
        """Node ref serializes to [node_id, output_index]."""
        ref = ComfyuiNodeRef(node_id="3", output_index=0)
        assert ref.to_list() == ["3", 0]

    def test_node_ref_default_index(self) -> None:
        """Output index defaults to 0."""
        ref = ComfyuiNodeRef(node_id="5")
        assert ref.output_index == 0

    def test_output_image_url_path(self) -> None:
        """URL path contains filename, subfolder, and type."""
        img = ComfyuiOutputImage(filename="test.png", subfolder="sub", type="output")
        assert "filename=test.png" in img.url_path
        assert "subfolder=sub" in img.url_path
        assert "type=output" in img.url_path

    def test_execution_result_all_images(self) -> None:
        """All images are flattened across nodes."""
        result = ComfyuiExecutionResult(
            prompt_id="abc",
            outputs={
                "9": [
                    ComfyuiOutputImage(filename="img1.png"),
                    ComfyuiOutputImage(filename="img2.png"),
                ],
                "12": [
                    ComfyuiOutputImage(filename="img3.png"),
                ],
            },
            status="completed",
        )
        assert len(result.all_images) == 3
        assert result.succeeded is True

    def test_execution_result_failed(self) -> None:
        """Failed execution is reflected in status and error."""
        result = ComfyuiExecutionResult(
            prompt_id="abc",
            status="error",
            error="CUDA out of memory",
        )
        assert result.succeeded is False
        assert result.error == "CUDA out of memory"

    def test_execution_result_empty(self) -> None:
        """Empty execution result has no images and is not succeeded."""
        result = ComfyuiExecutionResult(prompt_id="abc")
        assert result.all_images == []
        assert result.succeeded is False


@pytest.mark.asyncio
async def test_comfyui_generate_full_flow(tmp_path: Path) -> None:
    """Integration-style test mocking the HTTP layer end-to-end."""
    from fabricatio_comfyui.capabilities.comfyui import Comfyui

    client = Comfyui()
    workflow = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 42,
                "steps": 20,
                "cfg": 8,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1,
                "model": ComfyuiNodeRef("4").to_list(),
                "positive": ComfyuiNodeRef("6").to_list(),
                "negative": ComfyuiNodeRef("7").to_list(),
                "latent_image": ComfyuiNodeRef("5").to_list(),
            },
        },
    }

    with (
        patch.object(client, "_api_post") as mock_post,
        patch.object(client, "_api_get") as mock_get,
        patch.object(client, "comfyui_get_image") as mock_img,
    ):
        mock_post.return_value = {"prompt_id": "mock-uuid-123", "number": 1}

        mock_history: Dict[str, Any] = {
            "mock-uuid-123": {
                "status": {"status_str": "completed", "completed": True},
                "outputs": {
                    "9": {
                        "images": [
                            {
                                "filename": "ComfyUI_00001_.png",
                                "subfolder": "",
                                "type": "output",
                            }
                        ]
                    }
                },
            }
        }

        async def get_side_effect(path: str, **kwargs: Any) -> Any:
            if path.startswith("/history/"):
                return mock_history
            if path == "/queue":
                return {"running": [], "pending": []}
            return {}

        mock_get.side_effect = get_side_effect
        mock_img.return_value = b"fake-image-bytes"

        result = await client.comfyui_generate(
            workflow=workflow,
            download_dir=tmp_path,
        )

        assert result.prompt_id == "mock-uuid-123"
        assert result.succeeded is True
        assert len(result.all_images) == 1
        assert result.all_images[0].filename == "ComfyUI_00001_.png"
        mock_img.assert_called_once()


@pytest.mark.asyncio
async def test_comfyui_generate_timeout() -> None:
    """Verify timeout raises when prompt never completes."""
    from fabricatio_comfyui.capabilities.comfyui import Comfyui

    client = Comfyui()

    with patch.object(client, "_api_post") as mock_post, patch.object(client, "_api_get", return_value={}):
        mock_post.return_value = {"prompt_id": "timeout-uuid"}

        with pytest.raises(TimeoutError):
            await client.comfyui_generate(
                workflow={"3": {"class_type": "KSampler", "inputs": {}}},
                poll_interval=0.05,
                timeout=0.2,
            )


@pytest.mark.asyncio
async def test_comfyui_upload_image(tmp_path: Path) -> None:
    """Test image upload delegates to _api_upload correctly."""
    from fabricatio_comfyui.capabilities.comfyui import Comfyui

    client = Comfyui()

    with patch.object(client, "_api_upload") as mock_upload:
        mock_upload.return_value = {"name": "test.png", "subfolder": "input"}

        fake_img = tmp_path / "test.png"
        fake_img.write_bytes(b"fake-png-content")

        result = await client.comfyui_upload_image(fake_img)
        assert result["name"] == "test.png"
        mock_upload.assert_called_once()
        assert mock_upload.call_args[0][0] == "/upload/image"
