"""Module-level one-shot functions for fabricatio-comfyui.

Following the flat function surface of :mod:`fabricatio_skill` (e.g.
``scan_skills``, ``get_skill``), these helpers hide the client entirely:
each call runs against the shared pooled client
(:func:`fabricatio_comfyui.http_client.get_comfyui_client`) — no Role, no
client construction, no workflow — and shares the exact keyword surface
of :meth:`UseComfyUI.generate_image`.
"""

from pathlib import Path
from typing import Unpack, overload

from fabricatio_comfyui.config import comfyui_config
from fabricatio_comfyui.http_client import get_comfyui_client
from fabricatio_comfyui.models.kwargs_types import GenerateKwargs
from fabricatio_core.journal import logger
from fabricatio_core.utils import ok

__all__ = ["generate_image"]


@overload
async def generate_image(
        prompt: str,
        download_dir: str | Path | None = None,
        **kwargs: Unpack[GenerateKwargs],
) -> Path | None: ...


@overload
async def generate_image(
        prompt: list[str],
        download_dir: str | Path | None = None,
        **kwargs: Unpack[GenerateKwargs],
) -> list[Path | None]: ...


@overload
async def generate_image(
        prompt: str | list[str],
        download_dir: str | Path | None = None,
        **kwargs: Unpack[GenerateKwargs],
) -> Path | None | list[Path | None]: ...


async def generate_image(
        prompt: str | list[str],
        download_dir: str | Path | None = None,
        **kwargs: Unpack[GenerateKwargs],
) -> Path | None | list[Path | None]:
    """Generate image(s) against the configured ComfyUI server.

    One-shot: queues a bundled workflow parameterised with the knobs,
    polls until completion, downloads the output image to
    ``download_dir`` (defaults to :data:`comfyui_config.download_dir`),
    and returns its local path — ``None`` when generation failed or
    produced no output image.  Runs on the shared pooled client;
    generation knobs
    (:class:`~fabricatio_comfyui.models.kwargs_types.GenerateKwargs`)
    are forwarded verbatim to the client.

    With a list of prompts, the prompts are generated sequentially and
    the result is one path per prompt — ``None`` at the index of any
    failed generation, preserving prompt/path correspondence.

    Raises:
        ValueError: when neither ``download_dir`` nor
            :data:`comfyui_config.download_dir` is configured.
    """
    target = ok(
        download_dir or comfyui_config.download_dir,
        "generate_image needs a download directory: pass download_dir= or set [ext.comfyui] download_dir",
    )
    if isinstance(prompt, list):
        return [await generate_image(p, download_dir=target, **kwargs) for p in prompt]
    client = get_comfyui_client(comfyui_config.base_url)
    result = await client.generate(prompt, **kwargs)
    if not result.succeeded():
        logger.error(f"ComfyUI generation failed: {result.error}")
        return None
    path = await client.download_first_image(result, target)
    if path is None:
        logger.error("ComfyUI generation finished without output images")
        return None
    logger.info(f"ComfyUI generation completed: {path}")
    return path
