"""ComfyUI capability mixin.

Mix into a Role to gain ComfyUI image generation methods.  The public
surface is intentionally **narrow**: callers supply high-level knobs
(``prompt``, ``width``, ``height``, ``seed``, ``steps``, ``cfg``,
``checkpoint``) and the package parameterises a bundled workflow template
internally.  Workflow graphs are an implementation detail — external
callers never see or operate on one.

Method naming follows the ``Use*`` capability pattern of
:mod:`fabricatio_skill` (``UseSkill``): plain verbs (``generate_image``,
``upload_image``, ``get_history`` ...), no ``a``-prefix.

Each instance holds its own :class:`ComfyUIClientBase` (lazily created
from :class:`ComfyUIHttpClient`), so tests and alternate backends can
inject a client via :meth:`with_comfyui_client` — no ``@lru_cache``
global, no ``hasattr`` sniffing.
"""

from typing import TYPE_CHECKING, Self, Unpack

from fabricatio_core.journal import logger

from fabricatio_comfyui.http_client import ComfyUIHttpClient
from fabricatio_comfyui.models.kwargs_types import GenerateKwargs

if TYPE_CHECKING:
    from pathlib import Path

    from fabricatio_comfyui.client_base import ComfyUIClientBase
    from fabricatio_comfyui.models.comfyui import (
        ExecutionResult,
        HistoryEntry,
        QueueInfo,
        UploadResponse,
    )

__all__ = ["UseComfyUI"]


class UseComfyUI:
    """ComfyUI capability mixin — owns a per-instance :class:`ComfyUIClientBase`.

    Mix into a Role or Action to generate images from typed knobs without
    ever touching a workflow graph::

        class ImageRole(Role, UseComfyUI): ...

        result = await role.generate_image("a mountain landscape", download_dir="./outputs")

    The workflow graph is built internally from the bundled templates;
    callers supply only high-level knobs.
    """

    _comfyui_client: "ComfyUIClientBase | None" = None

    @classmethod
    def with_comfyui_client(cls, comfyui_client: "ComfyUIClientBase") -> Self:
        """Create an instance bound to a pre-built client (tests / alternate backends)."""
        instance = cls()
        instance._comfyui_client = comfyui_client
        return instance

    @property
    def comfyui_client(self) -> "ComfyUIClientBase":
        """The lazily-created (or injected) :class:`ComfyUIClientBase`."""
        if self._comfyui_client is None:
            self._comfyui_client = ComfyUIHttpClient.create()
        return self._comfyui_client

    async def close(self) -> None:
        """Close the underlying client if this mixin owns one."""
        if self._comfyui_client is not None:
            await self._comfyui_client.aclose()
            self._comfyui_client = None

    # ------------------------------------------------------------------
    # High-level public surface — only typed knobs, no workflow graphs
    # ------------------------------------------------------------------

    async def generate_image(
        self,
        prompt: str,
        **kwargs: Unpack[GenerateKwargs],
    ) -> "ExecutionResult":
        """Generate an image from typed knobs using a bundled workflow.

        Queues a bundled template parameterised with the provided knobs,
        polls until completion, and — when ``download_dir`` is given —
        writes the output images there.

        Returns:
            An :class:`~fabricatio_comfyui.models.comfyui.ExecutionResult`
            describing the executed prompt.
        """
        download_dir = kwargs.pop("download_dir", None)
        timeout = kwargs.pop("timeout", None)

        client = self.comfyui_client
        result = await client.generate(prompt, timeout=timeout, **kwargs)

        if download_dir is not None and result.succeeded:
            await client.download_images(result, download_dir)

        if result.succeeded:
            logger.info(f"ComfyUI generation completed: {len(result.all_images)} images")
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
        return await self.comfyui_client.upload_image(image_path, image_type=image_type)

    async def interrupt(self) -> None:
        """Interrupt the currently running workflow."""
        await self.comfyui_client.interrupt()
        logger.info("ComfyUI execution interrupted")

    async def get_history(self, prompt_id: str) -> "HistoryEntry | None":
        """Retrieve execution history for *prompt_id*."""
        return await self.comfyui_client.get_history(prompt_id)

    async def get_queue_info(self) -> "QueueInfo":
        """Fetch the current execution queue state."""
        return await self.comfyui_client.get_queue_info()
