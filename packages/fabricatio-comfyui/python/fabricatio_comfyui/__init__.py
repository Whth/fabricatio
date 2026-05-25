"""ComfyUI API integration for Fabricatio.

Provides async ComfyUI client, actions, and workflow templates for
generating images via a ComfyUI server.
"""

from fabricatio_comfyui.actions import ComfyuiGenerateImage, ComfyuiUploadImage
from fabricatio_comfyui.capabilities.comfyui import Comfyui
from fabricatio_comfyui.config import ComfyuiConfig, comfyui_config
from fabricatio_comfyui.models.comfyui import (
    ComfyuiExecutionResult,
    ComfyuiNodeRef,
    ComfyuiOutputImage,
)

__all__ = [
    "Comfyui",
    "ComfyuiConfig",
    "ComfyuiExecutionResult",
    "ComfyuiGenerateImage",
    "ComfyuiNodeRef",
    "ComfyuiOutputImage",
    "ComfyuiUploadImage",
    "comfyui_config",
]
