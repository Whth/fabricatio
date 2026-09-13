"""Configuration for fabricatio-comfyui."""

from fabricatio_core import CONFIG
from pydantic import BaseModel

from fabricatio_comfyui.models.catalog import LoraEntry
from fabricatio_comfyui.models.resolution import Prop

__all__ = ["ComfyUIConfig", "comfyui_config"]


class ComfyUIConfig(BaseModel):
    """Configuration for the ComfyUI API client."""

    base_url: str = "http://127.0.0.1:8188"
    """Base URL of the ComfyUI server (default localhost:8188)."""

    timeout: float = 300.0
    """Default timeout in seconds for API requests (default 5 min)."""

    mp: float | None = None
    """Default megapixel budget of the finished image (``1.0`` = 1,000,000 pixels).

    Resolves every generation's canvas from this budget and :attr:`prop`;
    the two-pass template sizes its base canvas so the upscaled output
    lands at the budget.  A per-call ``mp=`` / ``prop=`` knob takes
    precedence.  ``None`` keeps the active template's built-in canvas
    (768x512 for the two-pass template, 1344x1024 for the anima preset).
    """

    prop: Prop | None = None
    """Default aspect-ratio preset applied to every generation.

    TOML takes enum member names like ``"prop_16_9"`` (the member values).
    Pairs with :attr:`mp`; a per-call ``prop=`` knob takes precedence.
    ``None`` keeps the active template's canvas ratio.
    """

    checkpoint: str | None = None
    """Default checkpoint filename on the server.

    Overrides the template's checkpoint — the bundled default or the
    anima placeholder — for every generation; a per-call ``checkpoint=``
    knob takes precedence.
    """

    anima_checkpoint: str | None = None
    """Default checkpoint filename for :meth:`ComfyUIClientBase.generate_anima`.

    The anima template's model filenames are placeholders in source;
    this key (and ``anima_clip`` / ``anima_vae``) supplies the real
    server-side filenames.  Generation fails loudly while unset.
    """

    anima_clip: str | None = None
    """Default CLIP filename for :meth:`ComfyUIClientBase.generate_anima` (see ``anima_checkpoint``)."""

    anima_vae: str | None = None
    """Default VAE filename for :meth:`ComfyUIClientBase.generate_anima` (see ``anima_checkpoint``)."""

    download_dir: str | None = None
    """Default directory for generated images.

    Used by :meth:`UseComfyUI.generate_image` (and
    :func:`fabricatio_comfyui.api.generate_image`) when no per-call
    ``download_dir`` is given; the directory is created on demand.
    """

    choose_loras_template: str = "built-in/lora_selection"
    """Template used by :meth:`ChooseLoras.choose_loras` to render the LoRA-selection prompt."""

    loras: tuple[LoraEntry, ...] = ()
    """User-declared LoRAs the LLM may choose from (see :mod:`fabricatio_comfyui.models.catalog`)."""


comfyui_config = CONFIG.load("comfyui", ComfyUIConfig)
"""Singleton ComfyUI config loaded from fabricatio config chain."""
