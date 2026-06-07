"""HTTP-only ComfyUI client.

Owns the ``httpx.AsyncClient`` lifecycle and all REST endpoints.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Self, Unpack

import httpx

from fabricatio_comfyui.config import comfyui_config
from fabricatio_comfyui.models.comfyui import (
    ComfyuiExecutionResult,
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

__all__ = ["ComfyuiHTTPClient"]


@dataclass
class ComfyuiHTTPClient:
    """Async HTTP client for the ComfyUI REST API.

    Manages an ``httpx.AsyncClient`` connection pool.  Use as an async
    context manager or call :meth:`open` / :meth:`close` manually.
    """

    _http: Optional[httpx.AsyncClient] = field(default=None, init=False, repr=False)
    _client_id: str = field(default_factory=lambda: str(uuid.uuid4()), init=False, repr=False)

    @property
    def client_id(self) -> str:
        """Persistent client ID for this instance."""
        return self._client_id

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def __aenter__(self) -> Self:
        self.open()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    def open(self) -> None:
        """Create the HTTP connection pool if not already open."""
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
        """Close the HTTP connection pool."""
        if self._http is not None and not self._http.is_closed:
            await self._http.aclose()
            self._http = None

    @property
    def _client(self) -> httpx.AsyncClient:
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
        json_data: Optional[Dict[str, Any]] = None,
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
            kw["json"] = json_data
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
    # Public API
    # ------------------------------------------------------------------

    async def queue_prompt(
        self,
        workflow: Dict[str, Any] | Workflow,
        **kwargs: Unpack[QueueKwargs],
    ) -> PromptResponse:
        """Submit a workflow for execution via ``POST /prompt``."""
        front = kwargs.get("front", False)
        wf = workflow.to_api() if isinstance(workflow, Workflow) else workflow
        req = PromptRequest(prompt=wf, client_id=self._client_id, front=front)
        data = await self._post("/prompt", json_data=req.model_dump(exclude_unset=True))
        return PromptResponse.from_raw(data)

    async def get_queue_info(self) -> QueueInfo:
        """Get current queue status via ``GET /queue``."""
        return QueueInfo.from_raw(await self._get("/queue"))

    async def get_history(self, prompt_id: str) -> Optional[HistoryEntry]:
        """Get execution history via ``GET /history/{prompt_id}``."""
        raw: Dict[str, Any] = await self._get(f"/history/{prompt_id}")
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
        from fabricatio_comfyui.utils import build_result

        poll_interval = kwargs.get("poll_interval", 1.0)
        timeout = kwargs.get("timeout")
        effective_timeout = timeout or comfyui_config.timeout
        deadline = asyncio.get_event_loop().time() + effective_timeout

        while True:
            if asyncio.get_event_loop().time() > deadline:
                raise TimeoutError(f"ComfyUI prompt {prompt_id} timed out after {effective_timeout}s")

            entry = await self.get_history(prompt_id)
            if entry is not None:
                return build_result(prompt_id, entry)

            await asyncio.sleep(poll_interval)
