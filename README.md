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

 <a href="https://fabricatio.readthedocs.io/en/latest/?badge=fabricatio">
    <img src="https://readthedocs.org/projects/fabricatio/badge/?version=latest" alt="Documentation Status">
  </a>
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

### Using UV (Recommended)

```bash
# Install uv if not already installed
pip install uv

# Clone the repository
git clone https://github.com/Whth/fabricatio.git
cd fabricatio

# Install the package in development mode with uvx
uvx --with-editable . maturin develop --uv -r

# Or, with make
make dev
```

### Building Distribution

```bash
# Build distribution packages
make bdist
```

## Usage

### Basic Example

```python
"""Example of a simple hello world program using fabricatio."""

from typing import Any

from fabricatio import Action, Event, Role, Task, WorkFlow, logger


class Hello(Action):
    """Action that says hello."""

    output_key: str = "task_output"

    async def _execute(self, **_) -> Any:
        ret = "Hello fabricatio!"
        logger.info("executing talk action")
        return ret

    """Main function."""


(Role()
 .register_workflow(Event.quick_instantiate("talk"), WorkFlow(name="talk", steps=(Hello,)))
 .dispatch())

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

_(For full example details, please check our detailed documentation, see [Examples](./examples))_

## Configuration

The configuration for Fabricatio is managed via environment variables or TOML files. For example:

```toml
[llm]
api_endpoint = "https://api.openai.com"
api_key = "your_openai_api_key"
timeout = 300
max_retries = 3
model = "gpt-3.5-turbo"
temperature = 1.0
stop_sign = ["\n\n\n", "User:"]
top_p = 0.35
generation_count = 1
stream = false
max_tokens = 8192
```

## Development Setup

1. **Clone the Repository**:
    ```bash
    git clone https://github.com/Whth/fabricatio.git
    cd fabricatio
    ```
2. **Install Dependencies**:
    ```bash
    make dev
    ```
3. **Run Tests**:
    ```bash
    make test
    ```

## Contributing

Contributions are welcome! Follow these steps:

1. Fork the repository.
2. Create your feature branch (`git checkout -b feature/new-feature`).
3. Commit your changes (`git commit -am 'Add new feature'`).
4. Push to the branch (`git push origin feature/new-feature`).
5. Create a new Pull Request.

## License

Fabricatio is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Acknowledgments

Special thanks to the contributors and maintainers of:

- [PyO3](https://github.com/PyO3/pyo3)
- [Maturin](https://github.com/PyO3/maturin)
- [Handlebars.rs](https://github.com/sunng87/handlebars-rust)
- [LiteLLM](https://github.com/BerriAI/litellm)
