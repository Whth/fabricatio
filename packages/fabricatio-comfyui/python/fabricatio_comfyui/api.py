"""Module-level one-shot functions for fabricatio-comfyui.

Following the plain module-level function style fabricatio exposes elsewhere
(rather than Roles or client objects), these helpers hide the client entirely:
each call runs against the shared pooled client
(:func:`fabricatio_comfyui.http_client.get_comfyui_client`) — no Role, no
client construction, no workflow — and shares the exact keyword surface
of the corresponding :class:`UseComfyUI` method.

Each bundled workflow kind gets its own function: :func:`generate_image`
(two-pass), :func:`generate_simple_image` (single-pass),
:func:`generate_anima_image` (anima preset), and :func:`generate_img2img`
(refine an input image) — the kind is chosen at the call site, not via
configuration.
"""

from pathlib import Path
from typing import Unpack, overload

from fabricatio_core.journal import logger
from fabricatio_core.utils import ok

from fabricatio_comfyui.config import comfyui_config
from fabricatio_comfyui.http_client import ComfyUIHttpClient, get_comfyui_client
from fabricatio_comfyui.models.comfyui import ExecutionResult
from fabricatio_comfyui.models.kwargs_types import GenerateKwargs, Img2ImgGenerateKwargs

__all__ = ["generate_anima_image", "generate_image", "generate_img2img", "generate_simple_image"]


async def _download_paths(
    client: ComfyUIHttpClient,
    prompt: str | list[str],
    results: list[ExecutionResult],
    target: str | Path,
) -> Path | list[Path | None] | None:
    """Download each result's first image into *target*, one path per prompt.

    Returns ``None`` for a scalar *prompt* that failed (or produced no
    image); a list prompt yields one such value per prompt, preserving
    prompt/path correspondence.
    """
    paths: list[Path | None] = []
    for result in results:
        if not result.succeeded():
            logger.error(f"ComfyUI generation failed: {result.error}")
            paths.append(None)
            continue
        path = await client.download_first_image(result, target)
        if path is None:
            logger.error("ComfyUI generation finished without output images")
            paths.append(None)
            continue
        logger.info(f"ComfyUI generation completed: {path}")
        paths.append(path)
    return paths[0] if isinstance(prompt, str) else paths


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
) -> Path | list[Path | None] | None: ...


async def generate_image(
    prompt: str | list[str],
    download_dir: str | Path | None = None,
    **kwargs: Unpack[GenerateKwargs],
) -> Path | list[Path | None] | None:
    """Generate image(s) with the bundled two-pass workflow.

    One-shot: queues the two-pass template parameterised with the knobs,
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
    client = get_comfyui_client(comfyui_config.base_url)
    results = await client.generate(prompt, **kwargs)
    return await _download_paths(client, prompt, results, target)


@overload
async def generate_simple_image(
    prompt: str,
    download_dir: str | Path | None = None,
    **kwargs: Unpack[GenerateKwargs],
) -> Path | None: ...


@overload
async def generate_simple_image(
    prompt: list[str],
    download_dir: str | Path | None = None,
    **kwargs: Unpack[GenerateKwargs],
) -> list[Path | None]: ...


@overload
async def generate_simple_image(
    prompt: str | list[str],
    download_dir: str | Path | None = None,
    **kwargs: Unpack[GenerateKwargs],
) -> Path | list[Path | None] | None: ...


async def generate_simple_image(
    prompt: str | list[str],
    download_dir: str | Path | None = None,
    **kwargs: Unpack[GenerateKwargs],
) -> Path | list[Path | None] | None:
    """Generate image(s) with the bundled single-pass workflow.

    Same contract as :func:`generate_image`, but the single-pass
    template skips the upscale/refine branch — the finished image is
    exactly the latent canvas, so *mp* / *prop* size it directly.
    """
    target = ok(
        download_dir or comfyui_config.download_dir,
        "generate_simple_image needs a download directory: pass download_dir= or set [ext.comfyui] download_dir",
    )
    client = get_comfyui_client(comfyui_config.base_url)
    results = await client.generate_simple(prompt, **kwargs)
    return await _download_paths(client, prompt, results, target)


@overload
async def generate_anima_image(
    prompt: str,
    download_dir: str | Path | None = None,
    *,
    clip: str | None = None,
    vae: str | None = None,
    **kwargs: Unpack[GenerateKwargs],
) -> Path | None: ...


@overload
async def generate_anima_image(
    prompt: list[str],
    download_dir: str | Path | None = None,
    *,
    clip: str | None = None,
    vae: str | None = None,
    **kwargs: Unpack[GenerateKwargs],
) -> list[Path | None]: ...


@overload
async def generate_anima_image(
    prompt: str | list[str],
    download_dir: str | Path | None = None,
    *,
    clip: str | None = None,
    vae: str | None = None,
    **kwargs: Unpack[GenerateKwargs],
) -> Path | list[Path | None] | None: ...


async def generate_anima_image(
    prompt: str | list[str],
    download_dir: str | Path | None = None,
    *,
    clip: str | None = None,
    vae: str | None = None,
    **kwargs: Unpack[GenerateKwargs],
) -> Path | list[Path | None] | None:
    """Generate image(s) with the bundled anima workflow.

    Same contract as :func:`generate_image`, but the anima template
    loads checkpoint / CLIP / VAE from separate nodes and samples once
    at a fixed 4:3 canvas (*mp* / *prop* overridable).  *clip* / *vae*
    fall back to ``[ext.comfyui] anima_clip`` / ``anima_vae`` and
    *checkpoint* to ``checkpoint`` / ``anima_checkpoint`` — unset
    filenames fail loudly.
    """
    target = ok(
        download_dir or comfyui_config.download_dir,
        "generate_anima_image needs a download directory: pass download_dir= or set [ext.comfyui] download_dir",
    )
    client = get_comfyui_client(comfyui_config.base_url)
    results = await client.generate_anima(prompt, clip=clip, vae=vae, **kwargs)
    return await _download_paths(client, prompt, results, target)


@overload
async def generate_img2img(
    prompt: str,
    image: str | Path,
    download_dir: str | Path | None = None,
    *,
    denoise: float | None = None,
    **kwargs: Unpack[Img2ImgGenerateKwargs],
) -> Path | None: ...


@overload
async def generate_img2img(
    prompt: list[str],
    image: str | Path,
    download_dir: str | Path | None = None,
    *,
    denoise: float | None = None,
    **kwargs: Unpack[Img2ImgGenerateKwargs],
) -> list[Path | None]: ...


@overload
async def generate_img2img(
    prompt: str | list[str],
    image: str | Path,
    download_dir: str | Path | None = None,
    *,
    denoise: float | None = None,
    **kwargs: Unpack[Img2ImgGenerateKwargs],
) -> Path | list[Path | None] | None: ...


async def generate_img2img(
    prompt: str | list[str],
    image: str | Path,
    download_dir: str | Path | None = None,
    *,
    denoise: float | None = None,
    **kwargs: Unpack[Img2ImgGenerateKwargs],
) -> Path | list[Path | None] | None:
    """Refine *image* into image(s) with the bundled img2img workflow.

    Same contract as :func:`generate_image`, but the template takes an
    input image: a local file (passed as a :class:`pathlib.Path`) is
    uploaded first, while a ``str`` names an image already in the
    server's input directory.  *mp* scales the image toward the budget
    and *denoise* maps to the sampler's start step — lower values keep
    more of the source composition.  All other knobs are forwarded
    verbatim to :meth:`ComfyUIClientBase.generate_img2img`.
    """
    target = ok(
        download_dir or comfyui_config.download_dir,
        "generate_img2img needs a download directory: pass download_dir= or set [ext.comfyui] download_dir",
    )
    client = get_comfyui_client(comfyui_config.base_url)
    results = await client.generate_img2img(prompt, image, denoise=denoise, **kwargs)
    return await _download_paths(client, prompt, results, target)
