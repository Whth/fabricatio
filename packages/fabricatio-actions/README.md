# `fabricatio-actions`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-actions)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-actions)](https://pypi.org/project/fabricatio-actions/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-actions/week)](https://pepy.tech/projects/fabricatio-actions)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-actions)](https://pepy.tech/projects/fabricatio-actions)
[![Build Tool: uv](https://img.shields.io/badge/built%20with-uv-orange)](https://github.com/astral-sh/uv)

A Python library providing foundational actions for file system operations and output management in LLM applications.

---

## 📦 Installation

This package is part of the `fabricatio` monorepo and can be installed as an optional dependency using either pip or uv:

```bash
pip install fabricatio[actions]
# or
uv pip install fabricatio[actions]
```

For a full installation that includes this package and all other components of `fabricatio`:

```bash
pip install fabricatio[full]
# or
uv pip install fabricatio[full]
```

## 🔍 Overview

Provides foundational actions for file system operations and output management in LLM applications. The package offers
robust functionality for reading and writing files, handling file paths, and formatting output for clear presentation in
AI-driven workflows.

## 🧩 Key Features

- **File System Operations**: Robust functionality for reading and writing files with encoding handling
- **Output Formatting**: Tools for presenting results in clear and organized manner
- **Path Handling**: Efficient file path management and validation
- **Task Execution Building Blocks**: Foundation components for complex task workflows
- **Agent Integration**: Seamless integration with Fabricatio agent framework
- **Asynchronous Support**: Built-in async support for non-blocking operations

## 🧩 Usage Example

```python
from fabricatio.actions import ReadText
from fabricatio import Role, Event, Task, WorkFlow
import asyncio

(Role(name="file_reader", description="file reader role")
 .register_workflow(Event.quick_instantiate("read_text"), WorkFlow(steps=(ReadText().to_task_output(),))
                    ))

async def main():
    ret: str = await Task(name="read_file", goals=["read file"], description="read file").update_init_context(
        read_path="path/to/file"
    ).delegate("read_text")
    print(ret)

asyncio.run(main())
```

## 📁 Structure

```
fabricatio-actions/
├── actions/          - Action implementations
│   ├── fs.py         - File system operations
│   └── output.py     - Output formatting and display
├── models/           - Data models
│   └── generic.py    - Shared type definitions
└── __init__.py       - Package entry point
```

## 🔗 Dependencies

Core dependencies:

- `fabricatio-core` - Core interfaces and utilities
- `fabricatio-capabilities` - Base capability patterns

## 📄 License

MIT – see [LICENSE](../../LICENSE)

