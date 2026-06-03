"""ComfyUI capability mixin.

Holds a :class:`ComfyuiClient` instance and delegates every API call to it.
Mix into a Role to gain ComfyUI interaction methods.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from fabricatio_core.journal import logger
from pydantic import PrivateAttr

from fabricatio_comfyui.client import ComfyuiClient
from fabricatio_comfyui.models.comfyui import (
    ComfyuiExecutionResult,
    HistoryEntry,
    PromptResponse,
    QueueInfo,
    UploadResponse,
)

__all__ = ["Comfyui"]


class Comfyui:
    """ComfyUI capability mixin — delegates to a :class:`ComfyuiClient`."""

    _client: Optional[ComfyuiClient] = PrivateAttr(None)

    @property
    def comfyui(self) -> ComfyuiClient:
        """Return the underlying client, creating lazily if needed."""
        if self._client is None:
            self._client = ComfyuiClient.cached()
        return self._client

    # ------------------------------------------------------------------
    # Delegated API surface
    # ------------------------------------------------------------------

    async def comfyui_queue_prompt(
        self,
        workflow: Dict[str, Any],
        client_id: Optional[str] = None,
        front: bool = False,
    ) -> PromptResponse:
        """Submit a workflow graph for execution."""
        resp = await self.comfyui.queue_prompt(workflow, client_id=client_id, front=front)
        logger.info(f"ComfyUI prompt queued: {resp.prompt_id}")
        return resp

    async def comfyui_get_queue_info(self) -> QueueInfo:
        """Get current queue status."""
        return await self.comfyui.get_queue_info()

    async def comfyui_get_history(self, prompt_id: str) -> Optional[HistoryEntry]:
        """Get execution history for a specific prompt."""
        return await self.comfyui.get_history(prompt_id)

    async def comfyui_wait_for_completion(
        self,
        prompt_id: str,
        poll_interval: float = 1.0,
        timeout: Optional[float] = None,
    ) -> ComfyuiExecutionResult:
        """Poll until a prompt completes or fails."""
        return await self.comfyui.wait_for_completion(prompt_id, poll_interval=poll_interval, timeout=timeout)

    async def comfyui_get_image(
        self,
        filename: str,
        subfolder: str = "",
        image_type: str = "output",
    ) -> bytes:
        """Download a generated image."""
        data = await self.comfyui.get_image(filename, subfolder=subfolder, image_type=image_type)
        logger.info(f"Downloaded image: {filename}")
        return data

    async def comfyui_upload_image(
        self,
        image_path: str | Path,
        image_type: str = "input",
        overwrite: bool = True,
    ) -> UploadResponse:
        """Upload an image to the server."""
        resp = await self.comfyui.upload_image(image_path, image_type=image_type, overwrite=overwrite)
        logger.info(f"Uploaded image -> {resp.name}")
        return resp

    async def comfyui_interrupt(self) -> None:
        """Interrupt the currently running workflow."""
        await self.comfyui.interrupt()
        logger.info("ComfyUI execution interrupted")

    async def comfyui_generate(
        self,
        workflow: Dict[str, Any],
        download_dir: Optional[str | Path] = None,
        client_id: Optional[str] = None,
        poll_interval: float = 1.0,
        timeout: Optional[float] = None,
    ) -> ComfyuiExecutionResult:
        """Queue a workflow, wait for completion, optionally download images."""
        logger.info("Starting ComfyUI image generation")
        result = await self.comfyui.generate(
            workflow,
            download_dir=download_dir,
            client_id=client_id,
            poll_interval=poll_interval,
            timeout=timeout,
        )
        if result.succeeded:
            logger.info(f"ComfyUI generation completed: {len(result.all_images)} images")
        else:
            logger.error(f"ComfyUI generation failed: {result.error}")
        return result
