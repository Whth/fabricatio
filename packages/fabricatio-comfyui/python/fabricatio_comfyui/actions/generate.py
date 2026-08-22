"""``ComfyuiGenerateImage`` action — high-level image generation step.

Use as a step inside a :class:`fabricatio_core.WorkFlow`::

    GenerateImage = WorkFlow(
        name="ComfyUI Generate",
        steps=(
            ComfyuiGenerateImage(
                prompt="masterpiece, best quality",
                download_dir="./outputs",
            ),
        ),
    )
"""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 — pydantic forward-ref needs this at runtime
from typing import TYPE_CHECKING

from fabricatio_core.models.action import Action

from fabricatio_comfyui.capabilities.comfyui import Comfyui
from fabricatio_comfyui.config import comfyui_config

if TYPE_CHECKING:
    from fabricatio_comfyui.models.comfyui import ComfyuiExecutionResult

__all__ = ["ComfyuiGenerateImage"]


class ComfyuiGenerateImage(Action, Comfyui):
    """Generate an image via ComfyUI from typed knobs (no raw workflow injection).

    The action loads a bundled workflow template (``template="default"`` by
    default) and parameterises it with the prompt/size/sampler overrides
    supplied at construction time.  See :meth:`Comfyui.acomfyui_generate`
    for full parameter documentation.
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

    template: str | None = None
    """Bundled workflow template name (``"default"`` if unset)."""

    download_dir: str | Path | None = None
    """If set, output images are written here."""

    timeout: float | None = None
    """Maximum seconds to wait for completion; ``None`` falls back to :data:`comfyui_config.timeout`."""

    async def _execute(self, **_cxt: object) -> ComfyuiExecutionResult:
        """Run :meth:`Comfyui.acomfyui_generate` with this action's fields."""
        return await self.acomfyui_generate(
            prompt=self.prompt,
            negative_prompt=self.negative_prompt,
            width=self.width,
            height=self.height,
            seed=self.seed,
            steps=self.steps,
            cfg=self.cfg,
            template=self.template,
            download_dir=self.download_dir,
            timeout=self.timeout or comfyui_config.timeout,
        )
