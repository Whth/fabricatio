"""Module-level one-shot functions for fabricatio-comfyui.

Following the flat function surface of :mod:`fabricatio_skill` (e.g.
``scan_skills``, ``get_skill``), these helpers hide the client entirely:
each call runs against the shared pooled client
(:func:`fabricatio_comfyui.http_client.get_comfyui_client`) — no Role, no
client construction, no workflow — and shares the exact keyword surface
of :meth:`UseComfyUI.generate_image`.
"""

from pathlib import Path
from typing import Unpack

from fabricatio_comfyui.config import comfyui_config
from fabricatio_comfyui.http_client import get_comfyui_client
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
    download_dir: str | Path | None = None,
    **kwargs: Unpack[GenerateKwargs],
) -> ExecutionResult:
    """Generate an image against the configured ComfyUI server.

    One-shot: queues a bundled workflow parameterised with the knobs,
    polls until completion, and downloads outputs when ``download_dir``
    is given.  Runs on the shared pooled client; generation knobs
    (:class:`~fabricatio_comfyui.models.kwargs_types.GenerateKwargs`)
    are forwarded verbatim to the client.
    """
    client = get_comfyui_client(comfyui_config.base_url)
    result = await client.generate(prompt, **kwargs)
    if download_dir is not None and result.succeeded():
        await client.download_images(result, download_dir)
    return result


async def upload_image(
    image_path: str | Path,
    *,
    image_type: str = "input",
) -> UploadResponse:
    """Upload an image to the configured ComfyUI server."""
    return await get_comfyui_client(comfyui_config.base_url).upload_image(image_path, image_type=image_type)


async def get_history(prompt_id: str) -> HistoryEntry | None:
    """Retrieve execution history for *prompt_id* from the configured server."""
    return await get_comfyui_client(comfyui_config.base_url).get_history(prompt_id)


async def get_queue_info() -> QueueInfo:
    """Fetch the current execution queue state from the configured server."""
    return await get_comfyui_client(comfyui_config.base_url).get_queue_info()


async def interrupt() -> None:
    """Interrupt the currently running workflow on the configured server."""
    await get_comfyui_client(comfyui_config.base_url).interrupt()
