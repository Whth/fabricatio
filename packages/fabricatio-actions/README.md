# `fabricatio-actions`

A Python library providing foundational actions for file system operations and output management in LLM applications.

## 📦 Installation

This package is part of the `fabricatio` monorepo and can be installed as an optional dependency:

```bash
pip install fabricatio[actions]
```

Or install all components:

```bash
pip install fabricatio[full]
```

## 🔍 Overview

Provides essential tools for:

- File system operations (read/write, path handling)
- Output formatting and display
- Basic task execution building blocks

Designed to work seamlessly with Fabricatio's agent framework and other modules like `fabricatio-core`,
`fabricatio-capabilities`, and `fabricatio-improve`.

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

MIT – see [LICENSE](LICENSE)

GitHub: [github.com/Whth/fabricatio](https://github.com/Whth/fabricatio)