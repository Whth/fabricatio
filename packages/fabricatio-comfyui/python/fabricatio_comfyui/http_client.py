"""Concrete ComfyUI HTTP client.

:class:`ComfyUIHttpClient` is the sole implementation of
:class:`ComfyUIClientBase`.  It owns the ``httpx.AsyncClient`` lifecycle
and all REST endpoints.

Clients are process-wide singletons per base URL via the cached
:func:`get_comfyui_client` factory (the ``fabricatio-milvus`` pattern):
the mixin fetches the shared client when needed and the connection pool
is reused across every instance instead of being bound (and leaked) per
instance.  Direct construction / ``async with`` stays available for
tests and alternate backends that want a private pool::

    async with ComfyUIHttpClient.create() as client:
        result = await client.generate("a mountain landscape")
        await client.download_images(result, "./outputs")
"""

import asyncio
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import IO, Self, Unpack

import httpx
from fabricatio_core.utils import first_available

from fabricatio_comfyui.client_base import ComfyUIClientBase
from fabricatio_comfyui.config import comfyui_config
from fabricatio_comfyui.models.comfyui import (
    ExecutionResult,
    HistoryEntry,
    OutputImage,
    PromptRequest,
    PromptResponse,
    QueueInfo,
    UploadResponse,
    ViewImageParams,
)
from fabricatio_comfyui.models.graph import Graph
from fabricatio_comfyui.models.kwargs_types import (
    PollKwargs,
    UploadKwargs,
    ViewImageKwargs,
)

__all__ = ["ComfyUIHttpClient", "get_comfyui_client"]


@cache
def _cached_client_for_loop(loop: asyncio.AbstractEventLoop, base_url: str) -> "ComfyUIHttpClient":
    """Build the shared client for *base_url* bound to *loop*'s lifetime."""
    return ComfyUIHttpClient.create(base_url)


def get_comfyui_client(base_url: str) -> "ComfyUIHttpClient":
    """Return the shared client for *base_url* on the current event loop.

    One client (and therefore one ``httpx`` connection pool) per distinct
    (event loop, base URL) pair — the ``fabricatio-milvus`` pattern, with
    one extra key: ``httpx.AsyncClient`` pools are event-loop-bound, so a
    plain per-URL ``@cache`` would hand a pool from a closed loop to the
    next one (``RuntimeError: Event loop is closed``).  Within a single
    loop the pool is created once and reused by every holder; a fresh
    loop gets a fresh pool, keeping pytest-asyncio and multi-loop apps
    safe.  Never ``aclose`` the returned client — other holders on the
    same loop may still be using it.
    """
    return _cached_client_for_loop(asyncio.get_running_loop(), base_url)


@dataclass
class ComfyUIHttpClient(ComfyUIClientBase):
    """Async HTTP client for the ComfyUI REST API.

    Manages an ``httpx.AsyncClient`` connection pool.  Prefer the shared
    :func:`get_comfyui_client` factory for normal use; construct directly
    (or via :meth:`create` with ``async with``) only when a private pool
    is wanted.
    """

    source: httpx.AsyncClient

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

    def client_id(self) -> str:
        """Return the client ID derived from the configured server URL."""
        return comfyui_config.base_url.rstrip("/").lower()

    # ------------------------------------------------------------------
    # Lifecycle — explicit close; the context-manager pair is inherited
    # from :class:`ComfyUIClientBase` and delegates here
    # ------------------------------------------------------------------

    async def aclose(self) -> None:
        """Close the underlying ``httpx.AsyncClient`` connection pool."""
        await self.source.aclose()

    # ------------------------------------------------------------------
    # Low-level HTTP
    # ------------------------------------------------------------------

    async def _post(
        self,
        path: str,
        *,
        json_data: dict[str, object] | None = None,
        body: bytes | None = None,
        files: dict[str, tuple[str, IO[bytes], str]] | None = None,
        timeout: float | None = None,
    ) -> dict[str, object]:
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
    ) -> dict[str, object] | bytes:
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
        files: dict[str, tuple[str, IO[bytes], str]],
        data: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> dict[str, object]:
        """Upload files via multipart POST and return the JSON response."""
        resp = await self.source.post(path, data=data, files=files, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # REST endpoints (ComfyUIClientBase implementation)
    # ------------------------------------------------------------------

    async def generate(  # noqa: PLR0913 — public API keeps every override explicit
        self,
        prompt: str,
        *,
        negative_prompt: str | None = None,
        width: int | None = None,
        height: int | None = None,
        seed: int | None = None,
        steps: int | None = None,
        cfg: float | None = None,
        checkpoint: str | None = None,
        front: bool = False,
        timeout: float | None = None,
    ) -> ExecutionResult:
        """Generate an image from typed knobs: queue a bundled workflow and poll until completion.

        The workflow graph is built internally from the bundled template —
        callers never see or construct one.  Only the provided (non-``None``)
        knobs override the template; ``None`` keeps the template's value.
        *checkpoint* falls back to :data:`comfyui_config.checkpoint`, then to
        the template's own checkpoint.  *front* enqueues at the head of the
        queue.  Returns the execution result without downloading images.
        """
        graph = Graph.default()
        if prompt:
            graph.with_positive_prompt(prompt)
        if negative_prompt is not None:
            graph.with_negative_prompt(negative_prompt)
        if width is not None or height is not None:
            graph.with_resolution(width=width, height=height)
        if seed is not None or steps is not None or cfg is not None:
            graph.with_sampler(seed=seed, steps=steps, cfg=cfg)
        checkpoint_name = checkpoint or comfyui_config.checkpoint
        if checkpoint_name is not None:
            graph.with_checkpoint(checkpoint_name)

        req = PromptRequest(prompt=graph.to_api(), client_id=self.client_id(), front=front)
        data = await self._post("/prompt", json_data=req.model_dump(exclude_unset=True))
        resp = PromptResponse.from_raw(data)
        return await self.wait_for_completion(resp.prompt_id, timeout=timeout)

    async def get_queue_info(self) -> QueueInfo:
        """Get current queue status via ``GET /queue``."""
        raw = await self._get("/queue")
        if isinstance(raw, bytes):
            raise RuntimeError(f"Unexpected binary response from /queue: {len(raw)} bytes")
        return QueueInfo.from_raw(raw)

    async def get_history(self, prompt_id: str) -> HistoryEntry | None:
        """Get execution history via ``GET /history/{prompt_id}``."""
        raw = await self._get(f"/history/{prompt_id}")
        if isinstance(raw, bytes):
            raise RuntimeError(f"Unexpected binary response from /history: {len(raw)} bytes")
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
            files: dict[str, tuple[str, IO[bytes], str]] = {"image": (p.name, f, "image/png")}
            data = {"type": image_type, "overwrite": str(overwrite).lower()}
            raw = await self._upload("/upload/image", files=files, data=data)
        return UploadResponse.from_raw(raw)

    async def wait_for_completion(
        self,
        prompt_id: str,
        **kwargs: Unpack[PollKwargs],
    ) -> ExecutionResult:
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
                return ExecutionResult.from_history(prompt_id, entry)

            await asyncio.sleep(poll_interval)

    async def download_images(self, result: ExecutionResult, download_dir: str | Path) -> list[Path]:
        """Download all output images to *download_dir* concurrently; returns their local paths."""
        dst = Path(download_dir)
        dst.mkdir(parents=True, exist_ok=True)

        async def _fetch(img: OutputImage) -> Path:
            data = await self.get_image(filename=img.filename, subfolder=img.subfolder, image_type=img.type)
            path = dst / img.filename
            path.write_bytes(data)
            return path

        return await asyncio.gather(*(_fetch(img) for img in result.all_images()))

    async def download_first_image(self, result: ExecutionResult, download_dir: str | Path) -> Path | None:
        """Download the first output image and return its local path (``None`` when empty)."""
        paths = await self.download_images(result, download_dir)
        return paths[0] if paths else None
