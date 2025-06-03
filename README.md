<p style="text-align: center;">   
<picture>
        <img src="./assets/band.png" width="80%" alt="Fabricatio Logo" loading="lazy">
</picture>
</p>




[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio)](https://pypi.org/project/fabricatio/)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio)](https://pypi.org/project/fabricatio/)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/Whth/fabricatio)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio/week)](https://pepy.tech/projects/fabricatio)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio)](https://pepy.tech/projects/fabricatio)
[![Bindings: PyO3](https://img.shields.io/badge/bindings-pyo3-green)](https://github.com/PyO3/pyo3)
[![Powered by LiteLLM](https://img.shields.io/badge/Powered%20by-LiteLLM-blue)](https://github.com/BerriAI/litellm)
[![Build Tool: uv + maturin](https://img.shields.io/badge/built%20with-uv%20%2B%20maturin-orange)](https://github.com/astral-sh/uv)
[![Documentation Status](https://readthedocs.org/projects/fabricatio/badge/?version=latest)](https://fabricatio.readthedocs.io/en/latest/?badge=fabricatio)
[![Build Package](https://github.com/Whth/fabricatio/actions/workflows/build-package.yaml/badge.svg)](https://github.com/Whth/fabricatio/actions/workflows/build-package.yaml)
[![Ruff Lint](https://github.com/Whth/fabricatio/actions/workflows/ruff.yaml/badge.svg)](https://github.com/Whth/fabricatio/actions/workflows/ruff.yaml)
[![Tests](https://github.com/Whth/fabricatio/actions/workflows/tests.yaml/badge.svg)](https://github.com/Whth/fabricatio/actions/workflows/tests.yaml)
![GitHub Issues](https://img.shields.io/github/issues/Whth/fabricatio)
![GitHub Pull Requests](https://img.shields.io/github/issues-pr/Whth/fabricatio)
![GitHub Stars](https://img.shields.io/github/stars/Whth/fabricatio)
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
import asyncio
from fabricatio import Action, Role, Task, logger, WorkFlow, Event
from typing import Any


class Hello(Action):
    name: str = "hello"
    output_key: str = "task_output"

    async def _execute(self, task_input: Task[str], **_) -> Any:
        ret = "Hello fabricatio!"
        logger.info("executing talk action")
        return ret


async def main() -> None:
    Role(
        name="talker",
        description="talker role",
        registry={Event.quick_instantiate("talk"): WorkFlow(name="talk", steps=(Hello,))}
    )

    task = Task(name="say hello", goals=["say hello"], description="say hello to the world")
    result = await task.delegate("talk")
    logger.success(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
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
