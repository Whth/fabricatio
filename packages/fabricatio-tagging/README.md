# `fabricatio-tagging`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-tagging)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-tagging)](https://pypi.org/project/fabricatio-tagging/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-tagging/week)](https://pepy.tech/projects/fabricatio-tagging)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-tagging)](https://pepy.tech/projects/fabricatio-tagging)
[![Build Tool: uv](https://img.shields.io/badge/built%20with-uv-orange)](https://github.com/astral-sh/uv)

LLM-powered tag generation for text content. Part of the Fabricatio agent framework.

## Installation

This package is part of the `fabricatio` monorepo and can be installed as an optional dependency using either pip or uv:

```bash
pip install fabricatio[tagging]
# or
uv pip install fabricatio[tagging]
```

For a full installation that includes this package and all other components of `fabricatio`:

```bash
pip install fabricatio[full]
# or
uv pip install fabricatio[full]
```

## Overview

`fabricatio-tagging` provides a `Tagging` mixin class that uses LLMs to generate descriptive tags from text. It accepts a single string or a list of strings and returns corresponding tag lists, driven by a configurable Handlebars template.

The package extends `Propose` from `fabricatio-core`, so any role class that mixes in `Tagging` gains the `tagging()` method alongside existing proposal capabilities.

## Key Classes

### `Tagging` (`fabricatio_tagging.capabilities.tagging`)

A mixin extending `Propose` that adds the `tagging()` async method.

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `tagging` | `(text: str, requirement: str = "", k: int = 0, **kwargs) -> List[str] \| None` | Tag list or `None` | Generate tags for a single string. Returns `None` if generation fails. |
| `tagging` | `(text: List[str], requirement: str = "", k: int = 0, **kwargs) -> List[List[str]]` | List of tag lists | Generate tags for multiple strings. Each inner list corresponds to one input text. |

Parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `text` | `str \| List[str]` | _(required)_ | Input text(s) to tag |
| `requirement` | `str` | `""` | Additional constraints for tag generation |
| `k` | `int` | `0` | Maximum number of tags per text (`0` = no limit) |
| `**kwargs` | `Unpack[LLMKwargs]` | — | Generation parameters passed to the underlying LLM |

Raises `TypeError` if `text` is neither a `str` nor a `List[str]`.

### `TaggingConfig` (`fabricatio_tagging.config`)

Frozen dataclass controlling which Handlebars template is used for tag generation.

| Field | Default | Description |
|-------|---------|-------------|
| `tagging_template` | `"built-in/tagging"` | Template name resolved by `TEMPLATE_MANAGER` |

Access via the singleton:

```python
from fabricatio_tagging.config import tagging_config
print(tagging_config.tagging_template)
```

## Usage

Mixin `Tagging` into a role class and call `tagging()`:

```python
import asyncio
from fabricatio_core.capabilities.propose import Propose
from fabricatio_tagging.capabilities.tagging import Tagging


class MyRole(Propose, Tagging):
    """A role that can generate tags."""
    pass


async def main():
    role = MyRole()

    # Tag a single string
    tags = await role.tagging("Python is a high-level programming language.")
    print(tags)  # e.g. ["python", "programming", "language"]

    # Tag with requirements and a cap
    tags = await role.tagging(
        "Rust is a systems language.",
        requirement="use lowercase technical tags only",
        k=3,
    )
    print(tags)  # e.g. ["rust", "systems", "memory-safety"]

    # Tag multiple strings in a batch
    batch_tags = await role.tagging([
        "Django is a Python web framework.",
        "Tokio is an async runtime for Rust.",
    ])
    print(batch_tags)  # e.g. [["python", "web", "django"], ["rust", "async", "tokio"]]


asyncio.run(main())
```

The `requirement` parameter provides natural-language guidance to the LLM (e.g. `"use single words only"`, `"tag by topic and difficulty level"`). The `k` parameter limits the number of tags returned per text.

## Configuration

The default template `"built-in/tagging"` is registered by `fabricatio-core`. Override it by loading a custom template and updating the config:

```python
from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_tagging.config import tagging_config

# Register a custom Handlebars template
TEMPLATE_MANAGER.register_template("my-tags", "Generate {{k}} tags for: {{text}}. {{requirement}}")

# Point config at it
object.__setattr__(tagging_config, "tagging_template", "my-tags")
```

## Dependencies

- `fabricatio-core` — Core interfaces, `Propose` capability, template manager, and configuration system.

No additional dependencies.

## License

MIT – see [LICENSE](../../LICENSE)
