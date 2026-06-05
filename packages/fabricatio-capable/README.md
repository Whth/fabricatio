# `fabricatio-capable`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-capable)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-capable)](https://pypi.org/project/fabricatio-capable/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-capable/week)](https://pepy.tech/projects/fabricatio-capable)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-capable)](https://pepy.tech/projects/fabricatio-capable)
[![Build Tool: uv](https://img.shields.io/badge/built%20with-uv-orange)](https://github.com/astral-sh/uv)

Capability assessment mixin for Fabricatio agents — determines whether a request can be fulfilled given available tools and context.

---

## Installation

```bash
pip install fabricatio[capable]
# or
uv pip install fabricatio[capable]
```

For the full Fabricatio suite:

```bash
pip install fabricatio[full]
```

---

## Overview

`fabricatio-capable` provides the `Capable` mixin class, which equips an agent with the ability to assess whether a given task is within its capabilities. It answers questions like: "given my current toolboxes and context, can I handle this request?"

The mixin composes three capabilities into one method:

- **`WithBriefing`** — supplies agent context as a structured briefing.
- **`EvidentlyJudge`** — delegates to the evidence-based judgment engine from `fabricatio-judge`.
- **`UseTool`** — provides access to the agent's `ToolBox` set for tool-cognizant evaluation.

The `capable()` method renders a configurable Jinja2 template with the briefing, request text, and toolbox metadata, then passes it through `evidently_judge` to produce a `JudgeMent` — a binary verdict backed by affirmative and denying evidence.

---

## Key Types

| Name | Location | Description |
|---|---|---|
| `Capable` | `fabricatio_capable.capabilities.capable` | ABC mixin combining briefing, judgment, and tool-awareness. Exposes the `capable()` async method. |
| `CapableConfig` | `fabricatio_capable.config` | Frozen dataclass holding `capable_template` (default `"built-in/capable"`). Loaded via `fabricatio_core.CONFIG`. |

---

## Usage

### Single Request

```python
from fabricatio_capable.capabilities.capable import Capable
from fabricatio_judge.models.judgement import JudgeMent
from fabricatio_tool.models.tool import ToolBox

class MyAgent(Capable):
    # Capable is an ABC; provide your concrete agent logic here.
    ...

agent = MyAgent()
toolboxes = {ToolBox(name="file_tools"), ToolBox(name="web_tools")}

result: JudgeMent | None = await agent.capable(
    "Read the latest commit and summarize changes",
    toolboxes=toolboxes,
)

if result and result.final_judgement:
    print("Capable — proceeding.")
else:
    print("Not capable. Evidence:", result.evidences if result else "N/A")
```

### Batch Assessment

```python
requests = [
    "Fetch weather data for Tokyo",
    "Train a LoRA on 100GB of images",
]
results = await agent.capable(requests, toolboxes=toolboxes)

for req, judgement in zip(requests, results):
    verdict = judgement.final_judgement if judgement else "undetermined"
    print(f"{req}: {verdict}")
```

### Configuration

Override the default template via configuration:

```python
from fabricatio_capable.config import capable_config
# capable_config.capable_template is "built-in/capable" by default
# Register a custom template under a different name and set it:
# capable_config = CapableConfig(capable_template="my_custom_capable")
```

---

## Dependencies

- `fabricatio-core` — Core interfaces, briefing model, template manager
- `fabricatio-tool` — `UseTool` capability and `ToolBox` model
- `fabricatio-judge` — `EvidentlyJudge` and `JudgeMent`

---

## License

MIT — see [LICENSE](LICENSE)
