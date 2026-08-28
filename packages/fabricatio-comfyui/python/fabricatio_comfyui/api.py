"""Module-level one-shot functions for fabricatio-comfyui.

Following the flat function surface of :mod:`fabricatio_skill` (e.g.
``scan_skills``, ``get_skill``), these helpers hide the client lifecycle
entirely: each call opens its own connection pool, runs, and closes it.
They are the lowest-friction entry point — no Role, no client, no
workflow — and share the exact keyword surface of
:meth:`UseComfyUI.generate_image`.
"""

from pathlib import Path
from typing import Unpack

from fabricatio_comfyui.http_client import ComfyUIHttpClient
from fabricatio_comfyui.models.comfyui import (
    ExecutionResult,
    HistoryEntry,
    QueueInfo,
    UploadResponse,
)
from fabricatio_comfyui.models.kwargs_types import GenerateKwargs

__all__ = [
    "generate_image",
    "get_history",
    "get_queue_info",
    "interrupt",
    "upload_image",
]


async def generate_image(
    prompt: str,
    **kwargs: Unpack[GenerateKwargs],
) -> ExecutionResult:
    """Generate an image against the configured ComfyUI server.

    One-shot: queues a bundled workflow parameterised with *kwargs*, polls
    until completion, downloads outputs when ``download_dir`` is given,
    and closes the connection pool.
    """
    download_dir = kwargs.pop("download_dir", None)
    timeout = kwargs.pop("timeout", None)

    async with ComfyUIHttpClient.create() as client:
        result = await client.generate(prompt, timeout=timeout, **kwargs)
        if download_dir is not None and result.succeeded:
            await client.download_images(result, download_dir)
    return result


async def upload_image(
    image_path: str | Path,
    *,
    image_type: str = "input",
) -> UploadResponse:
    """Upload an image to the configured ComfyUI server."""
    async with ComfyUIHttpClient.create() as client:
        return await client.upload_image(image_path, image_type=image_type)


async def get_history(prompt_id: str) -> HistoryEntry | None:
    """Retrieve execution history for *prompt_id* from the configured server."""
    async with ComfyUIHttpClient.create() as client:
        return await client.get_history(prompt_id)


async def get_queue_info() -> QueueInfo:
    """Fetch the current execution queue state from the configured server."""
    async with ComfyUIHttpClient.create() as client:
        return await client.get_queue_info()


async def interrupt() -> None:
    """Interrupt the currently running workflow on the configured server."""
    async with ComfyUIHttpClient.create() as client:
        await client.interrupt()
