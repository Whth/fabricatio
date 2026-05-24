# `fabricatio-comfyui`

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-comfyui)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-comfyui)](https://pypi.org/project/fabricatio-comfyui/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-comfyui/week)](https://pepy.tech/projects/fabricatio-comfyui)

ComfyUI API integration for Fabricatio — generate images by submitting workflows to a ComfyUI server and downloading the results.

## Installation

```bash
pip install fabricatio[comfyui]
# or
uv pip install fabricatio[comfyui]
```

## Configuration

Configure the ComfyUI server URL via environment, `.env`, `fabricatio.toml`, or `pyproject.toml`:

```dotenv
FABRICATIO_COMFYUI__BASE_URL=http://127.0.0.1:8188
FABRICATIO_COMFYUI__TIMEOUT=300
```

Or in `fabricatio.toml`:

```toml
[comfyui]
base_url = "http://127.0.0.1:8188"
timeout = 300
```

## Usage

### Quick Start (capability)

Mix `Comfyui` into a Role and use `comfyui_generate`:

```python
import asyncio
from fabricatio import Role, Task, WorkFlow, Event, logger
from fabricatio_comfyui import Comfyui

class ImageRole(Role, Comfyui):
    """Role with ComfyUI image generation capability."""

async def main():
    role = ImageRole(name="ComfyUI Worker", description="Generates images via ComfyUI.")

    # A workflow exported from ComfyUI in API format
    workflow = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 42, "steps": 20, "cfg": 8,
                "sampler_name": "euler", "scheduler": "normal",
                "denoise": 1,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_base.safetensors"}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 1, "height": 1024, "width": 1024}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": "a serene mountain landscape"}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": "blurry, low quality"}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "fabricatio", "images": ["8", 0]}},
    }

    result = await role.comfyui_generate(workflow, download_dir="./outputs")
    logger.info(f"Generated {len(result.all_images)} image(s) — prompt_id={result.prompt_id}")

asyncio.run(main())
```

### As an Action (in a WorkFlow)

```python
from fabricatio import WorkFlow
from fabricatio_comfyui import ComfyuiGenerateImage

GenerateImage = WorkFlow(
    name="ComfyUI Generate",
    steps=(ComfyuiGenerateImage(workflow=WORKFLOW, download_dir="./outputs"),),
)
```

### Upload an image (for img2img)

```python
result = await role.comfyui_upload_image("./input_photo.png")
```

## API

| Method | Description |
|--------|-------------|
| `comfyui_queue_prompt(workflow)` | Submit a workflow graph, returns `prompt_id` |
| `comfyui_wait_for_completion(prompt_id)` | Poll until execution finishes |
| `comfyui_generate(workflow, download_dir=…)` | Queue + wait + download in one call |
| `comfyui_get_image(filename, …)` | Download a single image by filename |
| `comfyui_upload_image(image_path)` | Upload an image (img2img input) |
| `comfyui_interrupt()` | Stop the current execution |
| `comfyui_get_queue_info()` | Check queue status |
| `comfyui_get_history(prompt_id)` | Get execution history entry |
