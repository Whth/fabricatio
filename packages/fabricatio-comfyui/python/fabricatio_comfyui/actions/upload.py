"""``ComfyuiUploadImage`` action — upload a local image to the ComfyUI server.

The uploaded image can be consumed by an upstream bundled img2img workflow;
this action does not run any workflow itself.
"""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 — pydantic forward-ref needs this at runtime
from typing import TYPE_CHECKING

from fabricatio_core.models.action import Action

from fabricatio_comfyui.capabilities.comfyui import Comfyui

if TYPE_CHECKING:
    from fabricatio_comfyui.models.comfyui import UploadResponse

__all__ = ["ComfyuiUploadImage"]


class ComfyuiUploadImage(Action, Comfyui):
    """Upload a local image to the ComfyUI server."""

    output_key: str = "comfyui_upload_result"

    image_path: str | Path
    """Path to the image file to upload."""

    image_type: str = "input"
    """Target directory on the server: ``"input"`` or ``"temp"``."""

    async def _execute(self, **_cxt: object) -> UploadResponse:
        """Run :meth:`Comfyui.acomfyui_upload` with this action's fields."""
        return await self.acomfyui_upload(image_path=self.image_path, image_type=self.image_type)
