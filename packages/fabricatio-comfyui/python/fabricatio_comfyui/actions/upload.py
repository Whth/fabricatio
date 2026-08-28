"""``UploadImage`` action — upload a local image to the ComfyUI server.

The uploaded image can be consumed by an upstream img2img workflow; this
action does not run any workflow itself.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from fabricatio_core.models.action import Action

from fabricatio_comfyui.capabilities.comfyui import UseComfyUI

if TYPE_CHECKING:
    from fabricatio_comfyui.models.comfyui import UploadResponse

__all__ = ["UploadImage"]


class UploadImage(Action, UseComfyUI):
    """Upload a local image to the ComfyUI server."""

    output_key: str = "comfyui_upload_result"

    image_path: str | Path
    """Path to the image file to upload."""

    image_type: str = "input"
    """Target directory on the server: ``"input"`` or ``"temp"``."""

    async def _execute(self, **_cxt: object) -> "UploadResponse":
        """Run :meth:`UseComfyUI.upload_image` with this action's fields."""
        return await self.upload_image(image_path=self.image_path, image_type=self.image_type)
