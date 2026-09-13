"""ComfyUI capability mixin.

Mix into a Role to gain ComfyUI image generation methods.  The public
surface is intentionally **narrow**: callers supply high-level knobs
(``prompt``, ``prop``, ``mp``, ``seed``, ``steps``, ``cfg``,
``checkpoint``) and the package parameterises a bundled workflow template
internally.  Workflow graphs are an implementation detail — external
callers never see or operate on one.  Each bundled workflow kind gets
its own method — :meth:`generate_image` (two-pass),
:meth:`generate_simple_image` (single-pass), and
:meth:`generate_anima_image` (anima preset); the kind is chosen at the
call site, not via configuration.

Method naming follows the ``Use*`` capability pattern of
:mod:`fabricatio_skill` (``UseSkill``): plain verbs with the kind as a
suffix (``generate_image``, ``generate_anima_image`` ...), no
``a``-prefix.

Client lifecycle follows the ``fabricatio-milvus`` pattern: the mixin
holds no client at all.  A module-level ``@cache`` factory keeps one
process-wide shared client (and ``httpx`` connection pool) per base URL,
and :meth:`comfyui_client` fetches it when needed — stateless mixins, no
per-instance binding, no leak-prone ownership.
"""

from pathlib import Path
from typing import Unpack, overload

from fabricatio_core.utils import first_available

from fabricatio_comfyui.api import (
    generate_anima_image,
    generate_image,
    generate_img2img,
    generate_simple_image,
)
from fabricatio_comfyui.config import comfyui_config
from fabricatio_comfyui.models.comfyui import ComfyUIScopedConfig
from fabricatio_comfyui.models.kwargs_types import GenerateKwargs, Img2ImgGenerateKwargs

__all__ = ["UseComfyUI"]


class UseComfyUI(ComfyUIScopedConfig):
    """ComfyUI capability mixin — fetches the shared client on demand.

    Usage::

        class ImageRole(Role, UseComfyUI): ...

        path = await ImageRole(name="painter").generate_image("a mountain landscape")
        # path: Path | None — None when generation failed

    Inherits :class:`ComfyUIScopedConfig`; set ``download_dir`` as a
    subclass default or instance attribute to bind a Role to one output
    directory::

        class ArtRole(Role, UseComfyUI):
            download_dir: str = "./art"
    """

    # ------------------------------------------------------------------
    # High-level public surface — only typed knobs, no workflow graphs
    # ------------------------------------------------------------------

    @overload
    async def generate_image(
        self,
        prompt: str,
        download_dir: str | Path | None = None,
        **kwargs: Unpack[GenerateKwargs],
    ) -> "Path | None": ...

    @overload
    async def generate_image(
        self,
        prompt: list[str],
        download_dir: str | Path | None = None,
        **kwargs: Unpack[GenerateKwargs],
    ) -> "list[Path | None]": ...

    async def generate_image(
        self,
        prompt: str | list[str],
        download_dir: str | Path | None = None,
        **kwargs: Unpack[GenerateKwargs],
    ) -> "Path | list[Path | None] | None":
        """Generate image(s) from typed knobs and return their downloaded paths.

        Queues a bundled template parameterised with the provided knobs,
        polls until completion, then downloads the output image(s) to
        ``download_dir`` — or, when omitted, to this instance's scoped
        :attr:`~fabricatio_comfyui.models.comfyui.ComfyUIScopedConfig.download_dir`,
        then to :data:`comfyui_config.download_dir`.  Generation knobs
        (:class:`~fabricatio_comfyui.models.kwargs_types.GenerateKwargs`)
        are forwarded verbatim to the client.

        With a list of prompts, the prompts are generated sequentially and
        the result is one path per prompt — ``None`` at the index of any
        failed generation, preserving prompt/path correspondence.

        Returns:
            The local path of the generated image, or ``None`` when
            generation failed or produced no output image; for a list of
            prompts, a list with one such value per prompt.

        Raises:
            ValueError: when neither ``download_dir``, the scoped
                :attr:`~fabricatio_comfyui.models.comfyui.ComfyUIScopedConfig.download_dir`,
                nor :data:`comfyui_config.download_dir` is configured.

        Delegates to :func:`fabricatio_comfyui.api.generate_image`, the
        single implementation shared with the module-level function.
        """
        target = first_available(
            (download_dir, self.download_dir, comfyui_config.download_dir),
            "generate_image needs a download directory: pass download_dir=, set [ext.comfyui] download_dir, "
            "or set a download_dir on the Role",
        )
        return await generate_image(prompt, download_dir=target, **kwargs)

    @overload
    async def generate_simple_image(
        self,
        prompt: str,
        download_dir: str | Path | None = None,
        **kwargs: Unpack[GenerateKwargs],
    ) -> "Path | None": ...

    @overload
    async def generate_simple_image(
        self,
        prompt: list[str],
        download_dir: str | Path | None = None,
        **kwargs: Unpack[GenerateKwargs],
    ) -> "list[Path | None]": ...

    async def generate_simple_image(
        self,
        prompt: str | list[str],
        download_dir: str | Path | None = None,
        **kwargs: Unpack[GenerateKwargs],
    ) -> "Path | list[Path | None] | None":
        """Generate image(s) with the bundled single-pass workflow.

        Same contract as :meth:`generate_image`, but the single-pass
        template skips the upscale/refine branch — the finished image is
        exactly the latent canvas, so *mp* / *prop* size it directly.
        Delegates to
        :func:`fabricatio_comfyui.api.generate_simple_image`.
        """
        target = first_available(
            (download_dir, self.download_dir, comfyui_config.download_dir),
            "generate_simple_image needs a download directory: pass download_dir=, set [ext.comfyui] download_dir, "
            "or set a download_dir on the Role",
        )
        return await generate_simple_image(prompt, download_dir=target, **kwargs)

    @overload
    async def generate_anima_image(
        self,
        prompt: str,
        download_dir: str | Path | None = None,
        *,
        clip: str | None = None,
        vae: str | None = None,
        **kwargs: Unpack[GenerateKwargs],
    ) -> "Path | None": ...

    @overload
    async def generate_anima_image(
        self,
        prompt: list[str],
        download_dir: str | Path | None = None,
        *,
        clip: str | None = None,
        vae: str | None = None,
        **kwargs: Unpack[GenerateKwargs],
    ) -> "list[Path | None]": ...

    async def generate_anima_image(
        self,
        prompt: str | list[str],
        download_dir: str | Path | None = None,
        *,
        clip: str | None = None,
        vae: str | None = None,
        **kwargs: Unpack[GenerateKwargs],
    ) -> "Path | list[Path | None] | None":
        """Generate image(s) with the bundled anima workflow.

        Same contract as :meth:`generate_image`, but the anima template
        loads checkpoint / CLIP / VAE from separate nodes and samples
        once at a fixed 4:3 canvas (*mp* / *prop* overridable).  *clip* /
        *vae* fall back to ``[ext.comfyui] anima_clip`` / ``anima_vae``
        and *checkpoint* to ``checkpoint`` / ``anima_checkpoint`` — unset
        filenames fail loudly.  Delegates to
        :func:`fabricatio_comfyui.api.generate_anima_image`.
        """
        target = first_available(
            (download_dir, self.download_dir, comfyui_config.download_dir),
            "generate_anima_image needs a download directory: pass download_dir=, set [ext.comfyui] download_dir, "
            "or set a download_dir on the Role",
        )
        return await generate_anima_image(prompt, download_dir=target, clip=clip, vae=vae, **kwargs)

    @overload
    async def generate_img2img(
        self,
        prompt: str,
        image: str | Path,
        download_dir: str | Path | None = None,
        *,
        denoise: float | None = None,
        **kwargs: Unpack[Img2ImgGenerateKwargs],
    ) -> "Path | None": ...

    @overload
    async def generate_img2img(
        self,
        prompt: list[str],
        image: str | Path,
        download_dir: str | Path | None = None,
        *,
        denoise: float | None = None,
        **kwargs: Unpack[Img2ImgGenerateKwargs],
    ) -> "list[Path | None]": ...

    async def generate_img2img(
        self,
        prompt: str | list[str],
        image: str | Path,
        download_dir: str | Path | None = None,
        *,
        denoise: float | None = None,
        **kwargs: Unpack[Img2ImgGenerateKwargs],
    ) -> "Path | list[Path | None] | None":
        """Refine *image* into image(s) and return their downloaded paths.

        Same contract as :meth:`generate_image`, but the bundled img2img
        template takes an input image: a local file (passed as a
        :class:`pathlib.Path`) is uploaded first, while a ``str`` names an
        image already in the server's input directory.  *mp* scales the
        image toward the budget and *denoise* maps to the sampler's start
        step — lower values keep more of the source composition.
        Delegates to :func:`fabricatio_comfyui.api.generate_img2img`.
        """
        target = first_available(
            (download_dir, self.download_dir, comfyui_config.download_dir),
            "generate_img2img needs a download directory: pass download_dir=, set [ext.comfyui] download_dir, "
            "or set a download_dir on the Role",
        )
        return await generate_img2img(prompt, image, download_dir=target, denoise=denoise, **kwargs)
