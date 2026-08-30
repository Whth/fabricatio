"""Minimal fabricatio-comfyui example: one image via the class-based integration.

Boot ComfyUI on 127.0.0.1:8188 (the default), then run:

    uv run --no-sync python examples/comfyui/single_image.py

Image generation runs through the ``GenerateImage`` action composed into a
``WorkFlow`` behind a ``Role`` — the same class you use inside larger
pipelines.  The workflow graph itself is internal to the package; you only
ever supply high-level knobs (prompt, negative_prompt, checkpoint, ...) on
the action.
"""

from fabricatio import Event, Role, Task, WorkFlow
from fabricatio_comfyui import GenerateImage

# Any checkpoint installed on your server (see GET /object_info)
CHECKPOINT = "pasanctuarySDXL_v50.safetensors"

(
    Role.with_bio(name="painter", description="generates images via ComfyUI")
    .subscribe(
        Event.quick_instantiate(ns := "draw"),
        WorkFlow(
            name="ComfyUI single image",
            steps=(
                GenerateImage(
                    prompt="masterpiece, best quality, a calm mountain landscape at sunrise",
                    negative_prompt="worst quality, blurry",
                    checkpoint=CHECKPOINT,
                    download_dir="./outputs",
                ).to_task_output(),
            ),
        ),
    )
    .dispatch()
)

path = Task(name="draw a mountain").delegate_blocking(ns)
if path is None:
    raise SystemExit("generation failed")
print(path)
