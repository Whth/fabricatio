"""ComfyUI capability mixin.

Mix into a Role to gain ComfyUI image generation methods.  The public
surface is intentionally **narrow**: callers supply high-level knobs
(``prompt``, ``prop``, ``mp``, ``seed``, ``steps``, ``cfg``,
``checkpoint``) and the package parameterises a bundled workflow template
internally.  Workflow graphs are an implementation detail — external
callers never see or operate on one.

Method naming follows the ``Use*`` capability pattern of
:mod:`fabricatio_skill` (``UseSkill``): plain verbs (``generate_image``
...), no ``a``-prefix.

Client lifecycle follows the ``fabricatio-milvus`` pattern: the mixin
holds no client at all.  A module-level ``@cache`` factory keeps one
process-wide shared client (and ``httpx`` connection pool) per base URL,
and :meth:`comfyui_client` fetches it when needed — stateless mixins, no
per-instance binding, no leak-prone ownership.
"""

from pathlib import Path
from typing import Unpack, overload

from fabricatio_core.utils import first_available

from fabricatio_comfyui.api import generate_image
from fabricatio_comfyui.config import comfyui_config
from fabricatio_comfyui.models.comfyui import ComfyUIScopedConfig
from fabricatio_comfyui.models.kwargs_types import GenerateKwargs

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
