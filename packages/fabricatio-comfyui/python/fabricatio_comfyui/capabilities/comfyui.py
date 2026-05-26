"""ComfyUI API client capability.

Provides async HTTP methods to interact with a ComfyUI server:
queue workflows, poll execution status, upload images, and
download generated outputs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from fabricatio_core.journal import logger

from fabricatio_comfyui.config import comfyui_config
from fabricatio_comfyui.models.comfyui import (
    ComfyuiExecutionResult,
    ComfyuiOutputImage,
)

__all__ = ["Comfyui"]


class Comfyui:
    """Async ComfyUI API client capability.

    Mix this class into a Role to gain ComfyUI interaction methods.
    """

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    async def _api_post(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[bytes] = None,
        files: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Send a POST request to the ComfyUI API."""
        import httpx

        url = f"{comfyui_config.base_url.rstrip('/')}{path}"
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout or comfyui_config.timeout)) as client:
            if files:
                resp = await client.post(url, data=data, files=files)
            else:
                resp = await client.post(url, json=json)
            resp.raise_for_status()
            return resp.json()

    async def _api_get(
        self,
        path: str,
        params: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Send a GET request to the ComfyUI API."""
        import httpx

        url = f"{comfyui_config.base_url.rstrip('/')}{path}"
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout or comfyui_config.timeout)) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            ct = resp.headers.get("content-type", "")
            if ct.startswith("image/") or ct.startswith("application/"):
                return resp.content
            return resp.json()

    async def _api_upload(
        self,
        path: str,
        files: Dict[str, Any],
        data: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Send a multipart POST request to the ComfyUI API."""
        import httpx

        url = f"{comfyui_config.base_url.rstrip('/')}{path}"
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout or comfyui_config.timeout)) as client:
            resp = await client.post(url, data=data, files=files)
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Prompt / workflow execution
    # ------------------------------------------------------------------

    async def comfyui_queue_prompt(
        self,
        workflow: Dict[str, Any],
        client_id: Optional[str] = None,
        front: bool = False,
    ) -> str:
        """Submit a workflow graph for execution.

        Args:
            workflow: The ComfyUI workflow graph (node_id → class_type + inputs).
            client_id: Optional WebSocket client ID for progress tracking.
            front: If True, enqueue at the front of the queue.

        Returns:
            The assigned prompt_id (UUID string).
        """
        payload: Dict[str, Any] = {"prompt": workflow}
        if client_id is not None:
            payload["client_id"] = client_id
        if front:
            payload["front"] = True

        data = await self._api_post("/prompt", json=payload)
        prompt_id: str = data["prompt_id"]
        logger.info(f"ComfyUI prompt queued: {prompt_id}")
        return prompt_id

    async def comfyui_get_queue_info(self) -> Dict[str, Any]:
        """Get current queue status (running + pending)."""
        return await self._api_get("/queue")

    async def comfyui_get_history(
        self,
        prompt_id: str,
    ) -> Dict[str, Any]:
        """Get execution history for a specific prompt.

        Args:
            prompt_id: The prompt UUID returned by ``queue_prompt``.

        Returns:
            The history entry dict keyed by prompt_id, or empty dict if not found.
        """
        return await self._api_get(f"/history/{prompt_id}")

    async def comfyui_wait_for_completion(
        self,
        prompt_id: str,
        poll_interval: float = 1.0,
        timeout: Optional[float] = None,
    ) -> ComfyuiExecutionResult:
        """Poll the history endpoint until a prompt completes or fails.

        Args:
            prompt_id: The prompt UUID to wait for.
            poll_interval: Seconds between polling attempts.
            timeout: Maximum seconds to wait (defaults to config timeout).

        Returns:
            An execution result containing output image metadata.

        Raises:
            TimeoutError: If the prompt does not complete within the timeout.
        """
        import asyncio

        deadline = None
        if timeout is not None:
            deadline = asyncio.get_event_loop().time() + timeout

        while True:
            if deadline is not None and asyncio.get_event_loop().time() > deadline:
                raise TimeoutError(f"ComfyUI prompt {prompt_id} did not complete within {timeout}s")

            history = await self.comfyui_get_history(prompt_id)
            if not history or prompt_id not in history:
                await asyncio.sleep(poll_interval)
                continue

            entry = history[prompt_id]
            status_info = entry.get("status", {})
            status_str = status_info.get("status_str", "unknown")
            completed = status_info.get("completed", False)

            result = ComfyuiExecutionResult(
                prompt_id=prompt_id,
                status=status_str,
                error=status_info.get("exception", None),
            )

            if completed or status_str in ("failed", "error"):
                # Parse outputs
                outputs = entry.get("outputs", {})
                for node_id, node_output in outputs.items():
                    images_data = node_output.get("images", [])
                    images = [
                        ComfyuiOutputImage(
                            filename=img.get("filename", ""),
                            subfolder=img.get("subfolder", ""),
                            type=img.get("type", "output"),
                        )
                        for img in images_data
                        if img.get("filename")
                    ]
                    if images:
                        result.outputs[node_id] = images

                if status_str in ("failed", "error"):
                    logger.error(f"ComfyUI prompt {prompt_id} failed: {result.error}")
                else:
                    logger.info(f"ComfyUI prompt {prompt_id} completed")
                return result

            await asyncio.sleep(poll_interval)

    # ------------------------------------------------------------------
    # Image operations
    # ------------------------------------------------------------------

    async def comfyui_get_image(
        self,
        filename: str,
        subfolder: str = "",
        image_type: str = "output",
    ) -> bytes:
        """Download a generated image from the ComfyUI server.

        Args:
            filename: Name of the image file.
            subfolder: Subfolder within the type directory.
            image_type: Directory type (``output``, ``input``, or ``temp``).

        Returns:
            Raw image bytes.
        """
        params = {
            "filename": filename,
            "subfolder": subfolder,
            "type": image_type,
        }
        result = await self._api_get("/view", params=params)
        if isinstance(result, dict):
            logger.warning(f"Unexpected JSON response for image {filename}: {result}")
            raise RuntimeError(f"Failed to retrieve image: {result}")
        logger.info(f"Downloaded image: {filename}")
        return result

    async def comfyui_upload_image(
        self,
        image_path: str | Path,
        image_type: str = "input",
        overwrite: bool = True,
    ) -> Dict[str, Any]:
        """Upload an image to the ComfyUI server (e.g. for img2img workflows).

        Args:
            image_path: Path to the image file on disk.
            image_type: Target directory (``input`` or ``temp``).
            overwrite: Whether to overwrite an existing file with the same name.

        Returns:
            Server response dict with ``name``, ``subfolder``, etc.
        """
        p = Path(image_path)
        with p.open("rb") as f:
            files = {"image": (p.name, f, "image/png")}
            data = {"type": image_type, "overwrite": str(overwrite).lower()}
            result = await self._api_upload("/upload/image", files=files, data=data)
        logger.info(f"Uploaded image {p.name} → {result.get('subfolder', '')}")
        return result

    async def comfyui_interrupt(self) -> None:
        """Interrupt the currently running workflow."""
        await self._api_post("/interrupt")
        logger.info("ComfyUI execution interrupted")

    # ------------------------------------------------------------------
    # Convenience: queue, wait, download
    # ------------------------------------------------------------------

    async def comfyui_generate(
        self,
        workflow: Dict[str, Any],
        download_dir: Optional[str | Path] = None,
        client_id: Optional[str] = None,
        poll_interval: float = 1.0,
        timeout: Optional[float] = None,
    ) -> ComfyuiExecutionResult:
        """High-level helper: queue a workflow, wait for completion, optionally download images.

        Args:
            workflow: The ComfyUI workflow graph.
            download_dir: If set, download all output images to this directory.
            client_id: Optional WebSocket client ID.
            poll_interval: Polling interval in seconds.
            timeout: Maximum time to wait for completion.

        Returns:
            Execution result with image metadata.
        """
        prompt_id = await self.comfyui_queue_prompt(workflow, client_id=client_id)
        result = await self.comfyui_wait_for_completion(
            prompt_id,
            poll_interval=poll_interval,
            timeout=timeout,
        )

        if download_dir is not None and result.succeeded:
            dst = Path(download_dir)
            dst.mkdir(parents=True, exist_ok=True)
            for img in result.all_images:
                data = await self.comfyui_get_image(img.filename, img.subfolder, img.type)
                img_path = dst / img.filename
                img_path.write_bytes(data)
                logger.info(f"Saved image to {img_path}")

        return result
