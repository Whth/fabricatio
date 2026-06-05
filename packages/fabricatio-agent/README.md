# `fabricatio-agent`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-agent)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-agent)](https://pypi.org/project/fabricatio-agent/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-agent/week)](https://pepy.tech/projects/fabricatio-agent)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-agent)](https://pepy.tech/projects/fabricatio-agent)
[![Bindings: PyO3](https://img.shields.io/badge/bindings-pyo3-green)](https://github.com/PyO3/pyo3)
[![Build Tool: uv + maturin](https://img.shields.io/badge/built%20with-uv%20%2B%20maturin-orange)](https://github.com/astral-sh/uv)

AI agent framework that integrates thinking, memory, judgment, task dispatching, and team collaboration into a single composable `Agent` class. The agent digests requests, decomposes them into tasks, and executes them through a cooperative multi-role pipeline.

## Installation

```bash
pip install fabricatio[agent]
```

Or with full dependencies:

```bash
pip install fabricatio[full]
```

The package exposes a CLI entry point (`falcon`) when installed with the `cli` extra:

```bash
pip install fabricatio-agent[cli]
falcon code "write a fibonacci function in python"
```

## Key Components

### `Agent` (`fabricatio_agent.capabilities.agent`)

The central class composing these capabilities through multiple inheritance:

| Capability | Trait | Role |
|---|---|---|
| Checkpoint | `Checkpoint` | Save/restore execution state |
| Capable | `Capable` | Assess whether the agent can handle a request |
| CooperativeDigest | `CooperativeDigest` | Decompose requests into task lists with team-aware dispatch |
| Remember | `Remember` | Recall relevant memories to enrich context |
| Censor | `Censor` | Rule-based content filtering |
| EvidentlyJudge | `EvidentlyJudge` | Evidence-aware judgment and evaluation |
| DispatchTask | `DispatchTask` | Dispatch tasks to team members |
| DiffEdit | `DiffEdit` | Difference-based editing operations |
| Questioning | `Questioning` | Interactive question-asking |
| Thinking | `Thinking` | Sequential chain-of-thought reasoning |
| Handle | `Handle` | Tool execution and handling |

**`Agent.fulfill(request, sequential_thinking=False, check_capable=False, memory=False, top_k=100, boost_recent=True, **kwargs)`**

The main entry point. Orchestrates capability checking → memory recall → sequential thinking → request digestion into a task list → task execution. Returns `None` if the agent is not capable, otherwise returns the task execution results.

```python
from fabricatio_agent.capabilities.agent import Agent

class MyAgent(Agent):
    pass

agent = MyAgent()
result = await agent.fulfill(
    "Refactor the authentication module to use JWT",
    sequential_thinking=True,
    memory=True,
)
```

### `AgentConfig` (`fabricatio_agent.config`)

Dataclass controlling agent behavior, loaded from the Fabricatio configuration system:

| Field | Default | Description |
|---|---|---|
| `memory` | `False` | Enable memory recall globally |
| `sequential_thinking` | `False` | Enable sequential thinking globally |
| `check_capable` | `False` | Check capabilities before every request |
| `fulfill_prompt_template` | `"built-in/fulfill_prompt"` | Template used for request digestion |

Values set on `AgentConfig` act as defaults; the `fulfill()` method accepts per-call overrides.

### Actions (`fabricatio_agent.actions.code`)

Reusable `Action` subclasses that combine the `Agent` capability mixin:

- **`WriteCode`** — Generates code snippets from a prompt (with directory tree context), infers the coding language, and writes files to disk.
- **`Planning`** — Breaks complex tasks into subtasks via cooperative digestion, optionally preceded by sequential thinking.
- **`CleanUp`** — Removes unwanted files/directories using tool-based handling.
- **`ReviewCode`** — Saves a checkpoint of the current state for later review.
- **`MakeSpecification`** — Produces a specification document for a task.

### CLI (`fabricatio_agent.cli`)

A Typer application (`falcon`) that assembles a multi-role team and dispatches tasks:

**Roles** — each implements `Role` + `Cooperate` and subscribes to event patterns:

| Role | Handles | Workflow |
|---|---|---|
| `Developer` | `Coding`, `CleanUp`, `Plot`, `Synthesize` | WriteCode, CleanUp, chart/synthesis generation |
| `ProjectLeader` | `Orchestrate` | Planning (decomposes into subtasks) |
| `TestEngineer` | `Test` | WriteCode (generates test cases) |
| `DocumentationWriter` | `Documentation` | WriteCode (generates documentation) |

**`TaskType`** enum: `Coding`, `Orchestrate`, `CleanUp`, `Plot`, `Synthesize`, `Test`, `Documentation`.

```bash
falcon code "write a fibonacci function in python"
```

This command spins up a `Team` with all four roles and delegates a coding task through the orchestrator. Complex tasks are automatically decomposed into subtasks.

## Dependencies

- `fabricatio-core` — Core interfaces and utilities
- `fabricatio-digest` — Request digestion and task planning
- `fabricatio-memory` — Memory management and recall
- `fabricatio-improve` — Content improvement
- `fabricatio-rule` — Rule-based content processing
- `fabricatio-judge` — Judgment and evaluation
- `fabricatio-capabilities` — Base capability patterns
- `fabricatio-diff` — Difference editing operations
- `fabricatio-thinking` — Sequential thinking
- `fabricatio-question` — Interactive questioning
- `fabricatio-tool` — Tool handling and execution
- `fabricatio-team` — Team cooperation mechanisms
- `fabricatio-capable` — Capability assessment
- `fabricatio-checkpoint` — Execution checkpointing

## License

MIT — see [LICENSE](../../LICENSE)
