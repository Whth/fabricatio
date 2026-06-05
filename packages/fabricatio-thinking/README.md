# `fabricatio-thinking`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-thinking)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-thinking)](https://pypi.org/project/fabricatio-thinking/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-thinking/week)](https://pepy.tech/projects/fabricatio-thinking)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-thinking)](https://pepy.tech/projects/fabricatio-thinking)
[![Bindings: PyO3](https://img.shields.io/badge/bindings-pyo3-green)](https://github.com/PyO3/pyo3)
[![Build Tool: uv + maturin](https://img.shields.io/badge/built%20with-uv%20%2B%20maturin-orange)](https://github.com/astral-sh/uv)

Sequential Chain-of-Thought reasoning for `fabricatio` agents, backed by a Rust-implemented version control system for thought management.

---

## Installation

```bash
pip install fabricatio[thinking]
# or
uv pip install fabricatio[thinking]
```

For a full monorepo installation:

```bash
pip install fabricatio[full]
```

## Overview

`fabricatio-thinking` provides structured, multi-step reasoning through a
version-controlled thought process. Agents iterate through a chain of
thoughts, with built-in support for revising past steps, branching into
alternative reasoning paths, and managing the entire thought history via a
lightweight VCS written in Rust.

## Components

### Capabilities

| Name | Description |
|------|-------------|
| `Thinking` | ABC mixin (extends `Propose`) that adds the `thinking()` coroutine to any role. |

### Models

| Name | Description |
|------|-------------|
| `Thought` | Pydantic model for a single reasoning step. Fields: `thought` (content), `end` (stop flag), `serial` (step number), `estimated` (expected total steps), `revision`, `revises_thought`, `checkout`, `branch`. Extends `fabricatio_core.models.generic.SketchedAble`. |

### Rust Bindings

| Name | Description |
|------|-------------|
| `ThoughtVCS` | In-memory version control for thought chains. Each branch is an ordered list of commits. |

### Configuration

| Name | Description |
|------|-------------|
| `ThinkingConfig` | Frozen dataclass loaded via `fabricatio_core.CONFIG.load("thinking", …)`. |

## Usage

```python
from fabricatio_thinking.capabilities.thinking import Thinking
from fabricatio_thinking.rust import ThoughtVCS
from fabricatio_core.capabilities.propose import Propose

class MyAgent(Propose, Thinking):
    """An agent that can reason step-by-step."""

async def reason():
    agent = MyAgent()
    vcs = ThoughtVCS()

    # Run a thinking process for up to 10 steps
    result_vcs = await agent.thinking(
        question="Explain the difference between TCP and UDP.",
        vcs=vcs,
        max_steps=10,
    )

    # Export the final chain as a list of strings
    chain = result_vcs.export_branch()
    for commit in chain:
        print(commit)

    # Or as a single formatted string
    print(result_vcs.export_branch_string())
```

### How `thinking()` works

1. The LLM proposes a `Thought` for the current step.
2. If the thought requests a **revision** (`revision=True` + `revises_thought`), the VCS updates that prior commit.
3. If the thought requests a **checkout** (`checkout` + `branch`), the VCS truncates the branch at the given step.
4. Otherwise, the thought is **committed** to the current branch.
5. The loop repeats until `end=True` or `max_steps` is reached.

## ThoughtVCS API

| Method | Description |
|--------|-------------|
| `commit(content, serial, estimated, branch=None)` | Append a thought to a branch, creating the branch if it does not exist. |
| `revise(content, serial, branch=None)` | Replace the content of an existing commit. |
| `checkout(branch, serial)` | Truncate a branch to a specific commit (used for branching). |
| `export_branch(branch=None)` | Return all commits as a `list[str]`. |
| `export_branch_string(branch=None)` | Return all commits as a single formatted string. |

## Dependencies

- `fabricatio-core` — core interfaces (`Propose`, `SketchedAble`, `CONFIG`, loggers)

## License

MIT — see [LICENSE](../../LICENSE)
