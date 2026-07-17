"""HTTP-only ComfyUI client.

Owns the ``httpx.AsyncClient`` lifecycle and all REST endpoints.
"""

import asyncio
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Unpack, final

import httpx
from fabricatio_core.utils import first_available

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
    GenerateKwargs,
    PollKwargs,
    QueueKwargs,
    UploadKwargs,
    ViewImageKwargs,
)
from fabricatio_comfyui.models.workflow import Workflow

__all__ = ["ComfyuiHTTPClient"]


@dataclass
@final
class ComfyuiHTTPClient:
    """Async HTTP client for the ComfyUI REST API.

    Manages an ``httpx.AsyncClient`` connection pool.  Always instantiate via
    :meth:`create`; direct construction is internal.
    """

    source: httpx.AsyncClient

    @staticmethod
    @lru_cache
    def create(base_url: str | None = None) -> "ComfyuiHTTPClient":
        """Build a client from the global :data:`comfyui_config`."""
        return ComfyuiHTTPClient(
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
    # Low-level HTTP
    # ------------------------------------------------------------------

    async def post(
        self,
        path: str,
        *,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[bytes] = None,
        files: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Send a POST request and return the JSON response."""
        resp = await self.source.post(path, json=json_data, data=data, files=files, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    async def get(
        self,
        path: str,
        *,
        params: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Send a GET request; return bytes for binary content, JSON otherwise."""
        resp = await self.source.get(path, params=params, timeout=timeout)
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "")
        if ct.startswith("image/") or ct.startswith("application/octet"):
            return resp.content
        return resp.json()

    async def upload(
        self,
        path: str,
        *,
        files: Dict[str, Any],
        data: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Upload files via multipart POST and return the JSON response."""
        resp = await self.source.post(path, data=data, files=files, timeout=timeout)
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
        req = PromptRequest(prompt=wf, client_id=self.client_id, front=front)
        data = await self.post("/prompt", json_data=req.model_dump(exclude_unset=True))
        return PromptResponse.from_raw(data)

    async def get_queue_info(self) -> QueueInfo:
        """Get current queue status via ``GET /queue``."""
        return QueueInfo.from_raw(await self.get("/queue"))

    async def get_history(self, prompt_id: str) -> Optional[HistoryEntry]:
        """Get execution history via ``GET /history/{prompt_id}``."""
        raw: Dict[str, Any] = await self.get(f"/history/{prompt_id}")
        return HistoryEntry.from_history_response(raw, prompt_id)

    async def interrupt(self) -> None:
        """Interrupt the currently running workflow via ``POST /interrupt``."""
        await self.post("/interrupt")

    async def get_image(
        self,
        filename: str,
        **kwargs: Unpack[ViewImageKwargs],
    ) -> bytes:
        """Download a generated image via ``GET /view``."""
        subfolder = kwargs.get("subfolder", "")
        image_type = kwargs.get("image_type", "output")
        params = ViewImageParams(filename=filename, subfolder=subfolder, type=image_type)
        result = await self.get("/view", params=params.to_params())
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
            raw = await self.upload("/upload/image", files=files, data=data)
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

    # ------------------------------------------------------------------
    # High-level generation workflows
    # ------------------------------------------------------------------

    async def generate(
        self,
        workflow: Dict[str, Any] | Workflow,
        **kwargs: Unpack[GenerateKwargs],
    ) -> ComfyuiExecutionResult:
        """Queue a workflow and poll until completion, optionally downloading images.

        Args:
            workflow: A workflow graph dict or :class:`Workflow`.
            **kwargs: See :class:`GenerateKwargs`.
        """
        download_dir = kwargs.get("download_dir")
        timeout = kwargs.get("timeout")
        effective_timeout = timeout or comfyui_config.timeout

        resp = await self.queue_prompt(workflow)
        result = await self.wait_for_completion(resp.prompt_id, timeout=effective_timeout)

        if download_dir is not None and result.succeeded:
            await self.download_images(result, download_dir)

        return result

    async def download_images(self, result: ComfyuiExecutionResult, download_dir: str | Path) -> None:
        """Download all output images to *download_dir* concurrently."""
        dst = Path(download_dir)
        dst.mkdir(parents=True, exist_ok=True)

        async def _fetch(img: Any) -> None:
            data = await self.get_image(filename=img.filename, subfolder=img.subfolder, image_type=img.type)
            (dst / img.filename).write_bytes(data)

        await asyncio.gather(*(_fetch(img) for img in result.all_images))
