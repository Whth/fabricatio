"""Abstract interface for the ComfyUI HTTP client.

:class:`ComfyuiClientBase` is the nominal contract every ComfyUI HTTP
client must satisfy.  The :class:`Comfyui` capability mixin depends on
this ABC — never on the concrete :class:`ComfyuiHTTPClient` — so that
tests and alternate backends can be wired in through regular inheritance
rather than ``hasattr`` / ``Protocol`` duck-typing.

The ABC owns only the *interface*: typed API wrappers, the async
lifecycle (``__aenter__`` / ``__aexit__`` / ``aclose``), and the concurrent
image download helper.  Workflow *orchestration* (queue → poll → download
as a single call) is deliberately absent — it lives on the capability mixin.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Self, Unpack

from fabricatio_comfyui.models.comfyui import (
    ComfyuiExecutionResult,
    HistoryEntry,
    PromptResponse,
    QueueInfo,
    UploadResponse,
)
from fabricatio_comfyui.models.kwargs_types import (
    PollKwargs,
    QueueKwargs,
    UploadKwargs,
    ViewImageKwargs,
)
from fabricatio_comfyui.models.workflow import Workflow

__all__ = ["ComfyuiClientBase"]


class ComfyuiClientBase(ABC):
    """Abstract async ComfyUI HTTP client.

    Every method corresponds to a single ComfyUI REST endpoint (or a thin
    convenience over one, in the case of :meth:`wait_for_completion` and
    :meth:`download_images`).  No orchestration logic — that belongs to the
    :class:`Comfyui` capability mixin.
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    async def aclose(self) -> None:
        """Close the underlying connection pool."""

    @abstractmethod
    async def __aenter__(self) -> Self:
        """Enter async context — returns ``self``."""

    @abstractmethod
    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit async context — closes the connection pool."""

    # ------------------------------------------------------------------
    # REST endpoints
    # ------------------------------------------------------------------

    @abstractmethod
    async def queue_prompt(
        self,
        workflow: Workflow,
        **kwargs: Unpack[QueueKwargs],
    ) -> PromptResponse:
        """Submit a bundled workflow for execution via ``POST /prompt``.

        The caller owns *workflow* — typically obtained via
        :meth:`fabricatio_comfyui.models.workflow.Workflow.default` or
        :meth:`fabricatio_comfyui.models.workflow.Workflow.from_template`.
        Raw API-format dicts are no longer accepted at the public surface:
        the package narrows input to fully-typed ``Workflow`` instances so
        callers cannot inject unchecked workflow graphs.
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
    ) -> ComfyuiExecutionResult:
        """Poll ``GET /history/{prompt_id}`` until completion."""

    @abstractmethod
    async def download_images(self, result: ComfyuiExecutionResult, download_dir: str | Path) -> None:
        """Download all output images from *result* to *download_dir* concurrently."""
