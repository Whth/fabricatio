# `fabricatio-comfyui`

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/Whth/fabricatio/blob/master/LICENSE)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-comfyui)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-comfyui)](https://pypi.org/project/fabricatio-comfyui/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-comfyui/week)](https://pepy.tech/projects/fabricatio-comfyui)

Async ComfyUI API client for Fabricatio — generate images from typed
parameters and download results. Built on `httpx` with full Pydantic-typed
API coverage.

## Design: bundled workflows only

The package owns its workflow JSON files (`workflows/*.json`). Callers never
pass raw workflow graphs — they supply high-level knobs
(`prompt`, `negative_prompt`, `width`, `height`, `seed`, `steps`, `cfg`) and
the package selects and parameterises a bundled template
(`Workflow.from_template(name)` / `Workflow.default()`).
This keeps the public surface fully statically typed: no
`dict[str, Any]` workflow injection anywhere in capability or action signatures.

## Architecture

| Layer      | Module / Class                                        | Purpose                                                |
|------------|-------------------------------------------------------|--------------------------------------------------------|
| Graph core | `WorkflowCore` (`models/workflow_core.py`)            | Graph container: CRUD, construction, serialization     |
| Graph ops  | `LoaderOps` / `PromptOps` / `SamplerOps` / `ResolutionOps` (`models/workflow_ops.py`) | Typed node-family setters, composed into `Workflow` |
| Workflow   | `Workflow` (`models/workflow.py`)                     | Composition: `WorkflowCore` + all `*Ops`; `from_template()` |
| Client ABC | `ComfyuiClientBase` (`client_base.py`)                | Nominal HTTP client interface                          |
| Client     | `ComfyuiHTTPClient` (`http_client.py`)                | Concrete `httpx`-backed implementation, `async with`   |
| Capability | `Comfyui` (`capabilities/comfyui.py`)                 | Mixin: high-level generate (queue → poll → download)   |
| Action     | `ComfyuiGenerateImage`, `ComfyuiUploadImage`          | Pluggable steps for Fabricatio `WorkFlow`              |

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

### Capability mixin (with a Role)

Mix `Comfyui` into a Role to get the `acomfyui_*` predicate-verb methods
(following the same `a`-prefix convention as `UseLLM.aask`):

```python
import asyncio
from fabricatio import Role
from fabricatio_comfyui import Comfyui


class ImageRole(Role, Comfyui):
    """Role with ComfyUI image generation capability."""


async def main() -> None:
    role = ImageRole(name="ComfyUI Worker")
    result = await role.acomfyui_generate(
        "masterpiece, best quality, a mountain landscape",
        negative_prompt="worst quality, blurry",
        width=1024,
        height=768,
        download_dir="./outputs",
    )
    for img in result.all_images:
        print(img.filename)


asyncio.run(main())
```

### Standalone client

The HTTP client is a lower-level transport; it accepts `Workflow`
instances built from the bundled templates:

```python
import asyncio
from fabricatio_comfyui import ComfyuiHTTPClient, Workflow


async def main() -> None:
    wf = Workflow.default()
    wf.set_positive_prompt("a mountain landscape")

    async with ComfyuiHTTPClient.create() as client:
        resp = await client.queue_prompt(wf)
        result = await client.wait_for_completion(resp.prompt_id)
        if result.succeeded:
            await client.download_images(result, "./outputs")


asyncio.run(main())
```

### Action (in a WorkFlow)

Use `ComfyuiGenerateImage` and `ComfyuiUploadImage` as composable steps:

```python
from fabricatio import WorkFlow
from fabricatio_comfyui import ComfyuiGenerateImage, ComfyuiUploadImage

GenerateImage = WorkFlow(
    name="ComfyUI Generate",
    steps=(
        ComfyuiGenerateImage(
            prompt="masterpiece, best quality",
            download_dir="./outputs",
        ),
    ),
)
```

### Built-in workflow templates

Pre-built `WorkFlow` templates are available as quick starting points:

```python
from fabricatio_comfyui.workflows import Txt2Img, Txt2ImgWithDownload
```

Both run the bundled `default.json` graph; wire your own prompt through the
step's fields when composing custom pipelines.

## API Reference

### Capability methods

| Method                              | Description                                    |
|-------------------------------------|------------------------------------------------|
| `acomfyui_generate(prompt, …)`      | Queue a bundled template with overrides → poll → optionally download |
| `acomfyui_upload(image_path, …)`    | Upload an image for img2img workflows          |
| `acomfyui_history(prompt_id)`       | Retrieve execution history for a prompt        |
| `acomfyui_inspect_queue()`          | Fetch current queue status                     |
| `acomfyui_interrupt()`              | Interrupt the currently running workflow       |

`acomfyui_generate` keyword parameters: `negative_prompt`, `width`,
`height`, `seed`, `steps`, `cfg`, `template` (bundled template name),
`download_dir`, `timeout`.

### Client methods (`ComfyuiHTTPClient` / `ComfyuiClientBase`)

| Method                            | Returns                  | Description                             |
|-----------------------------------|--------------------------|-----------------------------------------|
| `queue_prompt(workflow)`          | `PromptResponse`         | Submit a `Workflow` for execution       |
| `get_queue_info()`                | `QueueInfo`              | Fetch current queue status              |
| `get_history(prompt_id)`          | `HistoryEntry \| None`   | Retrieve execution history for a prompt |
| `wait_for_completion(prompt_id)`  | `ComfyuiExecutionResult` | Poll until execution finishes           |
| `get_image(filename, …)`          | `bytes`                  | Download a single generated image       |
| `upload_image(image_path, …)`     | `UploadResponse`         | Upload an image                         |
| `interrupt()`                     | `None`                   | Interrupt the running workflow          |
| `download_images(result, dir)`    | `None`                   | Download all output images concurrently |

### Actions

| Class                  | Fields                                                                 | Description                          |
|------------------------|------------------------------------------------------------------------|--------------------------------------|
| `ComfyuiGenerateImage` | `prompt`, `negative_prompt`, `width`, `height`, `seed`, `steps`, `cfg`, `template`, `download_dir`, `timeout` | Generate images from typed knobs |
| `ComfyuiUploadImage`   | `image_path`, `image_type`                                             | Upload an image to the server        |

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
