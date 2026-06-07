"""ComfyUI client — HTTP-only with generation orchestration.

Provides :class:`ComfyuiClient` which wraps
high-level :meth:`generate` workflow using HTTP polling for completion detection.
"""

from pathlib import Path
from typing import Any, Dict, Self, Unpack

from fabricatio_comfyui.config import comfyui_config
from fabricatio_comfyui.http_client import ComfyuiHTTPClient
from fabricatio_comfyui.models.comfyui import ComfyuiExecutionResult
from fabricatio_comfyui.models.kwargs_types import GenerateKwargs
from fabricatio_comfyui.models.workflow import Workflow

__all__ = ["ComfyuiClient", "ComfyuiHTTPClient"]


class ComfyuiClient:
    """HTTP-only ComfyUI client with high-level generation workflows.

    Use as an async context manager::

        async with ComfyuiClient() as client:
            result = await client.generate(workflow)
    """

    def __init__(self) -> None:
        """Create the underlying HTTP client."""
        self._http = ComfyuiHTTPClient()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def __aenter__(self) -> Self:
        self._http.open()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._http.close()

    def open(self) -> None:
        """Open the HTTP connection pool."""
        self._http.open()

    async def close(self) -> None:
        """Close the HTTP connection pool."""
        await self._http.close()

    @property
    def client_id(self) -> str:
        """Client ID for this instance."""
        return self._http.client_id

    # ------------------------------------------------------------------
    # Forwarded HTTP API
    # ------------------------------------------------------------------

    async def queue_prompt(self, workflow: Any, **kwargs: Any) -> Any:
        """Submit a workflow for execution."""
        return await self._http.queue_prompt(workflow, **kwargs)

    async def get_queue_info(self) -> Any:
        """Get current queue status."""
        return await self._http.get_queue_info()

    async def get_history(self, prompt_id: str) -> Any:
        """Get execution history."""
        return await self._http.get_history(prompt_id)

    async def interrupt(self) -> None:
        """Interrupt the running workflow."""
        await self._http.interrupt()

    async def get_image(self, filename: str, **kwargs: Any) -> bytes:
        """Download a generated image."""
        return await self._http.get_image(filename, **kwargs)

    async def upload_image(self, image_path: str | Path, **kwargs: Any) -> Any:
        """Upload an image."""
        return await self._http.upload_image(image_path, **kwargs)

    async def wait_for_completion(self, prompt_id: str, **kwargs: Any) -> Any:
        """Poll history until completion."""
        return await self._http.wait_for_completion(prompt_id, **kwargs)

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

        resp = await self._http.queue_prompt(workflow)
        result = await self._http.wait_for_completion(resp.prompt_id, timeout=effective_timeout)

        if download_dir is not None and result.succeeded:
            await self._download_images(result, download_dir)

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _download_images(self, result: ComfyuiExecutionResult, download_dir: str | Path) -> None:
        """Download all output images to *download_dir*."""
        dst = Path(download_dir)
        dst.mkdir(parents=True, exist_ok=True)
        for img in result.all_images:
            img_bytes = await self._http.get_image(
                filename=img.filename,
                subfolder=img.subfolder,
                image_type=img.type,
            )
            (dst / img.filename).write_bytes(img_bytes)
