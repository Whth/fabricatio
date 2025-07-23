<p align="center">   
<picture>
        <img src="./assets/band.png" width="80%" alt="Fabricatio Logo" loading="lazy">
</picture>
</p>



<p align="center">
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License">
  </a>
  <a href="https://pypi.org/project/fabricatio/">
    <img src="https://img.shields.io/pypi/pyversions/fabricatio" alt="Python Versions">
  </a>
  <a href="https://pypi.org/project/fabricatio/">
    <img src="https://img.shields.io/pypi/v/fabricatio" alt="PyPI Version">
  </a>
  <a href="https://deepwiki.com/Whth/fabricatio">
    <img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki">
  </a>
  <a href="https://pepy.tech/projects/fabricatio">
    <img src="https://static.pepy.tech/badge/fabricatio/week" alt="PyPI Downloads (Week)">
  </a>
  <a href="https://pepy.tech/projects/fabricatio">
    <img src="https://static.pepy.tech/badge/fabricatio" alt="PyPI Downloads">
  </a>
  <a href="https://github.com/PyO3/pyo3">
    <img src="https://img.shields.io/badge/bindings-pyo3-green" alt="Bindings: PyO3">
  </a>
  <a href="https://github.com/BerriAI/litellm">
    <img src="https://img.shields.io/badge/Powered%20by-LiteLLM-blue" alt="Powered by LiteLLM">
  </a>
  <a href="https://github.com/astral-sh/uv">
    <img src="https://img.shields.io/badge/built%20with-uv%20%2B%20maturin-orange" alt="Build Tool: uv + maturin">
  </a>

</p>


<p align="center">


  <a href="https://github.com/Whth/fabricatio/actions/workflows/build-package.yaml">
    <img src="https://github.com/Whth/fabricatio/actions/workflows/build-package.yaml/badge.svg" alt="Build Package">
  </a>
  <a href="https://github.com/Whth/fabricatio/actions/workflows/ruff.yaml">
    <img src="https://github.com/Whth/fabricatio/actions/workflows/ruff.yaml/badge.svg" alt="Ruff Lint">
  </a>
  <a href="https://github.com/Whth/fabricatio/actions/workflows/tests.yaml">
    <img src="https://github.com/Whth/fabricatio/actions/workflows/tests.yaml/badge.svg" alt="Tests">
  </a>
  <a href="https://coveralls.io/github/Whth/fabricatio?branch=master">
    <img src="https://coveralls.io/repos/github/Whth/fabricatio/badge.svg?branch=master" alt="Coverage Status">
  </a>
  <a href="https://fabricatio.readthedocs.io/en/latest/?badge=fabricatio">
    <img src="https://readthedocs.org/projects/fabricatio/badge/?version=latest" alt="Documentation Status">
  </a>
  <a href="https://github.com/Whth/fabricatio/issues">
    <img src="https://img.shields.io/github/issues/Whth/fabricatio" alt="GitHub Issues">
  </a>
  <a href="https://github.com/Whth/fabricatio/pulls">
    <img src="https://img.shields.io/github/issues-pr/Whth/fabricatio" alt="GitHub Pull Requests">
  </a>
  <a href="https://github.com/Whth/fabricatio/stargazers">
    <img src="https://img.shields.io/github/stars/Whth/fabricatio" alt="GitHub Stars">
  </a>
</p>




---

## Overview

Fabricatio is a streamlined Python library for building LLM applications using an event-based agent structure. It
leverages Rust for performance-critical tasks, Handlebars for templating, and PyO3 for Python bindings.

## Features

- **Event-Driven Architecture**: Robust task management through an EventEmitter pattern.
- **LLM Integration & Templating**: Seamlessly interact with large language models and dynamic content generation.
- **Async & Extensible**: Fully asynchronous execution with easy extension via custom actions and workflows.

## Installation

```bash
# install fabricatio with full capabilities.
pip install fabricatio[full]

# or with uv

uv add fabricatio[full]


# install fabricatio with only rag and rule capabilities.
pip install fabricatio[rag,rule]

# or with uv

uv add fabricatio[rag,rule]

```


## Usage

### Basic Example

```python
"""Example of a simple hello world program using fabricatio."""

from typing import Any

# Import necessary classes from the namespace package.
from fabricatio import Action, Event, Role, Task, WorkFlow, logger

# Create an action.
class Hello(Action):
    """Action that says hello."""
    
    output_key: str = "task_output"

    async def _execute(self, **_) -> Any:
        ret = "Hello fabricatio!"
        logger.info("executing talk action")
        return ret


# Create the role and register the workflow.
(Role()
 .register_workflow(Event.quick_instantiate("talk"), WorkFlow(name="talk", steps=(Hello,)))
 .dispatch())


# Make a task and delegate it to the workflow registered above.
assert Task(name="say hello").delegate_blocking("talk") == "Hello fabricatio!"

```

### Examples

For various usage scenarios, refer to the following examples:

- Simple Chat
- Retrieval-Augmented Generation (RAG)
- Article Extraction
- Propose Task
- Code Review
- Write Outline

_(For full example details, see [Examples](./examples))_

## Configuration

Fabricatio supports flexible configuration through multiple sources, with the following priority order:
`Call Arguments` > `./.env` > `Environment Variables` > `./fabricatio.toml` > `./pyproject.toml` > `<ROMANING>/fabricatio/fabricatio.toml` > `Builtin Defaults`.

Below is a unified view of the same configuration expressed in different formats:

### Environment variables or dotenv file
```dotenv
FABRICATIO_LLM__API_ENDPOINT=https://api.openai.com
FABRICATIO_LLM__API_KEY=your_openai_api_key
FABRICATIO_LLM__TIMEOUT=300
FABRICATIO_LLM__MAX_RETRIES=3
FABRICATIO_LLM__MODEL=openai/gpt-3.5-turbo
FABRICATIO_LLM__TEMPERATURE=1.0
FABRICATIO_LLM__TOP_P=0.35
FABRICATIO_LLM__GENERATION_COUNT=1
FABRICATIO_LLM__STREAM=false
FABRICATIO_LLM__MAX_TOKENS=8192
FABRICATIO_DEBUG__LOG_LEVEL=INFO
```

### `fabricatio.toml` file
```toml
[llm]
api_endpoint = "https://api.openai.com"
api_key = "your_openai_api_key"
timeout = 300
max_retries = 3
model = "openai/gpt-3.5-turbo"
temperature = 1.0
top_p = 0.35
generation_count = 1
stream = false
max_tokens = 8192

[debug]
log_level = "INFO"
```

### `pyproject.toml` file
```toml
[tool.fabricatio.llm]
api_endpoint = "https://api.openai.com"
api_key = "your_openai_api_key"
timeout = 300
max_retries = 3
model = "openai/gpt-3.5-turbo"
temperature = 1.0
top_p = 0.35
generation_count = 1
stream = false
max_tokens = 8192

[tool.fabricatio.debug]
log_level = "INFO"
```

## Contributing

We welcome contributions from everyone! Before contributing, please read our [Contributing Guide](CONTRIBUTING.md) and [Code of Conduct](CODE_OF_CONDUCT.md).

## License

Fabricatio is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Acknowledgments

Special thanks to the contributors and maintainers of:

- [PyO3](https://github.com/PyO3/pyo3)
- [Maturin](https://github.com/PyO3/maturin)
- [Handlebars.rs](https://github.com/sunng87/handlebars-rust)
- [LiteLLM](https://github.com/BerriAI/litellm)
