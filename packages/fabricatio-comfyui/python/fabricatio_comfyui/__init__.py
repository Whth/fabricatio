"""ComfyUI API integration for Fabricatio.

The package exposes a deliberately narrow public surface:

* :class:`Comfyui` — capability mixin: typed knobs (prompt, size, sampler)
  mapped onto a bundled workflow template.
* :class:`ComfyuiGenerateImage` / :class:`ComfyuiUploadImage` — fabricatio
  ``Action`` subclasses usable as ``WorkFlow`` steps.
* :class:`ComfyuiHTTPClient` / :class:`ComfyuiClientBase` — async REST client.
* :class:`Workflow` — typed graph container for the bundled templates.
* :data:`comfyui_config` / :class:`ComfyuiConfig` — config singleton.

External callers cannot inject raw workflow graphs at the public surface;
the package owns the workflow JSON files under :mod:`fabricatio_comfyui.workflows`.
"""

from fabricatio_comfyui.actions import ComfyuiGenerateImage, ComfyuiUploadImage
from fabricatio_comfyui.capabilities.comfyui import Comfyui
from fabricatio_comfyui.client_base import ComfyuiClientBase
from fabricatio_comfyui.config import ComfyuiConfig, comfyui_config
from fabricatio_comfyui.http_client import ComfyuiHTTPClient
from fabricatio_comfyui.models import (
    RESOLUTION_SELECTOR_ASPECT_RATIOS,
    ComfyuiExecutionResult,
    ComfyuiOutputImage,
    FrameAspect,
    Node,
    PromptResponse,
    QueueInfo,
    UploadResponse,
    Workflow,
    WorkflowDict,
)

__all__ = [
    "RESOLUTION_SELECTOR_ASPECT_RATIOS",
    "Comfyui",
    "ComfyuiClientBase",
    "ComfyuiConfig",
    "ComfyuiExecutionResult",
    "ComfyuiGenerateImage",
    "ComfyuiHTTPClient",
    "ComfyuiOutputImage",
    "ComfyuiUploadImage",
    "FrameAspect",
    "Node",
    "PromptResponse",
    "QueueInfo",
    "UploadResponse",
    "Workflow",
    "WorkflowDict",
    "comfyui_config",
]
