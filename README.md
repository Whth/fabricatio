# Fabricatio

![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)
![Build Status](https://img.shields.io/badge/build-passing-brightgreen)

## Overview

Fabricatio is a streamlined Python library for building LLM applications using an event-based agent structure. It leverages Rust for performance-critical tasks, Handlebars for templating, and PyO3 for Python bindings.

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

# Install the package in development mode with uv
uv --with-editable . maturin develop --uv -r
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
from fabricatio import Action, Role, Task, logger, WorkFlow
from typing import Any

class Hello(Action):
    name: str = "hello"
    output_key: str = "task_output"

    async def _execute(self, task_input: Task[str], **_) -> Any:
        ret = "Hello fabricatio!"
        logger.info("executing talk action")
        return ret

async def main() -> None:
    role = Role(
        name="talker",
        description="talker role",
        registry={Task.pending_label: WorkFlow(name="talk", steps=(Hello,))}
    )

    task = Task(name="say hello", goals="say hello", description="say hello to the world")
    result = await task.delegate()
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
    uv --with-editable . maturin develop --uv -r
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