"""ComfyUI API integration for Fabricatio.

Provides async ComfyUI client, actions, and workflow templates for
generating images via a ComfyUI server.  Supports all three ComfyUI
API methods: HTTP-only, WebSocket + History, and WebSocket + direct images.
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
from fabricatio_comfyui.models.workflow import ComfyNode, WorkflowBuilder

__all__ = [
    "ComfyNode",
    "Comfyui",
    "ComfyuiClient",
    "ComfyuiConfig",
    "ComfyuiExecutionResult",
    "ComfyuiGenerateImage",
    "ComfyuiNodeRef",
    "ComfyuiOutputImage",
    "ComfyuiUploadImage",
    "WorkflowBuilder",
    "comfyui_config",
]
