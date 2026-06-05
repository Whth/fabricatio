# `fabricatio-actions`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-actions)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-actions)](https://pypi.org/project/fabricatio-actions)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-actions/week)](https://pepy.tech/projects/fabricatio-actions)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-actions)](https://pepy.tech/projects/fabricatio-actions)
[![Build Tool: uv](https://img.shields.io/badge/built%20with-uv-orange)](https://github.com/astral-sh/uv)

Action primitives for the Fabricatio LLM agent framework — file I/O, output persistence, context manipulation, and template-based rendering.

---

## Installation

```bash
pip install fabricatio[actions]
# or
uv pip install fabricatio[actions]
```

For the full Fabricatio suite:

```bash
pip install fabricatio[full]
```

---

## Overview

`fabricatio-actions` provides reusable `Action` subclasses that serve as building blocks in Fabricatio workflow steps. Each action encapsulates a single operation — reading a file, persisting output, gathering context values — and plugs directly into the agent's event-driven pipeline.

Actions integrate with the LLM capability layer (`UseLLM`) where appropriate, automatically inferring paths and parameters from task context when not explicitly provided.

---

## Actions

### File System

| Class | Description |
|---|---|
| `ReadText` | Read a file's contents as UTF-8 text. Accepts `read_path` (str or Path); exposes result under `output_key` (default `"read_text"`). |
| `DumpText` | Write text to a file, creating parent directories as needed. Accepts `dump_path` (str or Path) and `text_key` naming the context key to write. |
| `SmartReadText` | Extends `ReadText` with LLM-assisted path resolution. If `read_path` is unset, infers it from the task briefing via `UseLLM`. |
| `SmartDumpText` | Extends `DumpText` with LLM-assisted path resolution. If `dump_path` is unset, infers it from the task briefing. |

### Output Management

| Class | Description |
|---|---|
| `DumpFinalizedOutput` | Serializes a `FinalizedDumpAble` object to disk. Path may be provided directly, or inferred via LLM from the task briefing. |
| `RenderedDump` | Renders a `FinalizedDumpAble` object through a named template (`template_name`) and writes the result to disk. Uses Fabricatio's built-in template manager. |
| `PersistentAll` | Iterates the execution context and persists every `PersistentAble` object into its own subdirectory under `persist_dir`. Supports single objects and `Iterable` collections. Set `override=True` to clear an existing directory first. |
| `RetrieveFromPersistent` | Loads a `PersistentAble` object from a file or directory at `load_path`. Returns a single object for a file, or a list of objects for a directory. |
| `RetrieveFromLatest` | Loads the most recent `PersistentAble` object from a directory at `load_path`. Requires `load_path` to be a directory. |

### Context Manipulation

| Class | Description |
|---|---|
| `GatherAsList` | Collects context values whose keys match a `gather_prefix` or `gather_suffix` into a list. Both fields are optional; at least one must be set. |
| `Forward` | Copies a value from one context key (`original`) to another (`output_key`), enabling value aliasing across workflow steps. |

---

## Models

| Class | Description |
|---|---|
| `FromMapping` | Abstract base for actions that can be instantiated from a `Mapping[str, V]`. Implement `from_mapping()` to return a list of action instances. |
| `FromSequence` | Abstract base for actions that can be instantiated from a `Sequence[V]`. Implement `from_sequence()` to return a list of action instances. |

`ReadText`, `DumpText`, `RetrieveFromLatest`, and `Forward` all implement `from_mapping()`. `Forward` additionally implements `from_sequence()`.

---

## Usage

### Reading and Writing Files

```python
from fabricatio_actions.actions import ReadText, DumpText

# Read a file
read = ReadText(read_path="input.txt", output_key="content")
content = await read._execute()

# Write text from context
dump = DumpText(dump_path="output.txt", text_key="content")
await dump._execute(content="sample text")
```

### Bulk Instantiation from Mappings

```python
from fabricatio_actions.actions import ReadText, DumpText, Forward

# Create multiple ReadText actions from a mapping
readers = ReadText.from_mapping({
    "config": "config.yaml",
    "prompt": "prompts/main.txt",
})

# Create Forward actions from a mapping or sequence
forwards = Forward.from_mapping({"raw_data": ["data", "payload"]})
chain = Forward.from_sequence(["step1", "step2"], original="input")
```

### LLM-Assisted Path Resolution

`SmartReadText` and `SmartDumpText` extend the basic file actions with LLM path inference:

```python
from fabricatio_actions.actions import SmartReadText

smart = SmartReadText(read_path=None)  # path inferred from task briefing
content = await smart._execute(task_input=some_task)
```

Works the same way for `DumpFinalizedOutput` and `RenderedDump` when no explicit path is given.

### Persisting and Retrieving Objects

```python
from fabricatio_actions.actions import PersistentAll, RetrieveFromLatest

# Persist all PersistentAble objects from context
persist = PersistentAll(persist_dir="checkpoints/run-42", override=True)
count = await persist._execute(obj_a=model_a, obj_b=model_b)
# -> persists model_a and model_b into checkpoints/run-42/

# Retrieve the latest version
retrieve = RetrieveFromLatest(
    retrieve_cls=MyModel,
    load_path="checkpoints/run-42/",
)
latest = await retrieve._execute()
```

### Template-Based Output

```python
from fabricatio_actions.actions import RenderedDump

dump = RenderedDump(template_name="report.md.jinja", dump_path="report.md")
path = await dump._execute(to_dump=my_finalized_data)
```

---

## Dependencies

- `fabricatio-core` — Core interfaces (`Action`, `Task`) and utilities
- `fabricatio-capabilities` — `FinalizedDumpAble`, `PersistentAble` interfaces
- `fabricatio-tool` — File system utilities (`dump_text`)

---

## License

MIT — see [LICENSE](LICENSE)
