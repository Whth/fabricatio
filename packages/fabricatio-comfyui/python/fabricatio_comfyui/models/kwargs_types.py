"""TypedDict keyword-argument specifications for ComfyUI client methods.

Mirrors the pattern in :mod:`fabricatio_core.models.kwargs_types`: each public
method's optional keyword arguments are captured in a frozen ``TypedDict`` so
callers get full IDE completion and type-checking via ``**kwargs: Unpack[...]``.
"""

from pathlib import Path
from typing import Optional, TypedDict


class GenerateKwargs(TypedDict, total=False):
    """Keyword arguments for :meth:`ComfyuiClient.generate`.

    Controls output destination and execution timeout.
    """

    download_dir: Optional[str | Path]
    """Directory to save downloaded images. ``None`` skips download."""

    timeout: Optional[float]
    """Maximum seconds to wait for completion. ``None`` uses config default."""


class GenerateBatchKwargs(TypedDict, total=False):
    """Keyword arguments for batch ComfyUI generation."""

    download_dirs: list[str | Path | None]
    """Per-workflow download directories. ``None`` entries skip download."""

    timeout: Optional[float]
    """Maximum seconds to wait for completion."""


class PollKwargs(TypedDict, total=False):
    """Keyword arguments for :meth:`ComfyuiClient.wait_for_completion`.

    Controls HTTP polling behaviour.
    """

    poll_interval: float
    """Seconds between history polls (default 1.0)."""

    timeout: Optional[float]
    """Maximum seconds before raising ``TimeoutError``."""


class ViewImageKwargs(TypedDict, total=False):
    """Keyword arguments for :meth:`ComfyuiClient.get_image`.

    Selects which server-side image to download.
    """

    subfolder: str
    """Subfolder within the image type directory."""

    image_type: str
    """Directory type: ``output``, ``input``, or ``temp``."""


class UploadKwargs(TypedDict, total=False):
    """Keyword arguments for :meth:`ComfyuiClient.upload_image`.

    Controls upload destination and overwrite behaviour.
    """

    image_type: str
    """Target directory: ``input`` or ``temp``."""

    overwrite: bool
    """Whether to overwrite an existing file with the same name."""


class QueueKwargs(TypedDict, total=False):
    """Keyword arguments for :meth:`ComfyuiClient.queue_prompt`.

    Controls queue placement.
    """

    front: bool
    """If ``True``, enqueue at the front of the queue."""
