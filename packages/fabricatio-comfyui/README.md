# `fabricatio-comfyui`

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/Whth/fabricatio/blob/master/LICENSE)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-comfyui)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-comfyui)](https://pypi.org/project/fabricatio-comfyui/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-comfyui/week)](https://pepy.tech/projects/fabricatio-comfyui)

Async ComfyUI API integration for Fabricatio — generate images from typed
knobs and download the results. Built on `httpx` with full Pydantic-typed
API coverage.

## Design: workflows are fully internal

The package owns its workflow graph: it is initialised entirely in Python
code (an internal typed `Graph` model) and serialized to ComfyUI's API
format only on submission. Callers never see, construct, or operate on a
workflow — they supply high-level knobs (`prompt`, `negative_prompt`,
`width`, `height`, `seed`, `steps`, `cfg`, `checkpoint`) and the package
parameterises the built-in template internally. There is no `dict[str, Any]`
workflow injection anywhere in the public signatures.

Naming follows `fabricatio-skill`: one `Use*` capability mixin
(`UseComfyUI`), module-level one-shot functions (`generate_image`,
`get_history`, …), and bare-noun response models (`ExecutionResult`,
`QueueInfo`, …). `workflows/` stays a docstring-only namespace, as in
`fabricatio-skill`.

## Architecture

| Layer      | Module / Class                              | Purpose                                              |
| Graph      | `Graph` (`models/graph.py`)                 | Typed graph initialised in Python, serialized to the ComfyUI wire format; internal only |
| Transport  | `ComfyUIHttpClient` / `ComfyUIClientBase`   | Async REST client; shared per-URL via `get_comfyui_client` |
| Capability | `UseComfyUI` (`capabilities/comfyui.py`)    | Mixin: high-level generate (queue → poll → download)  |
| API        | `api.py`                                    | One-shot functions that run on the shared pooled client |
| Actions    | `GenerateImage`                             | Pluggable step for Fabricatio `WorkFlow`              |

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
download_dir = "./outputs"
```

| Option | Type | Default | Description |
|---|---|---|---|
| `base_url` | `str` | `"http://127.0.0.1:8188"` | Base URL of the ComfyUI server (default localhost:8188). |
| `timeout` | `float` | `300.0` | Default timeout in seconds for API requests (default 5 min). |
| `checkpoint` | `str \| None` | `None` | Checkpoint applied to every generation; a per-call `checkpoint=` knob takes precedence. |
| `download_dir` | `str \| None` | `None` | Default directory for generated images; a per-call `download_dir=` takes precedence. |

Access at runtime: `from fabricatio_comfyui.config import comfyui_config`.

## Usage

### One-shot functions

The lowest-friction entry point — no Role, no client, no workflow:

```python
import asyncio
from fabricatio_comfyui import generate_image


async def main() -> None:
    path = await generate_image(
        "masterpiece, best quality, a mountain landscape",
        negative_prompt="worst quality, blurry",
        width=1024,
        height=768,
    )
    print(path)  # Path to the generated image, or None on failure


asyncio.run(main())
```

### Capability mixin (with a Role or Action)

Mix `UseComfyUI` into a Role to get the same typed-knob methods:

```python
from fabricatio import Role
from fabricatio_comfyui import UseComfyUI


class ImageRole(Role, UseComfyUI):
    """Role with ComfyUI image generation capability."""


# then: path = await role.generate_image("a mountain landscape")  # Path | None
```

### Action (in a WorkFlow)

Use `GenerateImage` as a composable step:

```python
from fabricatio import WorkFlow
from fabricatio_comfyui import GenerateImage

GenerateImageWorkflow = WorkFlow(
    name="ComfyUI Generate",
    steps=(
        GenerateImage(
            prompt="masterpiece, best quality",
            download_dir="./outputs",
        ),
    ),
)
```

### Standalone client (advanced)

The mixin and the one-shot functions share one pooled client per server
URL, obtained from the cached factory
`fabricatio_comfyui.http_client.get_comfyui_client` — never close the
client it returns.  When you need a *private* pool instead (tests,
alternate backends), build a scoped one with `async with`:

```python
import asyncio
from fabricatio_comfyui import ComfyUIHttpClient


async def main() -> None:
    async with ComfyUIHttpClient.create() as client:
        result = await client.generate("a mountain landscape", seed=42)
        if result.succeeded():
            await client.download_images(result, "./outputs")


asyncio.run(main())
```

## API Reference

### Capability methods (`UseComfyUI`)

| Method                        | Description                                                            |
|-------------------------------|------------------------------------------------------------------------|
| `generate_image(prompt, …)`   | Queue the bundled graph → poll → download → return the image path (`Path \| None`) |
| `get_history(prompt_id)`      | Retrieve execution history for a prompt                                |
| `get_queue_info()`            | Fetch current queue status                                             |
| `interrupt()`                 | Interrupt the currently running generation                             |

`generate_image` keyword parameters: `negative_prompt`, `width`, `height`,
`seed`, `steps`, `cfg`, `checkpoint`, `download_dir`, `timeout`;
`download_dir` falls back to the `[ext.comfyui] download_dir` config value.

On failure the methods above return `None` — a single prompt yields at most
one image file path.

The module-level functions in `fabricatio_comfyui.api` (`generate_image`,
`get_history`, `get_queue_info`, `interrupt`) share the exact same
keyword surface and hide the client lifecycle entirely.

### Client methods (`ComfyUIHttpClient` / `ComfyUIClientBase`)

| Method                            | Returns            | Description                              |
|-----------------------------------|--------------------|------------------------------------------|
| `generate(prompt, …)`             | `ExecutionResult`  | Queue the bundled graph and poll         |
| `get_queue_info()`                | `QueueInfo`        | Fetch current queue status               |
| `get_history(prompt_id)`          | `HistoryEntry \| None` | Retrieve execution history for a prompt |
| `wait_for_completion(prompt_id)`  | `ExecutionResult`  | Poll until execution finishes            |
| `get_image(filename, …)`          | `bytes`            | Download a single generated image        |
| `upload_image(image_path, …)`     | `UploadResponse`   | Upload an image                          |
| `interrupt()`                     | `None`             | Interrupt the running generation         |
| `download_images(result, dir)`    | `None`             | Download all output images concurrently  |
| `download_first_image(result, dir)` | `Path \| None`  | Download the first output image and return its local path |

### Actions

| Class          | Fields                                                                                                    | Description                        |
|----------------|-----------------------------------------------------------------------------------------------------------|------------------------------------|
| `GenerateImage` | `prompt`, `negative_prompt`, `width`, `height`, `seed`, `steps`, `cfg`, `checkpoint`, `download_dir`, `timeout` | Generate images from typed knobs |

### Models

All API responses are deserialized into frozen Pydantic models:

| Model            | Description                                              |
|------------------|----------------------------------------------------------|
| `PromptResponse` | Response from `POST /prompt` — contains `prompt_id`      |
| `ExecutionResult`| Final result — `outputs`, `all_images`, `succeeded`      |
| `OutputImage`    | Single image metadata — `filename`, `subfolder`, `type`  |
| `HistoryEntry`   | Execution history — `status`, per-node `outputs`         |
| `QueueInfo`      | Queue state — `queue_running`, `queue_pending`           |
| `UploadResponse` | Upload result — `name`, `subfolder`, `type`              |

## License

MIT — see the [LICENSE](https://github.com/Whth/fabricatio/blob/master/LICENSE) file.
