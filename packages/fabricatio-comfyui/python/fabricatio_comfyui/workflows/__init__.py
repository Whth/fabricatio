"""Built-in ComfyUI workflow templates.

These are minimal txt2img workflows. In practice, users should export their
own workflows via "Save (API Format)" from the ComfyUI interface and pass
the resulting JSON as the ``workflow`` parameter.
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
    steps=(ComfyuiGenerateImage(output_key="comfyui_result"),),
)

Txt2ImgWithDownload = WorkFlow(
    name="ComfyUI Txt2Img with Download",
    description="Generate an image via ComfyUI and save outputs to a local directory.",
    steps=(ComfyuiGenerateImage(
        output_key="comfyui_result",
        download_dir="./comfyui_outputs",
    ),),
)
