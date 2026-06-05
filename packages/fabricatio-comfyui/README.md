# `fabricatio-comfyui`

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/Whth/fabricatio/blob/master/LICENSE)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-comfyui)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-comfyui)](https://pypi.org/project/fabricatio-comfyui/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-comfyui/week)](https://pepy.tech/projects/fabricatio-comfyui)

Async ComfyUI API client for Fabricatio — submit workflow graphs, poll for
completion, and download generated images. Built on `httpx` with persistent
connection pooling and full Pydantic-typed API coverage.

## Architecture

The package provides three integration layers, each building on the one below:

| Layer | Class | Purpose |
|-------|-------|---------|
| Client | `ComfyuiClient` | Standalone async HTTP client with connection pooling |
| Capability | `Comfyui` | Mixin that adds ComfyUI methods to a Fabricatio `Role` |
| Action | `ComfyuiGenerateImage`, `ComfyuiUploadImage` | Pluggable steps for Fabricatio `WorkFlow` |

Pre-built workflow templates (`Txt2Img`, `Txt2ImgWithDownload`) are also
available as a quick starting point.

## Installation

```bash
pip install fabricatio[comfyui]
# or
uv pip install fabricatio[comfyui]
```

## Configuration

Configure the ComfyUI server URL via environment, `.env`, `fabricatio.toml`, or
`pyproject.toml`:

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

The config dataclass supports three fields:

| Field | Default | Description |
|-------|---------|-------------|
| `base_url` | `http://127.0.0.1:8188` | ComfyUI server base URL |
| `timeout` | `300.0` | Request timeout in seconds |
| `pool_size` | `10` | Max concurrent connections in the httpx pool |

Access config at runtime: `from fabricatio_comfyui import comfyui_config`

## Usage

### Standalone client

Use `ComfyuiClient` directly as an async context manager — no Fabricatio
dependency beyond config:

```python
import asyncio
from fabricatio_comfyui import ComfyuiClient

async def main() -> None:
    async with ComfyuiClient.create() as client:
        result = await client.generate(workflow, download_dir="./outputs")
        for img in result.all_images:
            image_bytes = await client.get_image(img.filename)

asyncio.run(main())
```

### Capability mixin (with a Role)

Mix `Comfyui` into a Role to get `comfyui_*` methods:

```python
import asyncio
from fabricatio import Role
from fabricatio_comfyui import Comfyui

class ImageRole(Role, Comfyui):
    """Role with ComfyUI image generation capability."""

async def main() -> None:
    role = ImageRole(name="ComfyUI Worker")
    result = await role.comfyui_generate(workflow, download_dir="./outputs")
    for img in result.all_images:
        print(img.filename)

asyncio.run(main())
```

### Action (in a WorkFlow)

Use `ComfyuiGenerateImage` and `ComfyuiUploadImage` as composable steps:

```python
from fabricatio import WorkFlow
from fabricatio_comfyui import ComfyuiGenerateImage, ComfyuiUploadImage

GenerateImage = WorkFlow(
    name="ComfyUI Generate",
    steps=(ComfyuiGenerateImage(workflow=WORKFLOW, download_dir="./outputs"),),
)

UploadThenGenerate = WorkFlow(
    name="Img2Img Pipeline",
    steps=(
        ComfyuiUploadImage(image_path="./input.png"),
        ComfyuiGenerateImage(workflow=IMG2IMG_WORKFLOW),
    ),
)
```

### Upload an image (img2img)

```python
result = await role.comfyui_upload_image("./input_photo.png")
print(result.name)  # filename on the server
```

### Built-in workflow templates

Two minimal templates are provided as quick starting points. In practice, you
should export your own workflows via "Save (API Format)" from the ComfyUI
interface.

```python
from fabricatio_comfyui.workflows import Txt2Img, Txt2ImgWithDownload
```

## API Reference

### ComfyuiClient / Comfyui capability

All methods are available on both `ComfyuiClient` and the `Comfyui` capability
mixin (prefixed with `comfyui_` on the mixin).

| Method | Returns | Description |
|--------|---------|-------------|
| `queue_prompt(workflow)` | `PromptResponse` | Submit a workflow graph for execution |
| `get_queue_info()` | `QueueInfo` | Fetch current queue status (running + pending) |
| `get_history(prompt_id)` | `HistoryEntry \| None` | Retrieve execution history for a prompt |
| `wait_for_completion(prompt_id)` | `ComfyuiExecutionResult` | Poll until execution finishes or fails |
| `generate(workflow, download_dir=…)` | `ComfyuiExecutionResult` | Queue + wait + optionally download images |
| `get_image(filename, …)` | `bytes` | Download a single generated image |
| `upload_image(image_path, …)` | `UploadResponse` | Upload an image for img2img workflows |
| `interrupt()` | `None` | Interrupt the currently running workflow |

### Actions

| Class | Fields | Description |
|-------|--------|-------------|
| `ComfyuiGenerateImage` | `workflow`, `download_dir`, `poll_interval`, `timeout` | Queue a workflow and wait for images |
| `ComfyuiUploadImage` | `image_path`, `image_type` | Upload an image to the server |

### Models

All API responses are deserialized into frozen Pydantic models. Key types:

| Model | Description |
|-------|-------------|
| `PromptResponse` | Response from `POST /prompt` — contains `prompt_id` |
| `ComfyuiExecutionResult` | Final result — `outputs`, `all_images`, `succeeded` |
| `ComfyuiOutputImage` | Single image metadata — `filename`, `subfolder`, `type` |
| `HistoryEntry` | Execution history — `status`, per-node `outputs` |
| `QueueInfo` | Queue state — `queue_running`, `queue_pending` |
| `UploadResponse` | Upload result — `name`, `subfolder`, `type` |

## License

MIT — see the [LICENSE](https://github.com/Whth/fabricatio/blob/master/LICENSE) file.
