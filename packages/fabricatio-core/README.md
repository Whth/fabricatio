# `fabricatio-core`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-core)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-core)](https://pypi.org/project/fabricatio-core/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-core/week)](https://pepy.tech/projects/fabricatio-core)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-core)](https://pepy.tech/projects/fabricatio-core)
[![Build Tool: uv](https://img.shields.io/badge/built%20with-uv-orange)](https://github.com/astral-sh/uv)

Foundational Python library for building LLM-driven applications using an event-based agent architecture. Built on a
hybrid Rust/Python foundation for performance-critical operations.

Requires Python 3.12+.

## Installation

```bash
pip install fabricatio
# or
uv pip install fabricatio
```

For all optional extras:

```bash
pip install fabricatio[full]
```

## Key Components

### Event System (`Event`, `EventEmitter`)

Segmented event type with task-status lifecycle methods (`push_running`, `push_finished`, etc.) and glob-wildcard
(`*`) matching. The global `EventEmitter` dispatches events asynchronously with `on`/`off`/`emit`.

```python
from fabricatio_core.emitter import EMITTER
from fabricatio_core.rust import Event

EMITTER.on("task::*::finished", my_handler)
```

### LLM Routing (`Router`, `RouterUsage`)

Multi-provider router for completion, embedding, and reranking. `RouterUsage` provides structured LLM interaction
patterns — ask, list strings, code generation, judging, choosing — with configurable validation and fallback defaults.

```python
from fabricatio_core.rust import ROUTER, router_usage

response = await ROUTER.completion(send_to="default", message="Hello")
result = await router_usage.choosing("Pick two items", valid_names=["a", "b", "c"], k=2)
```

### Task Model (`Task`)

Pydantic-based task with lifecycle status management (`Pending`, `Running`, `Finished`, `Failed`, `Cancelled`),
dependency tracking, structured proposal generation from prompts, and automatic event emission on state transitions.

```python
task = Task(name="data_ingestion", description="Ingest raw data")
task.start()
# ... execute ...
task.finish(output={"rows": 1042})
```

### Workflow Engine (`Action`, `WorkFlow`)

Abstract action pipeline with shared context propagation. `WorkFlow` orchestrates sequences of `Action` instances,
managing input/output keys, error handling, and task lifecycle.

```python
class ParseData(Action):
    async def _execute(self, **cxt):
        return parse(cxt["task_input"])

wf = WorkFlow(actions=[ParseData().to_task_output()], name="parse_pipeline")
await wf.execute(task)
```

### Role Framework (`Role`)

Agent roles map event patterns to workflows. Global registry supports `register_role` / `get_registered_role`.
Roles dispatch workflows automatically when matching events are emitted.

```python
from fabricatio_core.models.role import Role, register_role

analyst = Role(name="analyst", description="Data analysis agent")
analyst.deploy_on("data::ingested", parse_wf)
register_role(analyst)
```

### Template Rendering (`TemplateManager`)

Handlebars-based template engine. Load templates from directories, render with structured data.

```python
from fabricatio_core.rust import TEMPLATE_MANAGER

TEMPLATE_MANAGER.add_store("./templates").discover_templates()
output = TEMPLATE_MANAGER.render_template("greeting", {"name": "World"})
```

### Capability Mixins (`UseLLM`, `UseEmbedding`, `UseReranker`, `Propose`)

Inheritable classes that add LLM querying, embedding generation, reranking, and structured proposal capabilities to
any model. All integrate with the `Router` for provider dispatch.

```python
class MyAgent(UseLLM, UseEmbedding, Propose, WithBriefing):
    pass

agent = MyAgent(name="helper")
answer = await agent.aask(question="What is 2+2?")
obj = await agent.propose(MyModel, prompt="Create a config object")
```

### Text Parsing & Language Utilities (Rust)

Fast Rust-backed functions for text processing:

- `split_sentence_bounds` / `split_word_bounds` — Unicode-aware text splitting
- `split_into_chunks` — chunk text with configurable overlap
- `tokens_of` / `word_count` — token and word counting
- `blake3_hash` — BLAKE3 content hashing
- `detect_language` — language detection
- `is_english`, `is_chinese`, `is_japanese`, etc. — language checks
- `is_likely_text` — file content type detection
- `CodeSnippetParser`, `CodeBlockParser`, `GenericBlockParser`, `JsonParser` — structured block extraction from LLM outputs

### Base Model Hierarchy (`models.generic`)

Pydantic-based abstract base classes for consistent model design: `Named`, `Described`, `WithBriefing`,
`WithDependency`, `ScopedConfig` (with hierarchical fallback), `ProposedAble`, `InstantiateFromString`, `Display`,
and more.

### Decorators

- `cfg_on` / `cfg_on_async` — feature-gated function execution
- `depend_on_external_cmd` — check external binary availability
- `logging_execution_info` / `logging_exec_time` — execution logging
- `once` — ensure single invocation

### Configuration (`Config`)

Structured configuration with sub-sections for LLM, embedding, reranking, emitter, routing, templates, debug, and
deployment settings. Accessible via `fabricatio_core.rust.CONFIG`.

## Package Structure

```
fabricatio-core/
├── python/fabricatio_core/
│   ├── capabilities/      - LLM, embedding, reranker, and proposal mixins
│   ├── models/            - Action, Role, Task, generic base models, kwargs types
│   ├── rust/              - PyO3 Rust extension (autogenerated stubs)
│   ├── decorators.py      - cfg_on, once, logging_exec_time, etc.
│   ├── emitter.py         - EventEmitter with wildcard pattern matching
│   ├── journal.py         - Logger bridge to Rust logger
│   ├── utils.py           - ok, cfg, override_kwargs, first_available, etc.
│   └── __init__.py        - Public API surface
├── src/                   - Rust sources (parser, templates, event, language, etc.)
└── pyproject.toml
```

## License

MIT — see [LICENSE](../../LICENSE)
