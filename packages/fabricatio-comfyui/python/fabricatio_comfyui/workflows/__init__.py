"""Built-in ComfyUI workflow templates.

The templates are minimal ``txt2img`` runs.  Callers wire their own prompt /
size / sampler knobs via :class:`ComfyuiGenerateImage`; the action picks
the bundled :data:`default <workflows/default.json>` template and parameterises it.

In practice users do not need to export their own ComfyUI workflow graphs
— the public surface of this package handles prompt-to-image generation
internally.  This module ships pre-built :class:`fabricatio_core.WorkFlow`
templates for the common cases.
"""

from fabricatio_core import WorkFlow

from fabricatio_comfyui.actions import ComfyuiGenerateImage

__all__ = [
    "Txt2Img",
    "Txt2ImgWithDownload",
]

Txt2Img = WorkFlow(
    name="ComfyUI Txt2Img",
    description="Generate an image from a text prompt via ComfyUI.",
    steps=(
        ComfyuiGenerateImage(
            prompt="${prompt}",
            output_key="comfyui_result",
        ),
    ),
)

Txt2ImgWithDownload = WorkFlow(
    name="ComfyUI Txt2Img with Download",
    description="Generate an image via ComfyUI and save outputs to a local directory.",
    steps=(
        ComfyuiGenerateImage(
            prompt="${prompt}",
            output_key="comfyui_result",
            download_dir="./comfyui_outputs",
        ),
    ),
)
