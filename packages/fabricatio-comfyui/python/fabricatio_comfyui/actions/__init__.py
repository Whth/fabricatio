"""Actions for ComfyUI image generation workflow."""

from pathlib import Path
from typing import Any

from fabricatio_core.journal import logger
from fabricatio_core.models.action import Action
from fabricatio_core.utils import ok

from fabricatio_comfyui.capabilities.comfyui import Comfyui
from fabricatio_comfyui.config import comfyui_config
from fabricatio_comfyui.models.comfyui import ComfyuiExecutionResult, UploadResponse

__all__ = [
    "ComfyuiGenerateImage",
    "ComfyuiUploadImage",
]


class ComfyuiGenerateImage(Action, Comfyui):
    """Queue a ComfyUI workflow and wait for the generated images.

    The ``workflow`` field should contain a full ComfyUI workflow graph
    (exported via "Save (API Format)" from the ComfyUI interface).
    Use ``download_dir`` to save images locally.
    """

    output_key: str = "comfyui_result"

    workflow: dict[str, Any] = None  # type: ignore[assignment]
    """The ComfyUI workflow graph to execute."""

    download_dir: str | Path | None = None
    """If set, download output images to this directory."""

    poll_interval: float = 1.0
    """Seconds between progress polling requests."""

    timeout: float | None = None
    """Maximum seconds to wait for completion."""

    async def _execute(self, *_: Any, **cxt: Any) -> ComfyuiExecutionResult:
        workflow = ok(self.workflow, "ComfyuiGenerateImage requires a `workflow` dict")
        logger.info("Starting ComfyUI image generation")

        return await self.comfyui_generate(
            workflow=workflow,
            download_dir=self.download_dir,
            poll_interval=self.poll_interval,
            timeout=self.timeout or comfyui_config.timeout,
        )


class ComfyuiUploadImage(Action, Comfyui):
    """Upload an image to the ComfyUI server (e.g. for img2img workflows)."""

    output_key: str = "comfyui_upload_result"

    image_path: str | Path = None  # type: ignore[assignment]
    """Path to the image file to upload."""

    image_type: str = "input"
    """Target directory: ``input`` or ``temp``."""

    async def _execute(self, *_: Any, **cxt: Any) -> UploadResponse:
        p = Path(ok(self.image_path, "ComfyuiUploadImage requires an `image_path`"))
        logger.info(f"Uploading image {p.name} to ComfyUI")
        return await self.comfyui_upload_image(
            image_path=p,
            image_type=self.image_type,
        )
