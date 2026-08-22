"""Concrete ComfyUI HTTP client.

:class:`ComfyuiHTTPClient` is the sole implementation of
:class:`ComfyuiClientBase`.  It owns the ``httpx.AsyncClient`` lifecycle
and all REST endpoints.  Construct it via :meth:`create` and manage it
as an async context manager (``async with client:``) so the connection
pool is always closed::

    async with ComfyuiHTTPClient.create() as client:
        wf = Workflow.default()
        wf.set_positive_prompt("a mountain landscape")
        resp = await client.queue_prompt(wf)
        result = await client.wait_for_completion(resp.prompt_id)

No ``@lru_cache`` — each :meth:`create` call returns a fresh client with
its own connection pool, so long-running apps no longer leak connections
and each event loop gets its own pool (fixing the
``RuntimeError: Event loop is closed`` that plagued pytest-asyncio).
"""

import asyncio
from pathlib import Path
from typing import Any, Self, Unpack

import httpx
from fabricatio_core.utils import first_available

from fabricatio_comfyui.client_base import ComfyuiClientBase
from fabricatio_comfyui.config import comfyui_config
from fabricatio_comfyui.models.comfyui import (
    ComfyuiExecutionResult,
    ComfyuiOutputImage,
    HistoryEntry,
    PromptRequest,
    PromptResponse,
    QueueInfo,
    UploadResponse,
    ViewImageParams,
)
from fabricatio_comfyui.models.kwargs_types import (
    PollKwargs,
    QueueKwargs,
    UploadKwargs,
    ViewImageKwargs,
)
from fabricatio_comfyui.models.workflow import Workflow
from fabricatio_comfyui.utils import build_result

__all__ = ["ComfyuiHTTPClient"]


class ComfyuiHTTPClient(ComfyuiClientBase):
    """Async HTTP client for the ComfyUI REST API.

    Manages an ``httpx.AsyncClient`` connection pool.  Always instantiate
    via :meth:`create`; direct construction is supported but the caller
    then owns the ``httpx.AsyncClient`` lifecycle.  Use ``async with`` to
    guarantee cleanup.
    """

    source: httpx.AsyncClient

    def __init__(self, source: httpx.AsyncClient) -> None:
        """Wrap an existing ``httpx.AsyncClient``."""
        self.source = source

    @classmethod
    def create(cls, base_url: str | None = None) -> Self:
        """Build a client from the global :data:`comfyui_config`.

        The returned client owns its own ``httpx.AsyncClient`` — close it
        via ``await client.aclose()`` or, preferably, ``async with``.
        """
        return cls(
            source=httpx.AsyncClient(
                base_url=first_available((base_url, comfyui_config.base_url)).rstrip("/"),
                timeout=httpx.Timeout(comfyui_config.timeout),
            ),
        )

    @property
    def client_id(self) -> str:
        """Client ID derived from the configured server URL."""
        return comfyui_config.base_url.rstrip("/").lower()

    # ------------------------------------------------------------------
    # Lifecycle — async context manager + explicit aclose
    # ------------------------------------------------------------------

    async def aclose(self) -> None:
        """Close the underlying ``httpx.AsyncClient`` connection pool."""
        await self.source.aclose()

    async def __aenter__(self) -> Self:
        """Enter async context — returns ``self``."""
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit async context — closes the connection pool."""
        await self.aclose()

    # ------------------------------------------------------------------
    # Low-level HTTP
    # ------------------------------------------------------------------

    async def _post(
        self,
        path: str,
        *,
        json_data: dict[str, Any] | None = None,
        body: bytes | None = None,
        files: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Send a POST request and return the JSON response.

        *json_data*, *body*, and *files* are mutually exclusive content
        shapes; the caller picks exactly one.  ``body`` is forwarded via
        httpx's ``content=`` parameter (raw request body).
        """
        resp = await self.source.post(
            path,
            json=json_data,
            content=body,
            files=files,
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()

    async def _get(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Send a GET request; return bytes for binary content, JSON otherwise."""
        resp = await self.source.get(path, params=params, timeout=timeout)
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "")
        if ct.startswith("image/") or ct.startswith("application/octet"):
            return resp.content
        return resp.json()

    async def _upload(
        self,
        path: str,
        *,
        files: dict[str, Any],
        data: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Upload files via multipart POST and return the JSON response."""
        resp = await self.source.post(path, data=data, files=files, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # REST endpoints (ComfyuiClientBase implementation)
    # ------------------------------------------------------------------

    async def queue_prompt(
        self,
        workflow: Workflow,
        **kwargs: Unpack[QueueKwargs],
    ) -> PromptResponse:
        """Submit a bundled workflow for execution via ``POST /prompt``."""
        front = kwargs.get("front", False)
        req = PromptRequest(prompt=workflow.to_api(), client_id=self.client_id, front=front)
        data = await self._post("/prompt", json_data=req.model_dump(exclude_unset=True))
        return PromptResponse.from_raw(data)

    async def get_queue_info(self) -> QueueInfo:
        """Get current queue status via ``GET /queue``."""
        return QueueInfo.from_raw(await self._get("/queue"))

    async def get_history(self, prompt_id: str) -> HistoryEntry | None:
        """Get execution history via ``GET /history/{prompt_id}``."""
        raw: dict[str, Any] = await self._get(f"/history/{prompt_id}")
        return HistoryEntry.from_history_response(raw, prompt_id)

    async def interrupt(self) -> None:
        """Interrupt the currently running workflow via ``POST /interrupt``."""
        await self._post("/interrupt")

    async def get_image(
        self,
        filename: str,
        **kwargs: Unpack[ViewImageKwargs],
    ) -> bytes:
        """Download a generated image via ``GET /view``."""
        subfolder = kwargs.get("subfolder", "")
        image_type = kwargs.get("image_type", "output")
        params = ViewImageParams(filename=filename, subfolder=subfolder, type=image_type)
        result = await self._get("/view", params=params.to_params())
        if isinstance(result, dict):
            raise RuntimeError(f"Failed to retrieve image {filename}: {result}")
        return result

    async def upload_image(
        self,
        image_path: str | Path,
        **kwargs: Unpack[UploadKwargs],
    ) -> UploadResponse:
        """Upload an image via ``POST /upload/image``."""
        image_type = kwargs.get("image_type", "input")
        overwrite = kwargs.get("overwrite", True)
        p = Path(image_path)
        with p.open("rb") as f:
            files = {"image": (p.name, f, "image/png")}
            data = {"type": image_type, "overwrite": str(overwrite).lower()}
            raw = await self._upload("/upload/image", files=files, data=data)
        return UploadResponse.from_raw(raw)

    async def wait_for_completion(
        self,
        prompt_id: str,
        **kwargs: Unpack[PollKwargs],
    ) -> ComfyuiExecutionResult:
        """Poll ``GET /history/{prompt_id}`` until completion."""
        poll_interval = kwargs.get("poll_interval", 1.0)
        timeout = kwargs.get("timeout")
        effective_timeout = timeout or comfyui_config.timeout
        loop = asyncio.get_running_loop()
        deadline = loop.time() + effective_timeout

        while True:
            if loop.time() > deadline:
                raise TimeoutError(f"ComfyUI prompt {prompt_id} timed out after {effective_timeout}s")

            entry = await self.get_history(prompt_id)
            if entry is not None:
                return build_result(prompt_id, entry)

            await asyncio.sleep(poll_interval)

    async def download_images(self, result: ComfyuiExecutionResult, download_dir: str | Path) -> None:
        """Download all output images to *download_dir* concurrently."""
        dst = Path(download_dir)
        dst.mkdir(parents=True, exist_ok=True)

        async def _fetch(img: ComfyuiOutputImage) -> None:
            data = await self.get_image(filename=img.filename, subfolder=img.subfolder, image_type=img.type)
            (dst / img.filename).write_bytes(data)

        await asyncio.gather(*(_fetch(img) for img in result.all_images))
