"""TypedDict keyword-argument specifications for ComfyUI client methods.

Mirrors the pattern in :mod:`fabricatio_core.models.kwargs_types`: each public
method's optional keyword arguments are captured in a frozen ``TypedDict`` so
callers get full IDE completion and type-checking via ``**kwargs: Unpack[...]``.
"""

from typing import TypedDict

from fabricatio_comfyui.models.graph import LoraSpec
from fabricatio_comfyui.models.resolution import Prop


class TemplateKwargs(TypedDict, total=False):
    """Workflow-template knobs accepted directly by :meth:`ComfyUIClientBase.generate`.

    Only the provided keys override the bundled workflow template; absent
    keys keep the template's values, falling back to :data:`comfyui_config`
    where the config defines a default.
    """

    negative_prompt: str | None
    """Optional negative prompt text."""

    prop: Prop | None
    """Aspect-ratio preset (e.g. :attr:`Prop.prop_16_9`); ``None`` keeps the template's canvas ratio."""

    mp: float | None
    """Megapixel budget of the finished image (``1.0`` = 1,000,000 pixels); ``None`` keeps the template's canvas area."""

    seed: int | None
    """Sampler seed; ``None`` keeps the bundled template's seed."""

    steps: int | None
    """Sampler step count."""

    cfg: float | None
    """Classifier-free guidance scale."""

    checkpoint: str | None
    """Checkpoint filename on the server; falls back to config, then the bundled template."""

    loras: list[LoraSpec] | None
    """LoRAs chained into the generation; each names a server-side file and a strength."""


class GenerateKwargs(TemplateKwargs, total=False):
    """High-level generation knobs for :func:`fabricatio_comfyui.api.generate_image`.

    Inherits every :class:`TemplateKwargs` key and adds *timeout*.
    """

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
