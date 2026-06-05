# `fabricatio-digest`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-digest)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-digest)](https://pypi.org/project/fabricatio-digest/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-digest/week)](https://pepy.tech/projects/fabricatio-digest)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-digest)](https://pepy.tech/projects/fabricatio-digest)
[![Build Tool: uv](https://img.shields.io/badge/built%20with-uv-orange)](https://github.com/astral-sh/uv)

Converts a natural-language requirement into a validated, executable `TaskList` with role awareness and dependency sequencing.

---

## Installation

```bash
pip install fabricatio[digest]
```

## Overview

`fabricatio-digest` takes a raw requirement string together with a set of registered roles and uses an LLM-backed proposal pipeline to generate a structured `TaskList`. The resulting task list is executable — each task carries the context and description injected during generation, and hook callbacks can be attached for pre/post-execution behavior.

## Key Classes

### `Digest` (mixin capability)

Extends `Propose`. Inherit this to add requirement-to-tasklist generation to a role.

```python
from fabricatio_digest.capabilities.digest import Digest

class PlannerRole(SomeBaseRole, Digest):
    """A role that can break down requirements into task lists."""
    pass

task_list = await planner.digest(
    requirement="Summarize all PRs from the last week and post to Slack.",
    receptions={RoleName("reviewer"), RoleName("notifier")},
)
```

| Method | Description |
|--------|-------------|
| `digest(requirement, receptions, **kwargs)` | Renders a template with the requirement and role metadata, then calls `propose(TaskList, ...)`. Returns `Optional[TaskList]`. |

### `TaskList`

Pydantic model representing a sequence of tasks that aim to satisfy an `ultimate_target`.

| Field / Method | Description |
|----------------|-------------|
| `ultimate_target: str` | The overarching goal of the task list. |
| `tasks: List[Task]` | Ordered list of `Task` objects from `fabricatio-core`. |
| `parallel: bool` | If `True`, tasks are executed concurrently. |
| `add_before_exec_hook(hook)` | Register a callback to run before each task. |
| `add_after_exec_hook(hook)` | Register a callback to run after each task. |
| `inject_context(**kwargs)` | Merge keyword arguments into every task's initial context. |
| `inject_description(desc: str)` | Append extra text to every task's description. |
| `execute(parallel=None)` | Run the task sequence, respecting hooks and the parallel flag. |
| `explain()` | Render a human-readable explanation via template. |

### `DigestConfig`

Dataclass loaded from `fabricatio-core` configuration under the `digest` namespace.

| Field | Default | Description |
|-------|---------|-------------|
| `digest_template` | `"built-in/digest"` | Template used to build the proposal prompt. |
| `task_list_explain_template` | `"built-in/task_list_explain"` | Template used by `TaskList.explain()`. |

Access the global instance:

```python
from fabricatio_digest.config import digest_config
```

## Dependencies

- `fabricatio-core` — core interfaces, template manager, and `Propose`/`Task` base classes.

## License

MIT — see [LICENSE](../../LICENSE)
