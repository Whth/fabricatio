"""ComfyUI API integration for Fabricatio.

The package exposes a deliberately narrow, skill-style surface (mirroring
:mod:`fabricatio_skill`): one ``Use*`` capability mixin, module-level
one-shot functions, and bare-noun response models.  Workflow graphs are
an internal implementation detail — external callers supply high-level
knobs (prompt, size, sampler, checkpoint) and never see or operate on a
workflow.

* :class:`UseComfyUI` — capability mixin: ``generate_image`` and friends.
* :func:`generate_image` — one-shot module-level function that hides the
  client lifecycle entirely.
* :class:`ComfyUIHttpClient` / :class:`ComfyUIClientBase` — async REST
  transport (advanced use; accepts only typed knobs, never workflows).
  :func:`fabricatio_comfyui.http_client.get_comfyui_client` keeps one
  process-wide shared client per server URL.
* :class:`GenerateImage` — an ``Action`` subclass usable as a
  ``WorkFlow`` step.
* :data:`comfyui_config` / :class:`ComfyUIConfig` — config singleton
  (``from fabricatio_comfyui.config import comfyui_config``).
"""

from fabricatio_comfyui.actions import GenerateImage
from fabricatio_comfyui.api import generate_image
from fabricatio_comfyui.capabilities.comfyui import UseComfyUI
from fabricatio_comfyui.client_base import ComfyUIClientBase
from fabricatio_comfyui.config import ComfyUIConfig, comfyui_config
from fabricatio_comfyui.http_client import ComfyUIHttpClient
from fabricatio_comfyui.models import (
    ExecutionResult,
    HistoryEntry,
    OutputImage,
    PromptResponse,
    QueueInfo,
    SystemStats,
    UploadResponse,
)

__all__ = [
    "ComfyUIClientBase",
    "ComfyUIConfig",
    "ComfyUIHttpClient",
    "ExecutionResult",
    "GenerateImage",
    "HistoryEntry",
    "OutputImage",
    "PromptResponse",
    "QueueInfo",
    "SystemStats",
    "UploadResponse",
    "UseComfyUI",
    "comfyui_config",
    "generate_image",
]
