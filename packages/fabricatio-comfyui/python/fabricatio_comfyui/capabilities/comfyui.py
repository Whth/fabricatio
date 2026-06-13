"""ComfyUI capability mixin.

Mix into a Role to gain ComfyUI interaction methods.  Clients are shared
via :func:`~fabricatio_comfyui.pool.get_client` — no per-instance state.

Predicate-verb methods (``acomfyui_*``) follow the same naming convention as
:class:`fabricatio_core.capabilities.usages.UseLLM` — ``a`` prefix + domain verb.
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
    # Predicate-verb API (acomfyui_*)
    # ------------------------------------------------------------------

    async def acomfyui_generate(
        self,
        workflow: "Dict[str, Any] | Workflow",
        **kwargs: "Unpack[GenerateKwargs]",
    ) -> "ComfyuiExecutionResult":
        """Execute a workflow and return the result.

        Queues the workflow, polls until completion, and optionally downloads
        output images.
        """
        logger.info("Starting ComfyUI image generation")
        result = await get_client().generate(workflow, **kwargs)
        if result.succeeded:
            logger.info(f"ComfyUI generation completed: {len(result.all_images)} images")
        else:
            logger.error(f"ComfyUI generation failed: {result.error}")
        return result

    async def acomfyui_queue(
        self,
        workflow: "Dict[str, Any] | Workflow",
        **kwargs: "Unpack[QueueKwargs]",
    ) -> "PromptResponse":
        """Submit a workflow for execution without waiting."""
        resp = await get_client().queue_prompt(workflow, **kwargs)
        logger.info(f"ComfyUI prompt queued: {resp.prompt_id}")
        return resp

    async def acomfyui_inspect_queue(self) -> "QueueInfo":
        """Fetch the current execution queue state."""
        return await get_client().get_queue_info()

    async def acomfyui_history(self, prompt_id: str) -> "HistoryEntry | None":
        """Retrieve execution history for *prompt_id*."""
        return await get_client().get_history(prompt_id)

    async def acomfyui_retrieve(
        self,
        prompt_id: str,
        **kwargs: "Unpack[PollKwargs]",
    ) -> "ComfyuiExecutionResult":
        """Poll until *prompt_id* completes and return the result."""
        return await get_client().wait_for_completion(prompt_id, **kwargs)

    async def acomfyui_retrieve_image(
        self,
        filename: str,
        **kwargs: "Unpack[ViewImageKwargs]",
    ) -> bytes:
        """Download a single generated image by filename."""
        data = await get_client().get_image(filename, **kwargs)
        logger.info(f"Downloaded image: {filename}")
        return data

    async def acomfyui_upload(
        self,
        image_path: "str | Path",
        **kwargs: "Unpack[UploadKwargs]",
    ) -> "UploadResponse":
        """Upload an image to the server."""
        resp = await get_client().upload_image(image_path, **kwargs)
        logger.info(f"Uploaded image -> {resp.name}")
        return resp

    async def acomfyui_interrupt(self) -> None:
        """Interrupt the currently running workflow."""
        await get_client().interrupt()
        logger.info("ComfyUI execution interrupted")

    # ------------------------------------------------------------------
    # Legacy aliases (deprecated — prefer acomfyui_* methods)
    # ------------------------------------------------------------------

    async def comfyui_generate(
        self,
        workflow: "Dict[str, Any] | Workflow",
        **kwargs: "Unpack[GenerateKwargs]",
    ) -> "ComfyuiExecutionResult":
        """Alias for :meth:`acomfyui_generate`."""
        return await self.acomfyui_generate(workflow, **kwargs)

    async def comfyui_queue_prompt(
        self,
        workflow: "Dict[str, Any] | Workflow",
        **kwargs: "Unpack[QueueKwargs]",
    ) -> "PromptResponse":
        """Alias for :meth:`acomfyui_queue`."""
        return await self.acomfyui_queue(workflow, **kwargs)

    async def comfyui_get_queue_info(self) -> "QueueInfo":
        """Alias for :meth:`acomfyui_inspect_queue`."""
        return await self.acomfyui_inspect_queue()

    async def comfyui_get_history(self, prompt_id: str) -> "HistoryEntry | None":
        """Alias for :meth:`acomfyui_history`."""
        return await self.acomfyui_history(prompt_id)

    async def comfyui_wait_for_completion(
        self,
        prompt_id: str,
        **kwargs: "Unpack[PollKwargs]",
    ) -> "ComfyuiExecutionResult":
        """Alias for :meth:`acomfyui_retrieve`."""
        return await self.acomfyui_retrieve(prompt_id, **kwargs)

    async def comfyui_get_image(
        self,
        filename: str,
        **kwargs: "Unpack[ViewImageKwargs]",
    ) -> bytes:
        """Alias for :meth:`acomfyui_retrieve_image`."""
        return await self.acomfyui_retrieve_image(filename, **kwargs)

    async def comfyui_upload_image(
        self,
        image_path: "str | Path",
        **kwargs: "Unpack[UploadKwargs]",
    ) -> "UploadResponse":
        """Alias for :meth:`acomfyui_upload`."""
        return await self.acomfyui_upload(image_path, **kwargs)

    async def comfyui_interrupt(self) -> None:
        """Alias for :meth:`acomfyui_interrupt`."""
        return await self.acomfyui_interrupt()
