"""``GenerateImage`` action — high-level image generation step.

Use as a step inside a :class:`fabricatio_core.WorkFlow`::

    GenerateImageWorkflow = WorkFlow(
        name="ComfyUI Generate",
        steps=(
            GenerateImage(
                prompt="masterpiece, best quality",
                download_dir="./outputs",
            ),
        ),
    )
"""

from pathlib import Path
from typing import TYPE_CHECKING

from fabricatio_core.models.action import Action

from fabricatio_comfyui.capabilities.comfyui import UseComfyUI

if TYPE_CHECKING:
    from fabricatio_comfyui.models.comfyui import ExecutionResult

__all__ = ["GenerateImage"]


class GenerateImage(Action, UseComfyUI):
    """Generate an image via ComfyUI from typed knobs (no workflow graphs).

    The action parameterises the bundled workflow template with the
    prompt/size/sampler overrides supplied at construction time.  See
    :meth:`UseComfyUI.generate_image` for full parameter documentation.
    """

    output_key: str = "comfyui_result"

    prompt: str
    """Positive prompt text."""

    negative_prompt: str | None = None
    """Optional negative prompt text."""

    width: int | None = None
    """Output image width (pixels)."""

    height: int | None = None
    """Output image height (pixels)."""

    seed: int | None = None
    """Sampler seed; ``None`` keeps the bundled template's seed."""

    steps: int | None = None
    """Sampler step count."""

    cfg: float | None = None
    """Classifier-free guidance scale."""

    checkpoint: str | None = None
    """Checkpoint filename on the server; falls back to config, then the bundled template's checkpoint."""

    download_dir: str | Path | None = None
    """If set, output images are written here."""

    timeout: float | None = None
    """Maximum seconds to wait for completion; ``None`` falls back to :data:`comfyui_config.timeout`."""

    async def _execute(self, **_cxt: object) -> "ExecutionResult":
        """Run :meth:`UseComfyUI.generate_image` with this action's fields."""
        return await self.generate_image(
            prompt=self.prompt,
            negative_prompt=self.negative_prompt,
            width=self.width,
            height=self.height,
            seed=self.seed,
            steps=self.steps,
            cfg=self.cfg,
            checkpoint=self.checkpoint,
            download_dir=self.download_dir,
            timeout=self.timeout,
        )
