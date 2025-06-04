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

### File System Operations
The file system operations in this library offer robust functionality for reading and writing files, as well as handling file paths. For example, the `ReadText` class can be used to read text files efficiently. It takes care of encoding issues and provides a simple interface for accessing the file content.

### Output Formatting and Display
Output formatting and display tools ensure that the results of operations are presented in a clear and organized manner. This includes formatting text, numbers, and other data types in a way that is easy to read and understand.

### Basic Task Execution Building Blocks
These building blocks are the foundation for creating complex tasks in LLM applications. They allow for the execution of tasks in a sequential or parallel manner, depending on the requirements of the application.

- File system operations (read/write, path handling)
- Output formatting and display
- Basic task execution building blocks

Designed to work seamlessly with Fabricatio's agent framework and other modules like `fabricatio-core`,
`fabricatio-capabilities`, and `fabricatio-improve`.

## 🧩 Usage Example

```python
# This example demonstrates how to use the ReadText class to read a file.
# First, we import the necessary classes and modules.
# The ReadText class is used to read text files.
# Role, Event, Task, and WorkFlow are part of the Fabricatio agent framework.
# asyncio is used for asynchronous programming.
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
### actions/
This directory contains the implementations of various actions.

#### fs.py
The `fs.py` file provides functions and classes for file system operations. It includes methods for reading and writing files, as well as handling file paths. For example, it may have a function to check if a file exists or to create a new directory.

#### output.py
The `output.py` file is responsible for output formatting and display. It contains functions to format text, numbers, and other data types in a way that is easy to read and understand.

### models/
This directory contains the data models used in the library.

#### generic.py
The `generic.py` file defines shared type definitions. These definitions are used across different parts of the library to ensure consistency in data handling.
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