"""TypedDict keyword-argument specifications for ComfyUI client methods.

Mirrors the pattern in :mod:`fabricatio_core.models.kwargs_types`: each public
method's optional keyword arguments are captured in a frozen ``TypedDict`` so
callers get full IDE completion and type-checking via ``**kwargs: Unpack[...]``.
"""

from typing import TypedDict


class GenerateKwargs(TypedDict, total=False):
    """Generation knobs forwarded verbatim to :meth:`ComfyUIClientBase.generate`.

    Only the provided keys override the bundled workflow template; absent
    keys keep the template's values.
    """

    negative_prompt: str | None
    """Optional negative prompt text."""

    width: int | None
    """Output image width (pixels)."""

    height: int | None
    """Output image height (pixels)."""

    seed: int | None
    """Sampler seed; ``None`` keeps the bundled template's seed."""

    steps: int | None
    """Sampler step count."""

    cfg: float | None
    """Classifier-free guidance scale."""

    checkpoint: str | None
    """Checkpoint filename on the server; falls back to config, then the bundled template."""

    timeout: float | None
    """Maximum seconds to wait for completion; ``None`` falls back to :data:`comfyui_config.timeout`."""


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
