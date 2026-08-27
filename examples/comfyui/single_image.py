"""Minimal fabricatio-comfyui example against a local ComfyUI server.

Boot ComfyUI on 127.0.0.1:8188 (the default), then run:

    uv run --no-sync python examples/comfyui/single_image.py

The bundled template's default checkpoint is not installed on every
server, so we pick one from the local ``models/checkpoints`` list via
``Workflow.with_checkpoint`` (list yours with ``GET /object_info``).
"""

import asyncio

from fabricatio_comfyui import ComfyuiHTTPClient, Workflow

# Any checkpoint installed on your server (see /object_info)
CHECKPOINT = "pasanctuarySDXL_v50.safetensors"


async def main() -> None:
    """Queue a single SDXL image generation and download the result."""
    wf = (
        Workflow.default()
        .with_checkpoint(CHECKPOINT)
        .with_positive_prompt("masterpiece, best quality, a calm mountain landscape at sunrise")
        .with_negative_prompt("worst quality, blurry")
    )

    async with ComfyuiHTTPClient.create() as client:
        resp = await client.queue_prompt(wf)
        result = await client.wait_for_completion(resp.prompt_id)
        if not result.succeeded:
            raise SystemExit(f"generation failed: {result.error}")
        await client.download_images(result, "./outputs")
        for _img in result.all_images:
            pass


asyncio.run(main())
