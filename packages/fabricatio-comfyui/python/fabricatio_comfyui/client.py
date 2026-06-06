"""Stateful ComfyUI client with HTTP and WebSocket support.

Implements all three ComfyUI API methods:
- Method 1: HTTP submit-and-forget (``queue_prompt``)
- Method 2: WebSocket + History — recommended for most use cases (``generate``)
- Method 3: WebSocket + SaveImageWebsocket — real-time image delivery (``generate_ws_images``)

Owns the ``httpx.AsyncClient`` lifecycle (connection pool, timeout, close)
and every API method.  The capability mixin delegates here.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Self

import httpx
import websockets
import websockets.asyncio.client

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
from fabricatio_comfyui.models.workflow import WorkflowBuilder

__all__ = ["ComfyuiClient"]


@dataclass
class ComfyuiClient:
    """Stateful async ComfyUI client with HTTP + WebSocket support.

    Use as an async context manager::

        async with ComfyuiClient() as client:
            result = await client.generate(workflow)

    Or manage the lifecycle manually::

        client = ComfyuiClient()
        try:
            result = await client.generate(workflow)
        finally:
            await client.close()

    Each client instance carries a unique ``client_id`` (UUID4) used for
    WebSocket identification, matching the ComfyUI API protocol.
    """

    _http: Optional[httpx.AsyncClient] = field(default=None, init=False, repr=False)
    _ws: Optional[websockets.asyncio.client.ClientConnection] = field(
        default=None, init=False, repr=False
    )
    _client_id: str = field(default_factory=lambda: str(uuid.uuid4()), init=False, repr=False)

    @property
    def client_id(self) -> str:
        """Persistent client ID for this instance."""
        return self._client_id

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def __aenter__(self) -> Self:
        """Open the connection pool and return ``self``."""
        self.open()
        return self

    async def __aexit__(self, *_: object) -> None:
        """Close the connection pool and WebSocket."""
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
        """Close the HTTP connection pool and WebSocket."""
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
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
    # WebSocket helpers
    # ------------------------------------------------------------------

    async def _ensure_ws(self) -> websockets.asyncio.client.ClientConnection:
        """Open a WebSocket connection if not already connected."""
        if self._ws is not None:
            try:
                # Check if still open by attempting a ping
                await asyncio.wait_for(self._ws.ping(), timeout=2.0)
                return self._ws
            except (OSError, websockets.exceptions.WebSocketException, asyncio.TimeoutError):
                self._ws = None

        ws_url = _ws_url(comfyui_config.base_url, self._client_id)
        self._ws = await websockets.asyncio.client.connect(ws_url)
        return self._ws

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
    # Prompt / workflow — HTTP
    # ------------------------------------------------------------------

    async def queue_prompt(
        self,
        workflow: Dict[str, Any] | WorkflowBuilder,
        *,
        front: bool = False,
    ) -> PromptResponse:
        """Submit a workflow for execution via HTTP ``POST /prompt``.

        Args:
            workflow: A workflow graph dict or :class:`WorkflowBuilder`.
            front: If ``True``, enqueue at the front of the queue.
        """
        wf = workflow.to_dict() if isinstance(workflow, WorkflowBuilder) else workflow
        req = PromptRequest(prompt=wf, client_id=self._client_id, front=front)
        data = await self._post("/prompt", json_data=req.model_dump(exclude_unset=True))
        return PromptResponse.from_raw(data)

    async def get_queue_info(self) -> QueueInfo:
        """Get current queue status via HTTP ``GET /queue``."""
        raw = await self._get("/queue")
        return QueueInfo.from_raw(raw)

    async def get_history(self, prompt_id: str) -> Optional[HistoryEntry]:
        """Get execution history for a prompt via HTTP ``GET /history/{prompt_id}``."""
        raw: Dict[str, Any] = await self._get(f"/history/{prompt_id}")
        return HistoryEntry.from_history_response(raw, prompt_id)

    async def interrupt(self) -> None:
        """Interrupt the currently running workflow via HTTP ``POST /interrupt``."""
        await self._post("/interrupt")

    # ------------------------------------------------------------------
    # Images — HTTP
    # ------------------------------------------------------------------

    async def get_image(
        self,
        filename: str,
        *,
        subfolder: str = "",
        image_type: str = "output",
    ) -> bytes:
        """Download a generated image via HTTP ``GET /view``."""
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
        """Upload an image to the server via HTTP ``POST /upload/image``."""
        p = Path(image_path)
        with p.open("rb") as f:
            files = {"image": (p.name, f, "image/png")}
            data = {"type": image_type, "overwrite": str(overwrite).lower()}
            raw = await self._upload("/upload/image", files=files, data=data)
        return UploadResponse.from_raw(raw)

    # ------------------------------------------------------------------
    # Generate — Method 2: WebSocket + History
    # ------------------------------------------------------------------

    async def generate(
        self,
        workflow: Dict[str, Any] | WorkflowBuilder,
        *,
        download_dir: str | Path | None = None,
        timeout: float | None = None,
    ) -> ComfyuiExecutionResult:
        """Queue a workflow and wait for completion via WebSocket (Method 2).

        Follows the official ComfyUI ``websockets_api_example.py``:
        1. Connect WebSocket with ``client_id``
        2. POST prompt to ``/prompt``
        3. Listen on WebSocket for ``executing`` message where ``node is None``
        4. Fetch history via HTTP ``GET /history/{prompt_id}``
        5. Optionally download output images

        Falls back to HTTP polling if WebSocket connection fails.

        Args:
            workflow: A workflow graph dict or :class:`WorkflowBuilder`.
            download_dir: If set, download output images to this directory.
            timeout: Maximum seconds to wait for completion.
        """
        effective_timeout = timeout or comfyui_config.timeout

        # Step 1: Queue the prompt
        resp = await self.queue_prompt(workflow)

        # Step 2: Wait for completion via WebSocket
        try:
            await self._ws_wait_for_completion(resp.prompt_id, timeout=effective_timeout)
        except (OSError, websockets.exceptions.WebSocketException):
            # WS failed — fall back to HTTP polling
            return await self._poll_and_collect(
                resp.prompt_id, download_dir=download_dir, timeout=effective_timeout
            )

        # Step 3: Fetch history
        entry = await self.get_history(resp.prompt_id)
        if entry is None:
            return ComfyuiExecutionResult(prompt_id=resp.prompt_id, status="error", error="No history found")

        # Step 4: Build result
        result = _build_result(resp.prompt_id, entry)

        # Step 5: Download images if requested
        if download_dir is not None and result.succeeded:
            await self._download_images(result, download_dir)

        return result

    # ------------------------------------------------------------------
    # Generate — Method 3: WebSocket + SaveImageWebsocket
    # ------------------------------------------------------------------

    async def generate_ws_images(
        self,
        workflow: Dict[str, Any] | WorkflowBuilder,
        *,
        timeout: float | None = None,
    ) -> ComfyuiExecutionResult:
        """Queue a workflow and receive images directly via WebSocket (Method 3).

        The workflow **must** contain a ``SaveImageWebsocket`` node.  Images are
        delivered as WebSocket binary frames (first 8 bytes are meta, rest is
        image data) — no disk I/O on the server.

        Follows the official ComfyUI ``websockets_api_example_ws_images.py``.

        Args:
            workflow: A workflow graph dict or :class:`WorkflowBuilder`.
            timeout: Maximum seconds to wait for completion.
        """
        effective_timeout = timeout or comfyui_config.timeout
        wf = workflow.to_dict() if isinstance(workflow, WorkflowBuilder) else workflow

        ws = await self._ensure_ws()

        # Step 1: Queue prompt via HTTP
        req = PromptRequest(prompt=wf, client_id=self._client_id)
        resp_data = await self._post("/prompt", json_data=req.model_dump(exclude_unset=True))
        prompt_id = resp_data["prompt_id"]

        # Step 2: Listen on WS for execution + binary image frames
        try:
            output_images = await self._ws_recv_images(ws, prompt_id, timeout=effective_timeout)
        except TimeoutError:
            raise
        except (OSError, websockets.exceptions.WebSocketException) as exc:
            raise RuntimeError(f"WebSocket error during image generation: {exc}") from exc

        # Build result with images as ComfyuiOutputImage placeholders
        outputs: Dict[str, list[ComfyuiOutputImage]] = {}
        for node_id, image_bytes_list in output_images.items():
            outputs[node_id] = [
                ComfyuiOutputImage(
                    filename=f"ws_image_{node_id}_{i}.png",
                    subfolder="",
                    type="ws_binary",
                )
                for i in range(len(image_bytes_list))
            ]

        return ComfyuiExecutionResult(
            prompt_id=prompt_id,
            outputs=outputs,
            status="completed",
        )

    # ------------------------------------------------------------------
    # HTTP polling fallback (Method 1 extended)
    # ------------------------------------------------------------------

    async def wait_for_completion(
        self,
        prompt_id: str,
        *,
        poll_interval: float = 1.0,
        timeout: float | None = None,
    ) -> ComfyuiExecutionResult:
        """Poll until a prompt completes or fails (HTTP polling fallback).

        Uses ``GET /history/{prompt_id}`` in a loop.  Prefer :meth:`generate`
        which uses WebSocket for real-time completion detection.
        """
        effective_timeout = timeout or comfyui_config.timeout
        deadline = asyncio.get_event_loop().time() + effective_timeout

        while True:
            if asyncio.get_event_loop().time() > deadline:
                raise TimeoutError(f"ComfyUI prompt {prompt_id} timed out after {effective_timeout}s")

            entry = await self.get_history(prompt_id)
            if entry is not None:
                return _build_result(prompt_id, entry)

            await asyncio.sleep(poll_interval)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _ws_wait_for_completion(self, prompt_id: str, *, timeout: float) -> None:
        """Wait on WebSocket for execution to complete (Method 2 core loop).

        Listens for ``executing`` messages.  When ``node`` is ``None``, execution
        is done (per the ComfyUI API docs).
        """
        ws = await self._ensure_ws()
        deadline = asyncio.get_event_loop().time() + timeout

        while True:
            if asyncio.get_event_loop().time() > deadline:
                raise TimeoutError(f"ComfyUI WS wait timed out after {timeout}s")

            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=min(5.0, timeout))
            except asyncio.TimeoutError:
                continue

            if isinstance(msg, str):
                message = json.loads(msg)
                if (
                    message.get("type") == "executing"
                    and message["data"].get("prompt_id") == prompt_id
                    and message["data"]["node"] is None
                ):
                    return  # Execution done
            # Binary frames (preview images) are skipped

    async def _ws_recv_images(
        self,
        ws: websockets.asyncio.client.ClientConnection,
        prompt_id: str,
        *,
        timeout: float,
    ) -> Dict[str, list[bytes]]:
        """Receive images via WebSocket binary frames until execution completes.
        Follows the ComfyUI ``websockets_api_example_ws_images.py`` pattern:
        binary frames carry image data (first 8 bytes are meta, rest is image).
        """
        output_images: Dict[str, list[bytes]] = {}
        current_node = ""
        deadline = asyncio.get_event_loop().time() + timeout

        while True:
            if asyncio.get_event_loop().time() > deadline:
                raise TimeoutError(f"ComfyUI WS image recv timed out after {timeout}s")

            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=min(5.0, timeout))
            except asyncio.TimeoutError:
                continue

            if isinstance(msg, str):
                message = json.loads(msg)
                if (
                    message.get("type") == "executing"
                    and message["data"].get("prompt_id") == prompt_id
                ):
                    if message["data"]["node"] is None:
                        break  # Execution done
                    current_node = message["data"]["node"]
            elif isinstance(msg, bytes) and current_node:
                # Binary frame from SaveImageWebsocket — skip first 8 bytes (meta)
                output_images.setdefault(current_node, []).append(msg[8:])

        return output_images


    async def _poll_and_collect(
        self,
        prompt_id: str,
        *,
        download_dir: str | Path | None,
        timeout: float,
    ) -> ComfyuiExecutionResult:
        """HTTP polling fallback: poll history then download images."""
        result = await self.wait_for_completion(prompt_id, timeout=timeout)

        if download_dir is not None and result.succeeded:
            await self._download_images(result, download_dir)

        return result

    async def _download_images(self, result: ComfyuiExecutionResult, download_dir: str | Path) -> None:
        """Download all output images to *download_dir*."""
        dst = Path(download_dir)
        dst.mkdir(parents=True, exist_ok=True)
        for img in result.all_images:
            if img.type == "ws_binary":
                continue  # WS images are in-memory, not on disk
            img_bytes = await self.get_image(
                filename=img.filename,
                subfolder=img.subfolder,
                image_type=img.type,
            )
            (dst / img.filename).write_bytes(img_bytes)


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _ws_url(base_url: str, client_id: str) -> str:
    """Convert an HTTP base URL to a WebSocket URL with client ID."""
    url = base_url.rstrip("/")
    if url.startswith("https://"):
        ws_url = "wss://" + url[len("https://"):]
    elif url.startswith("http://"):
        ws_url = "ws://" + url[len("http://"):]
    else:
        ws_url = "ws://" + url
    return f"{ws_url}/ws?clientId={client_id}"


def _build_result(prompt_id: str, entry: HistoryEntry) -> ComfyuiExecutionResult:
    """Build an execution result from a history entry."""
    outputs: Dict[str, list[ComfyuiOutputImage]] = {}
    for node_id, node_output in entry.outputs.items():
        if node_output.images:
            outputs[node_id] = list(node_output.images)

    return ComfyuiExecutionResult(
        prompt_id=prompt_id,
        outputs=outputs,
        status=entry.status.status_str,
        error=entry.status.exception,
    )
