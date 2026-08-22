"""ComfyUI capability mixin.

Mix into a Role to gain ComfyUI image generation methods.  The public
surface is intentionally **narrow**: callers supply high-level knobs
(``prompt``, ``width``, ``height``, ``seed``, ``steps``, ``cfg``) and the
package selects and parameterises a bundled workflow template.  External
callers cannot inject raw workflow graphs — that keeps the public surface
fully typed and the LLM-facing parameter set auditable.

Each instance holds its own :class:`ComfyuiClientBase` (lazily created
from :class:`ComfyuiHTTPClient`), so tests and alternate backends can
inject a client through the ``comfyui_client`` constructor argument — no
``@lru_cache`` global, no ``hasattr`` sniffing.

Predicate-verb methods (``acomfyui_*``) follow the same naming convention
as :class:`fabricatio_core.capabilities.usages.UseLLM` — ``a`` prefix +
domain verb.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fabricatio_core.journal import logger

from fabricatio_comfyui.config import comfyui_config
from fabricatio_comfyui.http_client import ComfyuiHTTPClient
from fabricatio_comfyui.models.workflow import Workflow

if TYPE_CHECKING:
    from pathlib import Path

    from fabricatio_comfyui.client_base import ComfyuiClientBase
    from fabricatio_comfyui.models.comfyui import (
        ComfyuiExecutionResult,
        HistoryEntry,
        QueueInfo,
        UploadResponse,
    )

__all__ = ["Comfyui"]


class Comfyui:
    """ComfyUI capability mixin — owns a per-instance :class:`ComfyuiClientBase`.

    The client is created lazily on first use from
    :meth:`ComfyuiHTTPClient.create`.  Inject a custom client (e.g. a mock)
    via the ``comfyui_client`` constructor argument.  Call :meth:`close`
    to release the connection pool when the mixin is no longer needed.
    """

    _comfyui_client: ComfyuiClientBase | None

    def __init__(self, comfyui_client: ComfyuiClientBase | None = None) -> None:
        """Optionally inject a pre-built client; otherwise created lazily."""
        self._comfyui_client = comfyui_client

    @property
    def comfyui_client(self) -> ComfyuiClientBase:
        """The lazily-created (or injected) :class:`ComfyuiClientBase`."""
        if self._comfyui_client is None:
            self._comfyui_client = ComfyuiHTTPClient.create()
        return self._comfyui_client

    async def close(self) -> None:
        """Close the underlying client if this mixin owns one."""
        if self._comfyui_client is not None:
            await self._comfyui_client.aclose()
            self._comfyui_client = None

    # ------------------------------------------------------------------
    # Template loading — internal, picks the right bundled workflow
    # ------------------------------------------------------------------

    @staticmethod
    def _load_template(template: str | None) -> Workflow:
        """Load a bundled workflow template by name.

        ``template`` is the stem of a ``.json`` file under
        :mod:`fabricatio_comfyui.workflows` (``"default"`` → ``default.json``).
        When ``None``, falls back to :meth:`Workflow.default`.
        """
        if template is None:
            return Workflow.default()
        return Workflow.from_template(template)

    # ------------------------------------------------------------------
    # High-level public surface — only typed knobs, no raw workflow dicts
    # ------------------------------------------------------------------

    async def acomfyui_generate(  # noqa: PLR0913 — public API keeps every override explicit
        self,
        prompt: str,
        *,
        negative_prompt: str | None = None,
        width: int | None = None,
        height: int | None = None,
        seed: int | None = None,
        steps: int | None = None,
        cfg: float | None = None,
        template: str | None = None,
        download_dir: str | Path | None = None,
        timeout: float | None = None,
    ) -> ComfyuiExecutionResult:
        """Generate an image from typed knobs using a bundled workflow.

        Returns:
            A :class:`~fabricatio_comfyui.models.comfyui.ComfyuiExecutionResult`
            describing the executed prompt.  When *download_dir* is provided,
            output images are written there.
        """
        wf = self._load_template(template)

        if prompt:
            wf.set_positive_prompt(prompt)
        if negative_prompt is not None:
            wf.set_negative_prompt(negative_prompt)
        if width is not None or height is not None:
            wf.set_resolution(width=width, height=height)
        if seed is not None or steps is not None or cfg is not None:
            wf.set_sampler(seed=seed, steps=steps, cfg=cfg)

        effective_timeout = timeout or comfyui_config.timeout

        client = self.comfyui_client
        resp = await client.queue_prompt(wf)
        result = await client.wait_for_completion(resp.prompt_id, timeout=effective_timeout)

        if download_dir is not None and result.succeeded:
            await client.download_images(result, download_dir)

        if result.succeeded:
            logger.info(f"ComfyUI generation completed: {len(result.all_images)} images")
        else:
            logger.error(f"ComfyUI generation failed: {result.error}")
        return result

    async def acomfyui_upload(
        self,
        image_path: str | Path,
        *,
        image_type: str = "input",
        overwrite: bool = True,
    ) -> UploadResponse:
        """Upload an image to the server."""
        resp = await self.comfyui_client.upload_image(image_path, image_type=image_type, overwrite=overwrite)
        logger.info(f"Uploaded image -> {resp.name}")
        return resp

    async def acomfyui_interrupt(self) -> None:
        """Interrupt the currently running workflow."""
        await self.comfyui_client.interrupt()
        logger.info("ComfyUI execution interrupted")

    async def acomfyui_history(self, prompt_id: str) -> HistoryEntry | None:
        """Retrieve execution history for *prompt_id*."""
        return await self.comfyui_client.get_history(prompt_id)

    async def acomfyui_inspect_queue(self) -> QueueInfo:
        """Fetch the current execution queue state."""
        return await self.comfyui_client.get_queue_info()
