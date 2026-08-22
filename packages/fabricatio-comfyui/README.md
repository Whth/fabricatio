# `fabricatio-comfyui`

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/Whth/fabricatio/blob/master/LICENSE)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-comfyui)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-comfyui)](https://pypi.org/project/fabricatio-comfyui/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-comfyui/week)](https://pepy.tech/projects/fabricatio-comfyui)

Async ComfyUI API client for Fabricatio — submit workflow graphs, poll for
completion, and download generated images. Built on `httpx` with full
Pydantic-typed API coverage.

## Architecture

The package is split into small, single-responsibility modules composed through
nominal inheritance — no plugin dicts, no `hasattr`, no duck typing:

| Layer      | Module / Class                                        | Purpose                                                |
|------------|-------------------------------------------------------|--------------------------------------------------------|
| Graph core | `WorkflowCore` (`models/workflow_core.py`)            | Graph container: CRUD, construction, serialization     |
| Graph ops  | `LoaderOps` / `PromptOps` / `SamplerOps` / `ResolutionOps` (`models/workflow_ops.py`) | Typed node-family setters, composed into `Workflow` |
| Workflow   | `Workflow` (`models/workflow.py`)                     | Thin composition: `WorkflowCore` + all `*Ops` ABCs    |
| Client ABC | `ComfyuiClientBase` (`client_base.py`)                | Nominal HTTP client interface                          |
| Client     | `ComfyuiHTTPClient` (`http_client.py`)                | Concrete `httpx`-backed implementation, `async with`   |
| Capability | `Comfyui` (`capabilities/comfyui.py`)                 | Mixin: orchestration (queue → poll → download) + DI    |
| Action     | `ComfyuiGenerateImage`, `ComfyuiUploadImage`          | Pluggable steps for Fabricatio `WorkFlow`              |

Pre-built workflow templates (`Txt2Img`, `Txt2ImgWithDownload`) are also
available as a quick starting point.

## Installation

```bash
pip install fabricatio[comfyui]
# or
uv pip install fabricatio[comfyui]
```

## Configuration

All options below are read through the fabricatio configuration chain (see the
[Configuration Guide](../../docs/source/configuration.rst)). Set them under the
`[ext.comfyui]` table in `fabricatio.toml`, equivalently under
`[tool.fabricatio.ext.comfyui]` in `pyproject.toml`, or via
`FABRICATIO_EXT__COMFYUI__<FIELD_UPPER>` environment variables.

```toml
[ext.comfyui]
base_url = "http://127.0.0.1:8188"
timeout = 300.0
```

| Option | Type | Default | Description |
|---|---|---|---|
| `base_url` | `str` | `"http://127.0.0.1:8188"` | Base URL of the ComfyUI server (default localhost:8188). |
| `timeout` | `float` | `300.0` | Default timeout in seconds for API requests (default 5 min). |

Access at runtime: `from fabricatio_comfyui.config import comfyui_config`.

## Usage

### Standalone client

Use `ComfyuiHTTPClient` directly as an async context manager — no Fabricatio
dependency beyond config:

```python
import asyncio
from fabricatio_comfyui import ComfyuiHTTPClient


async def main() -> None:
    async with ComfyuiHTTPClient.create() as client:
        resp = await client.queue_prompt(workflow)
        result = await client.wait_for_completion(resp.prompt_id)
        if result.succeeded:
            await client.download_images(result, "./outputs")
        for img in result.all_images:
            image_bytes = await client.get_image(img.filename)


asyncio.run(main())
```

### Capability mixin (with a Role)

Mix `Comfyui` into a Role to get `acomfyui_*` predicate-verb methods
(following the same `a`-prefix convention as `UseLLM.aask`):

```python
import asyncio
from fabricatio import Role
from fabricatio_comfyui import Comfyui


class ImageRole(Role, Comfyui):
    """Role with ComfyUI image generation capability."""


async def main() -> None:
    role = ImageRole(name="ComfyUI Worker")
    result = await role.acomfyui_generate(workflow, download_dir="./outputs")
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
result = await role.acomfyui_upload("./input_photo.png")
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

### ComfyuiHTTPClient / Comfyui capability

The HTTP client owns single REST endpoints only. The capability mixin owns
orchestration (queue → poll → download). All capability methods are prefixed
with `acomfyui_`, following the `a`-prefix predicate-verb convention used by
`UseLLM`.

| Client method                    | Capability method                      | Returns                  | Description                                    |
|----------------------------------|----------------------------------------|--------------------------|------------------------------------------------|
| `queue_prompt(workflow)`         | `acomfyui_queue(…)`                    | `PromptResponse`         | Submit a workflow graph for execution          |
| `get_queue_info()`               | `acomfyui_inspect_queue()`             | `QueueInfo`              | Fetch current queue status (running + pending) |
| `get_history(prompt_id)`         | `acomfyui_history(prompt_id)`          | `HistoryEntry \| None`   | Retrieve execution history for a prompt        |
| `wait_for_completion(prompt_id)` | `acomfyui_retrieve(prompt_id)`         | `ComfyuiExecutionResult` | Poll until execution finishes or fails         |
| `get_image(filename, …)`         | `acomfyui_retrieve_image(filename, …)` | `bytes`                  | Download a single generated image              |
| `upload_image(image_path, …)`    | `acomfyui_upload(image_path, …)`       | `UploadResponse`         | Upload an image for img2img workflows          |
| `interrupt()`                    | `acomfyui_interrupt()`                 | `None`                   | Interrupt the currently running workflow       |
| `download_images(result, dir)`   | — (used internally by `acomfyui_generate`) | `None`                | Download all output images concurrently        |
| —                                | `acomfyui_generate(…)`                 | `ComfyuiExecutionResult` | Queue + wait + optionally download images      |

### Actions

| Class                  | Fields                               | Description                          |
|------------------------|--------------------------------------|--------------------------------------|
| `ComfyuiGenerateImage` | `workflow`, `download_dir`, `timeout` | Queue a workflow and wait for images |
| `ComfyuiUploadImage`   | `image_path`, `image_type`           | Upload an image to the server        |

### Models

All API responses are deserialized into frozen Pydantic models. Key types:

| Model                    | Description                                             |
|--------------------------|---------------------------------------------------------|
| `PromptResponse`         | Response from `POST /prompt` — contains `prompt_id`     |
| `ComfyuiExecutionResult` | Final result — `outputs`, `all_images`, `succeeded`     |
| `ComfyuiOutputImage`     | Single image metadata — `filename`, `subfolder`, `type` |
| `HistoryEntry`           | Execution history — `status`, per-node `outputs`        |
| `QueueInfo`              | Queue state — `queue_running`, `queue_pending`          |
| `UploadResponse`         | Upload result — `name`, `subfolder`, `type`             |

### Workflow types (PEP 695)

| Type alias     | Definition            | Description                                      |
|----------------|-----------------------|--------------------------------------------------|
| `NodeInputs`   | `dict[str, Any]`      | Per-node input map (literals + node refs)        |
| `NodeApi`      | `dict[str, Any]`      | Per-node API dict (`class_type`, `inputs`, …)    |
| `WorkflowDict` | `dict[str, NodeApi]`  | Full ComfyUI API-format workflow graph            |

## License

MIT — see the [LICENSE](https://github.com/Whth/fabricatio/blob/master/LICENSE) file.
