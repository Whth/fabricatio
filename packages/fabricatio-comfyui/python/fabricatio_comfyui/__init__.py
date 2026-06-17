"""ComfyUI API integration for Fabricatio.

Provides async ComfyUI client, actions, and workflow templates for
generating images via a ComfyUI server over HTTP.
"""

from fabricatio_comfyui.actions import ComfyuiGenerateImage, ComfyuiUploadImage
from fabricatio_comfyui.capabilities.comfyui import Comfyui
from fabricatio_comfyui.client import ComfyuiClient
from fabricatio_comfyui.config import ComfyuiConfig, comfyui_config
from fabricatio_comfyui.models.comfyui import (
    ComfyuiExecutionResult,
    ComfyuiNodeRef,
    ComfyuiOutputImage,
)
from fabricatio_comfyui.models.kwargs_types import (
    GenerateBatchKwargs,
    GenerateKwargs,
    PollKwargs,
    QueueKwargs,
    UploadKwargs,
    ViewImageKwargs,
)
from fabricatio_comfyui.models.workflow import Node, NodeRef, Workflow
from fabricatio_comfyui.pool import close_all, get_client

__all__ = [
    "Comfyui",
    "ComfyuiClient",
    "ComfyuiConfig",
    "ComfyuiExecutionResult",
    "ComfyuiGenerateImage",
    "ComfyuiNodeRef",
    "ComfyuiOutputImage",
    "ComfyuiUploadImage",
    "GenerateBatchKwargs",
    "GenerateKwargs",
    "Node",
    "NodeRef",
    "PollKwargs",
    "QueueKwargs",
    "UploadKwargs",
    "ViewImageKwargs",
    "Workflow",
    "close_all",
    "comfyui_config",
    "get_client",
]
