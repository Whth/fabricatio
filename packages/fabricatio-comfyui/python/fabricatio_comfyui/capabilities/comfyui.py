"""ComfyUI capability mixin.

Mix into a Role to gain ComfyUI interaction methods.  Clients are shared
via :func:`~fabricatio_comfyui.pool.get_client` — no per-instance state.
"""

from typing import TYPE_CHECKING, Any, Dict, Unpack

from fabricatio_core.journal import logger

from fabricatio_comfyui.pool import get_client

if TYPE_CHECKING:
    from pathlib import Path

    from fabricatio_comfyui.models.comfyui import (
        ComfyuiExecutionResult,
        HistoryEntry,
        PromptResponse,
        QueueInfo,
        UploadResponse,
    )
    from fabricatio_comfyui.models.kwargs_types import (
        GenerateKwargs,
        PollKwargs,
        QueueKwargs,
        UploadKwargs,
        ViewImageKwargs,
    )
    from fabricatio_comfyui.models.workflow import Workflow

__all__ = ["Comfyui"]


class Comfyui:
    """ComfyUI capability mixin — delegates to a pooled :class:`ComfyuiClient`."""

    # ------------------------------------------------------------------
    # Delegated API surface
    # ------------------------------------------------------------------

    async def comfyui_queue_prompt(
        self,
        workflow: "Dict[str, Any] | Workflow",
        **kwargs: "Unpack[QueueKwargs]",
    ) -> "PromptResponse":
        """Submit a workflow graph for execution."""
        resp = await get_client().queue_prompt(workflow, **kwargs)
        logger.info(f"ComfyUI prompt queued: {resp.prompt_id}")
        return resp

    async def comfyui_get_queue_info(self) -> "QueueInfo":
        """Get current queue status."""
        return await get_client().get_queue_info()

    async def comfyui_get_history(self, prompt_id: str) -> "HistoryEntry | None":
        """Get execution history for a specific prompt."""
        return await get_client().get_history(prompt_id)

    async def comfyui_wait_for_completion(
        self,
        prompt_id: str,
        **kwargs: "Unpack[PollKwargs]",
    ) -> "ComfyuiExecutionResult":
        """Poll until a prompt completes or fails."""
        return await get_client().wait_for_completion(prompt_id, **kwargs)

    async def comfyui_get_image(
        self,
        filename: str,
        **kwargs: "Unpack[ViewImageKwargs]",
    ) -> bytes:
        """Download a generated image."""
        data = await get_client().get_image(filename, **kwargs)
        logger.info(f"Downloaded image: {filename}")
        return data

    async def comfyui_upload_image(
        self,
        image_path: "str | Path",
        **kwargs: "Unpack[UploadKwargs]",
    ) -> "UploadResponse":
        """Upload an image to the server."""
        resp = await get_client().upload_image(image_path, **kwargs)
        logger.info(f"Uploaded image -> {resp.name}")
        return resp

    async def comfyui_interrupt(self) -> None:
        """Interrupt the currently running workflow."""
        await get_client().interrupt()
        logger.info("ComfyUI execution interrupted")

    async def comfyui_generate(
        self,
        workflow: "Dict[str, Any] | Workflow",
        **kwargs: "Unpack[GenerateKwargs]",
    ) -> "ComfyuiExecutionResult":
        """Queue a workflow, wait for completion via HTTP polling, optionally download images."""
        logger.info("Starting ComfyUI image generation")
        result = await get_client().generate(workflow, **kwargs)
        if result.succeeded:
            logger.info(f"ComfyUI generation completed: {len(result.all_images)} images")
        else:
            logger.error(f"ComfyUI generation failed: {result.error}")
        return result
