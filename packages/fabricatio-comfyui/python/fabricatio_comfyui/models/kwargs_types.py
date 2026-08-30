"""TypedDict keyword-argument specifications for ComfyUI client methods.

Mirrors the pattern in :mod:`fabricatio_core.models.kwargs_types`: each public
method's optional keyword arguments are captured in a frozen ``TypedDict`` so
callers get full IDE completion and type-checking via ``**kwargs: Unpack[...]``.
"""

from typing import TypedDict


class PollKwargs(TypedDict, total=False):
    """Keyword arguments for :meth:`ComfyUIClientBase.wait_for_completion`.

    Controls HTTP polling behaviour.
    """

    poll_interval: float
    """Seconds between history polls (default 1.0)."""

    timeout: float | None
    """Maximum seconds before raising ``TimeoutError``."""


class ViewImageKwargs(TypedDict, total=False):
    """Keyword arguments for :meth:`ComfyUIClientBase.get_image`.

    Selects which server-side image to download.
    """

    subfolder: str
    """Subfolder within the image type directory."""

    image_type: str
    """Directory type: ``output``, ``input``, or ``temp``."""


class UploadKwargs(TypedDict, total=False):
    """Keyword arguments for :meth:`ComfyUIClientBase.upload_image`.

    Controls upload destination and overwrite behaviour.
    """

    image_type: str
    """Target directory: ``input`` or ``temp``."""

    overwrite: bool
    """Whether to overwrite an existing file with the same name."""
