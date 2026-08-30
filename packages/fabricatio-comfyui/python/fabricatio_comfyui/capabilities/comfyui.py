"""ComfyUI capability mixin.

Mix into a Role to gain ComfyUI image generation methods.  The public
surface is intentionally **narrow**: callers supply high-level knobs
(``prompt``, ``width``, ``height``, ``seed``, ``steps``, ``cfg```,
``checkpoint``) and the package parameterises a bundled workflow template
internally.  Workflow graphs are an implementation detail — external
callers never see or operate on one.

Method naming follows the ``Use*`` capability pattern of
:mod:`fabricatio_skill` (``UseSkill``): plain verbs (``generate_image``,
``upload_image``, ``get_history`` ...), no ``a``-prefix.

Client lifecycle follows the ``fabricatio-milvus`` pattern: the mixin
holds no client at all.  A module-level ``@cache`` factory keeps one
process-wide shared client (and ``httpx`` connection pool) per base URL,
and :meth:`comfyui_client` fetches it when needed — stateless mixins, no
per-instance binding, no leak-prone ownership.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Unpack

from fabricatio_core.journal import logger

from fabricatio_comfyui.client_base import ComfyUIClientBase
from fabricatio_comfyui.config import comfyui_config
from fabricatio_comfyui.http_client import get_comfyui_client
from fabricatio_comfyui.models.kwargs_types import GenerateKwargs

if TYPE_CHECKING:
    from fabricatio_comfyui.models.comfyui import ExecutionResult, HistoryEntry, QueueInfo, UploadResponse

__all__ = ["UseComfyUI"]


class UseComfyUI:
    """ComfyUI capability mixin — fetches the shared client on demand.

    Usage::

        class ImageRole(Role, UseComfyUI): ...

        result = await ImageRole(name="painter").generate_image(
            "a mountain landscape", download_dir="./outputs",
        )

    All ComfyUI method calls go through the shared cached client
    (:func:`fabricatio_comfyui.http_client.get_comfyui_client`); tests and
    alternate backends patch the factory or pass a custom client to the
    lower-level transport directly.
    """

    def comfyui_client(self) -> ComfyUIClientBase:
        """Return the process-wide shared ComfyUI client for the configured base URL."""
        return get_comfyui_client(comfyui_config.base_url)

    # ------------------------------------------------------------------
    # High-level public surface — only typed knobs, no workflow graphs
    # ------------------------------------------------------------------

    async def generate_image(
        self,
        prompt: str,
        download_dir: str | Path | None = None,
        **kwargs: Unpack[GenerateKwargs],
    ) -> "ExecutionResult":
        """Generate an image from typed knobs using a bundled workflow.

        Queues a bundled template parameterised with the provided knobs,
        polls until completion, and — when ``download_dir`` is given —
        writes the output images there.  Generation knobs
        (:class:`~fabricatio_comfyui.models.kwargs_types.GenerateKwargs`)
        are forwarded verbatim to the client.

        Returns:
            An :class:`~fabricatio_comfyui.models.comfyui.ExecutionResult`
            describing the executed prompt.
        """
        client = self.comfyui_client()
        result = await client.generate(prompt, **kwargs)

        if download_dir is not None and result.succeeded():
            await client.download_images(result, download_dir)

        if result.succeeded():
            logger.info(f"ComfyUI generation completed: {len(result.all_images())} images")
        else:
            logger.error(f"ComfyUI generation failed: {result.error}")
        return result

    async def upload_image(
        self,
        image_path: "str | Path",
        *,
        image_type: str = "input",
    ) -> "UploadResponse":
        """Upload an image to the server."""
        return await self.comfyui_client().upload_image(image_path, image_type=image_type)

    async def interrupt(self) -> None:
        """Interrupt the currently running workflow."""
        await self.comfyui_client().interrupt()
        logger.info("ComfyUI execution interrupted")

    async def get_history(self, prompt_id: str) -> "HistoryEntry | None":
        """Retrieve execution history for *prompt_id*."""
        return await self.comfyui_client().get_history(prompt_id)

    async def get_queue_info(self) -> "QueueInfo":
        """Fetch the current execution queue state."""
        return await self.comfyui_client().get_queue_info()
