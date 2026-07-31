"""ComfyUI capability mixin.

Mix into a Role to gain ComfyUI interaction methods.  Each instance holds
its own :class:`ComfyuiClientBase` (lazily created from
:class:`ComfyuiHTTPClient`), so tests and alternate backends can inject a
client through the ``comfyui_client`` constructor argument — no
``@lru_cache`` global, no ``hasattr`` sniffing.

Predicate-verb methods (``acomfyui_*``) follow the same naming convention as
:class:`fabricatio_core.capabilities.usages.UseLLM` — ``a`` prefix + domain verb.
"""

from asyncio import gather
from typing import TYPE_CHECKING, List, Unpack, overload

from fabricatio_core.journal import logger

from fabricatio_comfyui.config import comfyui_config
from fabricatio_comfyui.http_client import ComfyuiHTTPClient

if TYPE_CHECKING:
    from pathlib import Path

    from fabricatio_comfyui.client_base import ComfyuiClientBase
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
    from fabricatio_comfyui.models.workflow import Workflow, WorkflowDict

__all__ = ["Comfyui"]


class Comfyui:
    """ComfyUI capability mixin — owns a per-instance :class:`ComfyuiClientBase`.

    The client is created lazily on first use from
    :meth:`ComfyuiHTTPClient.create`.  Inject a custom client (e.g. a mock)
    via the ``comfyui_client`` constructor argument.  Call :meth:`close` to
    release the connection pool when the mixin is no longer needed.
    """

    _comfyui_client: "ComfyuiClientBase | None"

    def __init__(self, comfyui_client: "ComfyuiClientBase | None" = None) -> None:
        """Optionally inject a pre-built client; otherwise created lazily."""
        self._comfyui_client = comfyui_client

    @property
    def comfyui_client(self) -> "ComfyuiClientBase":
        """The lazily-created (or injected) :class:`ComfyuiClientBase`."""
        if self._comfyui_client is None:
            self._comfyui_client = ComfyuiHTTPClient.create()
        return self._comfyui_client

    async def close(self) -> None:
        """Close the underlying client if this mixin owns one."""
        if self._comfyui_client is not None:
            await self._comfyui_client.aclose()
            self._comfyui_client = None

    # ------------------------------------------------------------------
    # Predicate-verb API (acomfyui_*)
    # ------------------------------------------------------------------

    # -- acomfyui_generate: single + batch --

    @overload
    async def acomfyui_generate(
        self,
        workflow: "WorkflowDict | Workflow",
        *,
        download_dir: "str | Path | None" = None,
        timeout: float | None = None,
        base_url: str | None = None,
    ) -> "ComfyuiExecutionResult": ...

    @overload
    async def acomfyui_generate(
        self,
        workflow: "List[WorkflowDict | Workflow]",
        *,
        download_dir: "list[str | Path | None] | None" = None,
        timeout: float | None = None,
        base_url: str | None = None,
    ) -> "List[ComfyuiExecutionResult]": ...

    async def acomfyui_generate(
        self,
        workflow: "WorkflowDict | Workflow | List[WorkflowDict | Workflow]",
        *,
        download_dir: "str | Path | None | list[str | Path | None]" = None,
        timeout: float | None = None,
        base_url: str | None = None,
    ) -> "ComfyuiExecutionResult | List[ComfyuiExecutionResult]":
        """Execute one or more workflows: queue all, then poll all, then download."""
        effective_timeout = timeout or comfyui_config.timeout

        if base_url is not None:
            async with ComfyuiHTTPClient.create(base_url) as client:
                return await self._generate_with_client(client, workflow, download_dir, effective_timeout)
        return await self._generate_with_client(self.comfyui_client, workflow, download_dir, effective_timeout)

    async def _generate_with_client(
        self,
        client: "ComfyuiClientBase",
        workflow: "WorkflowDict | Workflow | List[WorkflowDict | Workflow]",
        download_dir: "str | Path | None | list[str | Path | None]",
        effective_timeout: float,
    ) -> "ComfyuiExecutionResult | List[ComfyuiExecutionResult]":
        """Core generation logic — queue, poll, download — against *client*."""
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

        if download_dir is not None and not isinstance(download_dir, list) and result.succeeded:
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
        workflow: "WorkflowDict | Workflow",
        **kwargs: "Unpack[QueueKwargs]",
    ) -> "PromptResponse": ...

    @overload
    async def acomfyui_queue(
        self,
        workflow: "List[WorkflowDict | Workflow]",
        **kwargs: "Unpack[QueueKwargs]",
    ) -> "List[PromptResponse]": ...

    async def acomfyui_queue(
        self,
        workflow: "WorkflowDict | Workflow | List[WorkflowDict | Workflow]",
        **kwargs: "Unpack[QueueKwargs]",
    ) -> "PromptResponse | List[PromptResponse]":
        """Submit one or more workflows for execution without waiting."""
        client = self.comfyui_client
        if isinstance(workflow, list):
            results = list(await gather(*(client.queue_prompt(wf, **kwargs) for wf in workflow)))
            for r in results:
                logger.info(f"ComfyUI prompt queued: {r.prompt_id}")
            return results
        resp = await client.queue_prompt(workflow, **kwargs)
        logger.info(f"ComfyUI prompt queued: {resp.prompt_id}")
        return resp

    async def acomfyui_inspect_queue(self) -> "QueueInfo":
        """Fetch the current execution queue state."""
        return await self.comfyui_client.get_queue_info()

    async def acomfyui_history(self, prompt_id: str) -> "HistoryEntry | None":
        """Retrieve execution history for *prompt_id*."""
        return await self.comfyui_client.get_history(prompt_id)

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
        client = self.comfyui_client
        if isinstance(prompt_id, list):
            return list(await gather(*(client.wait_for_completion(pid, **kwargs) for pid in prompt_id)))
        return await client.wait_for_completion(prompt_id, **kwargs)

    async def acomfyui_retrieve_image(
        self,
        filename: str,
        **kwargs: "Unpack[ViewImageKwargs]",
    ) -> bytes:
        """Download a single generated image by filename."""
        data = await self.comfyui_client.get_image(filename, **kwargs)
        logger.info(f"Downloaded image: {filename}")
        return data

    async def acomfyui_upload(
        self,
        image_path: "str | Path",
        **kwargs: "Unpack[UploadKwargs]",
    ) -> "UploadResponse":
        """Upload an image to the server."""
        resp = await self.comfyui_client.upload_image(image_path, **kwargs)
        logger.info(f"Uploaded image -> {resp.name}")
        return resp

    async def acomfyui_interrupt(self) -> None:
        """Interrupt the currently running workflow."""
        await self.comfyui_client.interrupt()
        logger.info("ComfyUI execution interrupted")
