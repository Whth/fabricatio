"""Stateful ComfyUI HTTP client.

Owns the ``httpx.AsyncClient`` lifecycle (connection pool, timeout,
close) and every API method.  The capability mixin delegates here.
"""

import asyncio
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

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

__all__ = ["ComfyuiClient"]


@dataclass
class ComfyuiClient:
    """Stateful async ComfyUI client with persistent connection pooling.

    Use as an async context manager::

        async with ComfyuiClient.create() as client:
            result = await client.generate(workflow)

    Or manage the lifecycle manually::

        client = ComfyuiClient.create()
        try:
            result = await client.generate(workflow)
        finally:
            await client.close()
    """

    _http: Optional[httpx.AsyncClient] = field(default=None, init=False, repr=False)

    @classmethod
    def create(cls) -> "ComfyuiClient":
        """Create a client with the connection pool already open."""
        client = cls()
        client.open()
        return client

    @classmethod
    @lru_cache(maxsize=8)
    def cached(cls, base_url: str = comfyui_config.base_url) -> "ComfyuiClient":
        """Return a shared client for *base_url*, creating on first access."""
        client = cls()
        client.open()
        return client



    async def __aenter__(self) -> "ComfyuiClient":
        """Open the connection pool and return ``self``."""
        self.open()
        return self
    async def __aexit__(self, *_: object) -> None:
        """Close the connection pool."""
        await self.close()

    def open(self) -> None:
        """Create the connection pool if not already open."""
        if self._http is not None and not self._http.is_closed:
            return
        self._http = httpx.AsyncClient(
            base_url=comfyui_config.base_url.rstrip("/"),
            timeout=httpx.Timeout(comfyui_config.timeout),
            limits=httpx.Limits(
                max_connections=comfyui_config.pool_size,
                max_keepalive_connections=comfyui_config.pool_size,
            ),
        )

    async def close(self) -> None:
        """Close the connection pool."""
        if self._http is not None and not self._http.is_closed:
            await self._http.aclose()
            self._http = None

    @property
    def _client(self) -> httpx.AsyncClient:
        """Return the httpx client, opening lazily if needed."""
        self.open()
        assert self._http is not None
        return self._http

    # ------------------------------------------------------------------
    # Low-level HTTP
    # ------------------------------------------------------------------

    async def _post(
        self,
        path: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[bytes] = None,
        files: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        kw: Dict[str, Any] = {}
        if timeout is not None:
            kw["timeout"] = httpx.Timeout(timeout)
        if files:
            kw["data"] = data
            kw["files"] = files
        else:
            kw["json"] = json
        resp = await self._client.post(path, **kw)
        resp.raise_for_status()
        return resp.json()

    async def _get(
        self,
        path: str,
        *,
        params: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        kw: Dict[str, Any] = {}
        if timeout is not None:
            kw["timeout"] = httpx.Timeout(timeout)
        if params:
            kw["params"] = params
        resp = await self._client.get(path, **kw)
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "")
        if ct.startswith("image/") or ct.startswith("application/octet"):
            return resp.content
        return resp.json()

    async def _upload(
        self,
        path: str,
        *,
        files: Dict[str, Any],
        data: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        kw: Dict[str, Any] = {"files": files}
        if data:
            kw["data"] = data
        if timeout is not None:
            kw["timeout"] = httpx.Timeout(timeout)
        resp = await self._client.post(path, **kw)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Prompt / workflow
    # ------------------------------------------------------------------

    async def queue_prompt(
        self,
        workflow: Dict[str, Any],
        *,
        client_id: Optional[str] = None,
        front: bool = False,
    ) -> PromptResponse:
        """Submit a workflow for execution."""
        req = PromptRequest(prompt=workflow, client_id=client_id, front=front)
        data = await self._post("/prompt", json=req.model_dump(exclude_unset=True))
        return PromptResponse.from_raw(data)

    async def get_queue_info(self) -> QueueInfo:
        """Get current queue status."""
        raw = await self._get("/queue")
        return QueueInfo.from_raw(raw)

    async def get_history(self, prompt_id: str) -> Optional[HistoryEntry]:
        """Get execution history for a prompt."""
        raw: Dict[str, Any] = await self._get(f"/history/{prompt_id}")
        return HistoryEntry.from_history_response(raw, prompt_id)

    async def wait_for_completion(
        self,
        prompt_id: str,
        *,
        poll_interval: float = 1.0,
        timeout: Optional[float] = None,
    ) -> ComfyuiExecutionResult:
        """Poll until a prompt completes or fails.

        Raises:
            TimeoutError: If the prompt does not complete within the timeout.
        """
        effective_timeout = timeout or comfyui_config.timeout
        deadline = asyncio.get_event_loop().time() + effective_timeout

        while True:
            if asyncio.get_event_loop().time() > deadline:
                raise TimeoutError(f"ComfyUI prompt {prompt_id} timed out after {effective_timeout}s")

            entry = await self.get_history(prompt_id)
            if entry is None:
                await asyncio.sleep(poll_interval)
                continue

            status = entry.status
            if status.completed or status.status_str in ("failed", "error"):
                outputs: Dict[str, list[ComfyuiOutputImage]] = {}
                for node_id, node_output in entry.outputs.items():
                    if node_output.images:
                        outputs[node_id] = list(node_output.images)
                return ComfyuiExecutionResult(
                    prompt_id=prompt_id,
                    outputs=outputs,
                    status=status.status_str,
                    error=status.exception,
                )

            await asyncio.sleep(poll_interval)

    # ------------------------------------------------------------------
    # Images
    # ------------------------------------------------------------------

    async def get_image(
        self,
        filename: str,
        *,
        subfolder: str = "",
        image_type: str = "output",
    ) -> bytes:
        """Download a generated image."""
        params = ViewImageParams(filename=filename, subfolder=subfolder, type=image_type)
        result = await self._get("/view", params=params.to_params())
        if isinstance(result, dict):
            raise RuntimeError(f"Failed to retrieve image {filename}: {result}")
        return result

    async def upload_image(
        self,
        image_path: str | Path,
        *,
        image_type: str = "input",
        overwrite: bool = True,
    ) -> UploadResponse:
        """Upload an image to the server."""
        p = Path(image_path)
        with p.open("rb") as f:
            files = {"image": (p.name, f, "image/png")}
            data = {"type": image_type, "overwrite": str(overwrite).lower()}
            raw = await self._upload("/upload/image", files=files, data=data)
        return UploadResponse.from_raw(raw)

    async def interrupt(self) -> None:
        """Interrupt the currently running workflow."""
        await self._post("/interrupt")

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    async def generate(
        self,
        workflow: Dict[str, Any],
        *,
        download_dir: Optional[str | Path] = None,
        client_id: Optional[str] = None,
        poll_interval: float = 1.0,
        timeout: Optional[float] = None,
    ) -> ComfyuiExecutionResult:
        """Queue a workflow, wait for completion, optionally download images."""
        resp = await self.queue_prompt(workflow, client_id=client_id)
        result = await self.wait_for_completion(
            resp.prompt_id,
            poll_interval=poll_interval,
            timeout=timeout,
        )

        if download_dir is not None and result.succeeded:
            dst = Path(download_dir)
            dst.mkdir(parents=True, exist_ok=True)
            for img in result.all_images:
                img_bytes = await self.get_image(
                    filename=img.filename,
                    subfolder=img.subfolder,
                    image_type=img.type,
                )
                (dst / img.filename).write_bytes(img_bytes)

        return result
