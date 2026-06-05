# `fabricatio-tool`

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-tool)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-tool)](https://pypi.org/project/fabricatio-tool)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-tool/week)](https://pepy.tech/projects/fabricatio-tool)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-tool)](https://pepy.tech/projects/fabricatio-tool)
[![Bindings: PyO3](https://img.shields.io/badge/bindings-pyo3-green)](https://github.com/PyO3/pyo3)
[![Build Tool: uv + maturin](https://img.shields.io/badge/built%20with-uv%20%2B%20maturin-orange)](https://github.com/astral-sh/uv)

Tool execution layer for [Fabricatio](https://github.com/Whth/fabricatio) — wraps Python callables as discoverable tools, lets LLMs generate orchestration code, and executes it with safety validation.

---

## Installation

```bash
pip install fabricatio[tool]
# or
uv pip install fabricatio[tool]
```

For all Fabricatio packages:

```bash
pip install fabricatio[full]
```

## Overview

`fabricatio-tool` enables Fabricatio agents to use arbitrary Python functions as **tools**. Tools are grouped into **toolboxes**, discovered by an LLM-driven selection process, composed into execution code (also LLM-generated), and run inside a `ToolExecutor` with import/call safety checks. Results are collected in a `ResultCollector` for downstream use.

The package also includes built-in filesystem tools, MCP (Model Context Protocol) client integration, and optional user-confirmation guards for destructive operations.

## Core concepts

| Concept | Description |
|---|---|
| `Tool` | A named, described callable with auto-extracted signature and briefing |
| `ToolBox` | A named collection of related `Tool` instances |
| `ToolExecutor` | Runs LLM-generated code that invokes tools; validates imports and calls |
| `ResultCollector` | Key-value container for tool execution results and errors |
| `Handle` / `HandleTask` | Mixin classes that wire tool discovery → code generation → execution |

## Key classes and functions

### `fabricatio_tool.models.tool`

- **`Tool(source, name, description)`** — wraps a callable with metadata. `invoke(*args, **kwargs)` calls through. `.signature` and `.briefing` are auto-generated.
- **`ToolBox(name, description)`** — collects tools. `add_tool(func)` appends a tool; `collect_tool()` works as a decorator. `get(name)` looks up a tool by name. `.briefing` produces an LLM-friendly description.

### `fabricatio_tool.models.collector`

- **`ResultCollector`** — `submit(key, val)`, `revoke(key)`, `take(key)` for typed retrieval, `error()` for retrieving execution errors.
- **`ApplicationError`** — captures exception type, message, traceback, and the generated source for retry.

### `fabricatio_tool.models.executor`

- **`ToolExecutor(candidates, data)`** — `execute(source)` runs tool-usage code asynchronously. `inject_tools(cxt)`, `inject_data(cxt)`, `inject_collector(cxt)` prepare the execution context. `from_recipe(recipe, toolboxes)` constructs an executor by selecting tools by name.

### `fabricatio_tool.capabilities`

- **`UseTool`** — LLM-driven selection: `choose_toolboxes(request)`, `choose_tools(request)`, `gather_tools(request)`, `gather_tools_fine_grind(request)`.
- **`Handle`** — `draft_tool_usage_code(request, tools, data)` generates Python code via LLM. `handle(request, data)` and `handle_fine_grind(request, data)` run the full pipeline.
- **`HandleTask`** — extends `Handle` with `handle_task(task, data)` for Fabricatio `Task` objects.

### `fabricatio_tool.config`

- **`ToolConfig`** — configuration model: `check_modules`, `check_imports`, `check_calls` (whitelist/blacklist), `mcp_servers`, `confirm_on_ops`, `logging_on_ops`.
- **`CheckConfigModel(targets, mode)`** — whitelist or blacklist mode for validation.
- **`tool_config`** — singleton instance loaded from Fabricatio config.

### `fabricatio_tool.fs`

Filesystem utilities callable as tools:

| Function | Description |
|---|---|
| `dump_text(path, text)` | Write text to a file |
| `copy_file(src, dst)` | Copy a file |
| `move_file(src, dst)` | Move/rename a file |
| `delete_file(path)` | Delete a file |
| `create_directory(path)` | Create a directory |
| `delete_directory(path)` | Recursively delete a directory |
| `absolute_path(path)` | Resolve to absolute POSIX path |
| `gather_files(directory, ext)` | Glob for files by extension |
| `safe_text_read(path)` | Read file as UTF-8 text |
| `safe_json_read(path)` | Read and parse JSON file |
| `treeview(path, max_depth)` | Render a directory tree (Rust) |

### `fabricatio_tool.mcp`

- **`get_global_mcp_manager(conf)`** — singleton MCP manager (Rust-backed).
- **`mcp_tool_to_function(client_id, tool_name)`** — converts an MCP tool to an async callable.
- **`mcp_to_toolbox(client_id)`** — converts all tools from an MCP client into a `ToolBox`.

### `fabricatio_tool.decorators`

- **`confirm_to_execute(func)`** — wraps a function with an interactive confirmation prompt via `questionary`.

### `fabricatio_tool.toolboxes`

- **`fs_toolbox`** — pre-built `ToolBox` containing all filesystem tools listed above.

## Usage example

```python
from fabricatio_tool.models.tool import Tool, ToolBox
from fabricatio_tool.models.executor import ToolExecutor

# Define a tool
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b

# Build a toolbox
box = ToolBox(name="math", description="Math operations")
box.add_tool(add, confirm=False, logging=True)

# Execute LLM-generated tool-usage code
executor = ToolExecutor(candidates=box.tools, data={})
source = """
async def execute(collector):
    result = await add(3, 4)
    collector.submit('sum', result)
"""
await executor.execute(source)
print(executor.collector.take('sum'))  # 7
```

### With filesystem toolbox

```python
from fabricatio_tool.toolboxes import fs_toolbox

# Use the built-in filesystem tools
executor = ToolExecutor(candidates=fs_toolbox.tools, data={})
source = """
async def execute(collector):
    import pathlib
    await dump_text(pathlib.Path('example.txt'), 'Hello, Fabricatio!')
    content = await safe_text_read(pathlib.Path('example.txt'))
    collector.submit('content', content)
"""
await executor.execute(source)
print(executor.collector.take('content'))  # Hello, Fabricatio!
```

### Using capability mixins

```python
from fabricatio_tool.capabilities.handle import Handle

class MyAgent(Handle):
    ...

agent = MyAgent()
result = await agent.handle(
    "Find all Python files and count their total lines",
    data={"dir": "src/"},
    model="default",
)
if result and not result.error():
    print(result.take("output"))
```

## Safety

`ToolExecutor` validates generated code against configurable whitelists or blacklists for modules, imports, and function calls. By default, only safe builtins (`str`, `int`, `float`, `bool`, `dict`, `set`, `list`, `pathlib.Path`, `print`, `len`) and `math` are permitted. Destructive tools can be gated behind `confirm_to_execute`, which prompts the user interactively.

## Dependencies

- `fabricatio-core` — core interfaces and utilities
- `pydantic>=2.11.7`
- `questionary>=2.1.0`

## License

MIT — see [LICENSE](../../LICENSE)
