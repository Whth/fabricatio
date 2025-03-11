# Fabricatio

![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)
![Build Status](https://img.shields.io/badge/build-passing-brightgreen)

## Overview

Fabricatio is a Python library designed for building LLM (Large Language Model) applications using an event-based agent structure. It integrates Rust for performance-critical tasks, utilizes Handlebars for templating, and employs PyO3 for Python bindings.

## Features

- **Event-Based Architecture**: Utilizes an EventEmitter pattern for robust task management.
- **LLM Integration**: Supports interactions with large language models for intelligent task processing.
- **Templating Engine**: Uses Handlebars for dynamic content generation.
- **Toolboxes**: Provides predefined toolboxes for common operations like file manipulation and arithmetic.
- **Async Support**: Fully asynchronous for efficient execution.
- **Extensible**: Easy to extend with custom actions, workflows, and tools.

## Installation

### Using UV (Recommended)

To install Fabricatio using `uv` (a package manager for Python):

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

For production builds:

```bash
# Build distribution packages
make bdist
```

This will generate distribution files in the `dist` directory.

## Usage

### Basic Example

#### Simple Hello World Program

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

### Advanced Examples

#### Simple Chat

Demonstrates a basic chat application.

```python
"""Simple chat example."""
import asyncio
from fabricatio import Action, Role, Task, WorkFlow, logger
from fabricatio.models.events import Event
from questionary import text

class Talk(Action):
    """Action that says hello to the world."""

    output_key: str = "task_output"

    async def _execute(self, task_input: Task[str], **_) -> int:
        counter = 0
        try:
            while True:
                user_say = await text("User: ").ask_async()
                gpt_say = await self.aask(
                    user_say,
                    system_message=f"You have to answer to user obeying task assigned to you:\n{task_input.briefing}",
                )
                print(f"GPT: {gpt_say}")  # noqa: T201
                counter += 1
        except KeyboardInterrupt:
            logger.info(f"executed talk action {counter} times")
        return counter

async def main() -> None:
    """Main function."""
    role = Role(
        name="talker",
        description="talker role",
        registry={Event.instantiate_from("talk").push_wildcard().push("pending"): WorkFlow(name="talk", steps=(Talk,))},
    )

    task = await role.propose_task(
        "you have to act as a helpful assistant, answer to all user questions properly and patiently"
    )
    _ = await task.delegate("talk")

if __name__ == "__main__":
    asyncio.run(main())
```

#### Simple RAG

Demonstrates Retrieval-Augmented Generation (RAG).

```python
"""Simple chat example."""
import asyncio
from fabricatio import RAG, Action, Role, Task, WorkFlow, logger
from fabricatio.models.events import Event
from questionary import text

class Talk(Action, RAG):
    """Action that says hello to the world."""

    output_key: str = "task_output"

    async def _execute(self, task_input: Task[str], **_) -> int:
        counter = 0

        self.init_client().view("test_collection", create=True)
        await self.consume_string(
            [
                "Company policy clearly stipulates that all employees must arrive at the headquarters building located at 88 Jianguo Road, Chaoyang District, Beijing before 9 AM daily.",
                "According to the latest revised health and safety guidelines, employees must wear company-provided athletic gear when using the company gym facilities.",
                "Section 3.2.1 of the employee handbook states that pets are not allowed in the office area under any circumstances.",
                "To promote work efficiency, the company has quiet workspaces at 100 Century Avenue, Pudong New District, Shanghai, for employees who need high concentration for their work.",
                "According to the company's remote work policy, employees can apply for a maximum of 5 days of working from home per month, but must submit the application one week in advance.",
                "The company has strict regulations on overtime. Unless approved by direct supervisors, no form of work is allowed after 9 PM.",
                "Regarding the new regulations for business travel reimbursement, all traveling personnel must submit detailed expense reports within five working days after returning.",
                "Company address: 123 East Sports Road, Tianhe District, Guangzhou, Postal Code: 510620.",
                "Annual team building activities will be held in the second quarter of each year, usually at a resort within a two-hour drive from the Guangzhou headquarters.",
                "Employees who are late more than three times will receive a formal warning, which may affect their year-end performance evaluation.",
            ]
        )
        try:
            while True:
                user_say = await text("User: ").ask_async()
                if user_say is None:
                    break
                gpt_say = await self.aask_retrieved(
                    user_say,
                    user_say,
                    extra_system_message=f"You have to answer to user obeying task assigned to you:\n{task_input.briefing}",
                )
                print(f"GPT: {gpt_say}")  # noqa: T201
                counter += 1
        except KeyboardInterrupt:
            logger.info(f"executed talk action {counter} times")
        return counter

async def main() -> None:
    """Main function."""
    role = Role(
        name="talker",
        description="talker role but with rag",
        registry={Event.instantiate_from("talk").push_wildcard().push("pending"): WorkFlow(name="talk", steps=(Talk,))},
    )

    task = await role.propose_task(
        "you have to act as a helpful assistant, answer to all user questions properly and patiently"
    )
    _ = await task.delegate("talk")

if __name__ == "__main__":
    asyncio.run(main())
```

#### Extract Article

Demonstrates extracting the essence of an article from a file.

```python
"""Example of proposing a task to a role."""
import asyncio
from typing import List

from fabricatio import ArticleEssence, Event, ExtractArticleEssence, Role, Task, WorkFlow, logger

async def main() -> None:
    """Main function."""
    role = Role(
        name="Researcher",
        description="Extract article essence",
        registry={
            Event.quick_instantiate("article"): WorkFlow(
                name="extract",
                steps=(ExtractArticleEssence(output_key="task_output"),),
            )
        },
    )
    task: Task[List[ArticleEssence]] = await role.propose_task(
        "Extract the essence of the article from the file at './7.md'"
    )
    ess = (await task.delegate("article")).pop()
    logger.success(f"Essence:\n{ess.display()}")

if __name__ == "__main__":
    asyncio.run(main())
```

#### Propose Task

Demonstrates proposing a task to a role.

```python
"""Example of proposing a task to a role."""
import asyncio
from typing import Any

from fabricatio import Action, Event, Role, Task, WorkFlow, logger

class Talk(Action):
    """Action that says hello to the world."""

    output_key: str = "task_output"

    async def _execute(self, **_) -> Any:
        ret = "Hello fabricatio!"
        logger.info("executing talk action")
        return ret

async def main() -> None:
    """Main function."""
    role = Role(
        name="talker",
        description="talker role",
        registry={Event.quick_instantiate("talk"): WorkFlow(name="talk", steps=(Talk,))},
    )
    logger.info(f"Task example:\n{Task.formated_json_schema()}")
    logger.info(f"proposed task: {await role.propose_task('write a rust clap cli that can download a html page')}")

if __name__ == "__main__":
    asyncio.run(main())
```

#### Review

Demonstrates reviewing code.

```python
"""Example of review usage."""
import asyncio

from fabricatio import Role, logger

async def main() -> None:
    """Main function."""
    role = Role(
        name="Reviewer",
        description="A role that reviews the code.",
    )

    code = await role.aask(
        "write a cli app using rust with clap which can generate a basic manifest of a standard rust project, output code only,no extra explanation"
    )

    logger.success(f"Code: \n{code}")
    res = await role.review_string(code, "If the cli app is of good design")
    logger.success(f"Review: \n{res.display()}")
    await res.supervisor_check()
    logger.success(f"Review: \n{res.display()}")

if __name__ == "__main__":
    asyncio.run(main())
```

#### Write Outline

Demonstrates writing an outline for an article in Typst format.

```python
"""Example of using the library."""
import asyncio

from fabricatio import Event, Role, WriteOutlineWorkFlow, logger

async def main() -> None:
    """Main function."""
    role = Role(
        name="Undergraduate Researcher",
        description="Write an outline for an article in typst format.",
        registry={Event.quick_instantiate(ns := "article"): WriteOutlineWorkFlow},
    )

    proposed_task = await role.propose_task(
        "You need to read the `./article_briefing.txt` file and write an outline for the article in typst format. The outline should be saved in the `./out.typ` file.",
    )
    path = await proposed_task.delegate(ns)
    logger.success(f"The outline is saved in:\n{path}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Configuration

The configuration for Fabricatio is managed via environment variables or TOML files. The default configuration file (`config.toml`) can be overridden by specifying a custom path.

Example `config.toml`:

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

To set up a development environment for Fabricatio:

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

4. **Build Documentation**:
    ```bash
    make docs
    ```

## Contributing

Contributions are welcome! Please follow these guidelines when contributing:

1. Fork the repository.
2. Create your feature branch (`git checkout -b feature/new-feature`).
3. Commit your changes (`git commit -am 'Add new feature'`).
4. Push to the branch (`git push origin feature/new-feature`).
5. Create a new Pull Request.

## License

Fabricatio is licensed under the MIT License. See [LICENSE](LICENSE) for more details.

## Acknowledgments

Special thanks to the contributors and maintainers of:
- [PyO3](https://github.com/PyO3/pyo3)
- [Maturin](https://github.com/PyO3/maturin)
- [Handlebars.rs](https://github.com/sunng87/handlebars-rust)