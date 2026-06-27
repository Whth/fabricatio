"""ComfyUI capability mixin.

Mix into a Role to gain ComfyUI interaction methods.  Clients are shared
via :meth:`ComfyuiHTTPClient.create` (``@lru_cache``) — no per-instance state.

Predicate-verb methods (``acomfyui_*``) follow the same naming convention as
:class:`fabricatio_core.capabilities.usages.UseLLM` — ``a`` prefix + domain verb.
"""

from asyncio import gather
from typing import TYPE_CHECKING, Any, Dict, List, Unpack, overload

from fabricatio_core.journal import logger

from fabricatio_comfyui.config import comfyui_config
from fabricatio_comfyui.http_client import ComfyuiHTTPClient

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

    # -- acomfyui_generate: single + batch --

    @overload
    async def acomfyui_generate(
        self,
        workflow: "Dict[str, Any] | Workflow",
        *,
        download_dir: "str | Path | None" = None,
        timeout: float | None = None,
        base_url: str | None = None,
    ) -> "ComfyuiExecutionResult": ...

    @overload
    async def acomfyui_generate(
        self,
        workflow: "List[Dict[str, Any] | Workflow]",
        *,
        download_dir: "list[str | Path | None] | None" = None,
        timeout: float | None = None,
        base_url: str | None = None,
    ) -> "List[ComfyuiExecutionResult]": ...

    async def acomfyui_generate(
        self,
        workflow: "Dict[str, Any] | Workflow | List[Dict[str, Any] | Workflow]",
        *,
        download_dir: "str | Path | None | list[str | Path | None]" = None,
        timeout: float | None = None,
        base_url: str | None = None,
    ) -> "ComfyuiExecutionResult | List[ComfyuiExecutionResult]":
        """Execute one or more workflows: queue all, then poll all, then download."""
        client = ComfyuiHTTPClient.create(base_url)
        effective_timeout = timeout or comfyui_config.timeout

        if isinstance(workflow, list):
            # Phase 1: submit all (parallel HTTP)
            responses: List[PromptResponse] = list(await gather(*(client.queue_prompt(wf) for wf in workflow)))
            logger.info(f"Batch queued {len(responses)} ComfyUI prompts")

            # Phase 2: wait for all (parallel polling)
            results: List[ComfyuiExecutionResult] = list(
                await gather(*(client.wait_for_completion(r.prompt_id, timeout=effective_timeout) for r in responses))
            )

            # Phase 3: download if needed
            if download_dir:
                dirs = download_dir if isinstance(download_dir, list) else [download_dir] * len(results)
                await gather(
                    *(
                        client.download_images(result, d)
                        for result, d in zip(results, dirs, strict=True)
                        if d is not None and result.succeeded
                    )
                )

            succeeded = sum(1 for r in results if r.succeeded)
            logger.info(f"Batch ComfyUI completed: {succeeded}/{len(results)} succeeded")
            return results
        # Single mode — inline queue+wait+download

        resp = await client.queue_prompt(workflow)
        result = await client.wait_for_completion(resp.prompt_id, timeout=effective_timeout)

        if download_dir is not None and result.succeeded:
            await client.download_images(result, download_dir)

        if result.succeeded:
            logger.info(f"ComfyUI generation completed: {len(result.all_images)} images")
        else:
            logger.error(f"ComfyUI generation failed: {result.error}")
        return result

    # -- acomfyui_queue: single + batch --

    @overload
    async def acomfyui_queue(
        self,
        workflow: "Dict[str, Any] | Workflow",
        **kwargs: "Unpack[QueueKwargs]",
    ) -> "PromptResponse": ...

    @overload
    async def acomfyui_queue(
        self,
        workflow: "List[Dict[str, Any] | Workflow]",
        **kwargs: "Unpack[QueueKwargs]",
    ) -> "List[PromptResponse]": ...

    async def acomfyui_queue(
        self,
        workflow: "Dict[str, Any] | Workflow | List[Dict[str, Any] | Workflow]",
        **kwargs: "Unpack[QueueKwargs]",
    ) -> "PromptResponse | List[PromptResponse]":
        """Submit one or more workflows for execution without waiting."""
        if isinstance(workflow, list):
            results = list(
                await gather(*(ComfyuiHTTPClient.create(None).queue_prompt(wf, **kwargs) for wf in workflow))
            )
            for r in results:
                logger.info(f"ComfyUI prompt queued: {r.prompt_id}")
            return results
        resp = await ComfyuiHTTPClient.create(None).queue_prompt(workflow, **kwargs)
        logger.info(f"ComfyUI prompt queued: {resp.prompt_id}")
        return resp

    async def acomfyui_inspect_queue(self) -> "QueueInfo":
        """Fetch the current execution queue state."""
        return await ComfyuiHTTPClient.create(None).get_queue_info()

    async def acomfyui_history(self, prompt_id: str) -> "HistoryEntry | None":
        """Retrieve execution history for *prompt_id*."""
        return await ComfyuiHTTPClient.create(None).get_history(prompt_id)

    # -- acomfyui_retrieve: single + batch --

    @overload
    async def acomfyui_retrieve(
        self,
        prompt_id: str,
        **kwargs: "Unpack[PollKwargs]",
    ) -> "ComfyuiExecutionResult": ...

    @overload
    async def acomfyui_retrieve(
        self,
        prompt_id: "List[str]",
        **kwargs: "Unpack[PollKwargs]",
    ) -> "List[ComfyuiExecutionResult]": ...

    async def acomfyui_retrieve(
        self,
        prompt_id: "str | List[str]",
        **kwargs: "Unpack[PollKwargs]",
    ) -> "ComfyuiExecutionResult | List[ComfyuiExecutionResult]":
        """Poll until one or more prompt_ids complete."""
        if isinstance(prompt_id, list):
            return list(
                await gather(*(ComfyuiHTTPClient.create(None).wait_for_completion(pid, **kwargs) for pid in prompt_id))
            )
        return await ComfyuiHTTPClient.create(None).wait_for_completion(prompt_id, **kwargs)

    async def acomfyui_retrieve_image(
        self,
        filename: str,
        **kwargs: "Unpack[ViewImageKwargs]",
    ) -> bytes:
        """Download a single generated image by filename."""
        data = await ComfyuiHTTPClient.create(None).get_image(filename, **kwargs)
        logger.info(f"Downloaded image: {filename}")
        return data

    async def acomfyui_upload(
        self,
        image_path: "str | Path",
        **kwargs: "Unpack[UploadKwargs]",
    ) -> "UploadResponse":
        """Upload an image to the server."""
        resp = await ComfyuiHTTPClient.create(None).upload_image(image_path, **kwargs)
        logger.info(f"Uploaded image -> {resp.name}")
        return resp

    async def acomfyui_interrupt(self) -> None:
        """Interrupt the currently running workflow."""
        await ComfyuiHTTPClient.create(None).interrupt()
        logger.info("ComfyUI execution interrupted")

    # ------------------------------------------------------------------
    # Legacy aliases (deprecated — prefer acomfyui_* methods)
    # ------------------------------------------------------------------

    async def comfyui_generate(
        self,
        workflow: "Dict[str, Any] | Workflow | List[Dict[str, Any] | Workflow]",
        **kwargs: Any,
    ) -> "ComfyuiExecutionResult | List[ComfyuiExecutionResult]":
        """Alias for :meth:`acomfyui_generate`."""
        return await self.acomfyui_generate(workflow, **kwargs)

    async def comfyui_queue_prompt(
        self,
        workflow: "Dict[str, Any] | Workflow | List[Dict[str, Any] | Workflow]",
        **kwargs: "Unpack[QueueKwargs]",
    ) -> "PromptResponse | List[PromptResponse]":
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
        prompt_id: "str | List[str]",
        **kwargs: "Unpack[PollKwargs]",
    ) -> "ComfyuiExecutionResult | List[ComfyuiExecutionResult]":
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
