"""Abstract interface for the ComfyUI HTTP client.

:class:`ComfyUIClientBase` is the nominal contract every ComfyUI HTTP
client must satisfy.  The :class:`UseComfyUI` capability mixin depends on
this ABC — never on the concrete :class:`ComfyUIHttpClient` — so that
tests and alternate backends can be wired in through regular inheritance
rather than ``hasattr`` / ``Protocol`` duck-typing.

The ABC owns only the *interface*: typed API wrappers, the async
lifecycle (``__aenter__`` / ``__aexit__`` / ``aclose``), and the concurrent
image download helper.  Workflow graphs never cross this surface — the
client accepts high-level knobs (:meth:`generate`) and builds the bundled
workflow internally.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from types import TracebackType
from typing import Self, Unpack

from fabricatio_comfyui.models.comfyui import (
    ExecutionResult,
    HistoryEntry,
    QueueInfo,
    UploadResponse,
)
from fabricatio_comfyui.models.kwargs_types import (
    PollKwargs,
    TemplateKwargs,
    UploadKwargs,
    ViewImageKwargs,
)

__all__ = ["ComfyUIClientBase"]


class ComfyUIClientBase(ABC):
    """Abstract async ComfyUI HTTP client.

    Every method corresponds to a single ComfyUI REST endpoint (or a thin
    convenience over one, in the case of :meth:`wait_for_completion` and
    :meth:`download_images`).  No orchestration logic — that belongs to the
    :class:`UseComfyUI` capability mixin.
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    async def aclose(self) -> None:
        """Close the underlying connection pool."""

    async def __aenter__(self) -> Self:
        """Enter async context — returns ``self``."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit async context — closes the connection pool."""
        await self.aclose()

    # ------------------------------------------------------------------
    # REST endpoints
    # ------------------------------------------------------------------

    @abstractmethod
    async def generate(
        self,
        prompt: str | list[str],
        *,
        front: bool = False,
        timeout: float | None = None,
        **kwargs: Unpack[TemplateKwargs],
    ) -> list[ExecutionResult]:
        """Queue one or more prompts and poll each to completion.

        The workflow graph is built internally from the bundled template —
        callers never see or construct one.  Keyword knobs
        (:class:`~fabricatio_comfyui.models.kwargs_types.TemplateKwargs`)
        override the active template only where provided: *mp* and *prop*
        size the latent canvas (a per-call value wins over
        :data:`comfyui_config`, and unset knobs keep the template's own
        canvas), *checkpoint* falls back to config then the template, and
        the remaining keys are direct template-level overrides.
        *front* enqueues at the head of the queue and *timeout* bounds each
        poll — both are queueing knobs consumed by the client and never
        reach the template.  Prompts run sequentially; the return holds one
        execution result per input prompt, in input order, without
        downloading images.
        """

    @abstractmethod
    async def get_queue_info(self) -> QueueInfo:
        """Get current queue status via ``GET /queue``."""

    @abstractmethod
    async def get_history(self, prompt_id: str) -> HistoryEntry | None:
        """Get execution history via ``GET /history/{prompt_id}``."""

    @abstractmethod
    async def interrupt(self) -> None:
        """Interrupt the currently running workflow via ``POST /interrupt``."""

    @abstractmethod
    async def get_image(
        self,
        filename: str,
        **kwargs: Unpack[ViewImageKwargs],
    ) -> bytes:
        """Download a generated image via ``GET /view``."""

    @abstractmethod
    async def upload_image(
        self,
        image_path: str | Path,
        **kwargs: Unpack[UploadKwargs],
    ) -> UploadResponse:
        """Upload an image via ``POST /upload/image``."""

    # ------------------------------------------------------------------
    # Thin conveniences (still single-endpoint, no orchestration)
    # ------------------------------------------------------------------

    @abstractmethod
    async def wait_for_completion(
        self,
        prompt_id: str,
        **kwargs: Unpack[PollKwargs],
    ) -> ExecutionResult:
        """Poll ``GET /history/{prompt_id}`` until completion."""

    @abstractmethod
    async def download_images(self, result: ExecutionResult, download_dir: str | Path) -> list[Path]:
        """Download all output images from *result* to *download_dir* concurrently.

        Returns the local path of every downloaded image.
        """

    @abstractmethod
    async def download_first_image(self, result: ExecutionResult, download_dir: str | Path) -> Path | None:
        """Download the first output image from *result* to *download_dir* and return its local path.

        Returns ``None`` when *result* holds no output images.
        """
