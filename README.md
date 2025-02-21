Sure, I can help you create a detailed `README.md` for the `fabricatio` project. Given that you're using `uv` instead of `pip`, and leveraging `maturin`, `pyo3`, `Rust`, and `Handlebars` with an event emitter system, it's essential to provide comprehensive instructions and examples. Here’s a well-structured `README.md`:

---

# Fabricatio

![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)
![Build Status](https://img.shields.io/badge/build-passing-brightgreen)
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

Below are some basic examples demonstrating how to use Fabricatio for different purposes.

#### Simple Hello World Program

```python
import asyncio
from fabricatio import Action, Role, Task, logger


class Hello(Action):
    """Action that says hello."""

    name: str = "hello"
    output_key: str = "task_output"

    async def _execute(self, task_input: Task[str], **_) -> Any:
        ret = "Hello fabricatio!"
        logger.info("executing talk action")
        return ret


async def main() -> None:
    """Main function."""
    role = Role(
        name="talker", 
        description="talker role", 
        registry={Task.pending_label: WorkFlow(name="talk", steps=(Hello,))}
    )

    task = Task(name="say hello", goal="say hello", description="say hello to the world")
    result = await task.delegate()
    logger.success(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
```

#### Writing and Dumping Code

```python
import asyncio
from fabricatio import Action, Event, PythonCapture, Role, Task, ToolBox, WorkFlow, fs_toolbox, logger


class WriteCode(Action):
    """Action that writes code based on a prompt."""

    name: str = "write code"
    output_key: str = "source_code"

    async def _execute(self, task_input: Task[str], **_) -> str:
        return await self.aask_validate(
            task_input.briefing,
            validator=PythonCapture.capture,
        )


class DumpCode(Action):
    """Action that dumps code to the file system."""

    name: str = "dump code"
    description: str = "Dump code to file system"
    toolboxes: set[ToolBox] = {fs_toolbox}
    output_key: str = "task_output"

    async def _execute(self, task_input: Task, source_code: str, **_) -> Any:
        path = await self.handle_fin_grind(task_input, {"source_code": source_code})
        return path[0] if path else None


async def main() -> None:
    """Main function."""
    role = Role(
        name="Coder",
        description="A python coder who can write and document code",
        registry={
            Event.instantiate_from("coding.*").push("pending"): WorkFlow(
                name="write code", steps=(WriteCode, DumpCode)
            ),
        },
    )

    prompt = "write a Python CLI app which prints 'hello world' n times with detailed Google-style docstring. Write the source code to `cli.py`."

    proposed_task = await role.propose(prompt)
    path = await proposed_task.move_to("coding").delegate()
    logger.success(f"Code Path: {path}")


if __name__ == "__main__":
    asyncio.run(main())
```

#### Proposing Tasks

```python
import asyncio
from typing import Any

from fabricatio import Action, Role, Task, WorkFlow, logger


class WriteDocumentation(Action):
    """Action that generates documentation for the code in markdown format."""

    name: str = "write documentation"
    description: str = "Write detailed documentation for the provided code."
    output_key: str = "task_output"

    async def _execute(self, task_input: Task[str], **_) -> str:
        return await self.aask(task_input.briefing)


async def main() -> None:
    """Main function."""
    role = Role(
        name="Documenter",
        description="Role responsible for writing documentation.",
        registry={
            "doc.*": WorkFlow(name="write documentation", steps=(WriteDocumentation,))
        }
    )

    prompt = "write a Rust clap CLI that downloads an HTML page"
    proposed_task = await role.propose(prompt)
    documentation = await proposed_task.move_to("doc").delegate()
    logger.success(f"Documentation:\n{documentation}")


if __name__ == "__main__":
    asyncio.run(main())
```

#### Complex Workflow Handling

```python
import asyncio
from fabricatio import Action, Event, Role, Task, WorkFlow, logger


class WriteCode(Action):
    """Action that writes code based on a prompt."""

    name: str = "write code"
    output_key: str = "source_code"

    async def _execute(self, task_input: Task[str], **_) -> str:
        return await self.aask_validate(
            task_input.briefing,
            validator=PythonCapture.capture,
        )


class WriteDocumentation(Action):
    """Action that generates documentation for the code in markdown format."""

    name: str = "write documentation"
    description: str = "Write detailed documentation for the provided code."
    output_key: str = "task_output"

    async def _execute(self, task_input: Task[str], **_) -> str:
        return await self.aask(task_input.briefing)


async def main() -> None:
    """Main function."""
    role = Role(
        name="Developer",
        description="A developer who can write code and documentation.",
        registry={
            Event.instantiate_from("coding.*").push("pending"): WorkFlow(
                name="write code", steps=(WriteCode,)
            ),
            Event.instantiate_from("doc.*").push("pending"): WorkFlow(
                name="write documentation", steps=(WriteDocumentation,)
            ),
        }
    )

    # Propose a coding task
    code_task_prompt = "write a Python CLI app which adds numbers from a file."
    proposed_task = await role.propose(code_task_prompt)
    code = await proposed_task.move_to("coding").delegate()
    logger.success(f"Code:\n{code}")

    # Propose a documentation task
    doc_task_prompt = f"{code}\n\nwrite Readme.md file for the above code."
    proposed_doc_task = await role.propose(doc_task_prompt)
    documentation = await proposed_doc_task.move_to("doc").delegate()
    logger.success(f"Documentation:\n{documentation}")


if __name__ == "__main__":
    asyncio.run(main())
```

### Advanced Examples

#### Template Management and Rendering

```python
from fabricatio._rust_instances import template_manager

template_name = "claude-xml.hbs"
data = {
    "absolute_code_path": "/path/to/project",
    "source_tree": "source tree content",
    "files": [{"path": "file1.py", "code": "print('Hello')"}],
}

rendered_template = template_manager.render_template(template_name, data)
print(rendered_template)
```

#### Handling Security Vulnerabilities

```python
from fabricatio.models.usages import ToolBoxUsage
from fabricatio.models.task import Task

toolbox_usage = ToolBoxUsage()

async def handle_security_vulnerabilities():
    task = Task(
        name="Security Check",
        goal=["Identify security vulnerabilities"],
        description="Perform a thorough security review on the project.",
        dependencies=["./src/main.py"]
    )
    
    vulnerabilities = await toolbox_usage.gather_tools_fine_grind(task)
    for vulnerability in vulnerabilities:
        print(f"Found vulnerability: {vulnerability.name}")
```

#### Managing CTF Challenges

```python
import asyncio

from fabricatio.models.usages import ToolBoxUsage
from fabricatio.models.task import Task

toolbox_usage = ToolBoxUsage()

async def solve_ctf_challenge(challenge_name: str, challenge_description: str, files: list[str]):
    task = Task(
        name=challenge_name,
        goal=[f"Solve {challenge_name} challenge"],
        description=challenge_description,
        dependencies=files
    )
    
    solution = await toolbox_usage.gather_tools_fine_grind(task)
    print(f"Challenge Solved: {solution}")

if __name__ == "__main__":
    asyncio.run(solve_ctf_challenge("Binary Exploitation", "CTF Binary Exploitation Challenge", ["./challenges/binary_exploit"]))
```

### Configuration

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

### Development Setup

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

### Contributing

Contributions are welcome! Please follow these guidelines when contributing:

1. Fork the repository.
2. Create your feature branch (`git checkout -b feature/new-feature`).
3. Commit your changes (`git commit -am 'Add new feature'`).
4. Push to the branch (`git push origin feature/new-feature`).
5. Create a new Pull Request.

### License

Fabricatio is licensed under the MIT License. See [LICENSE](LICENSE) for more details.

### Acknowledgments

Special thanks to the contributors and maintainers of:
- [PyO3](https://github.com/PyO3/pyo3)
- [Maturin](https://github.com/PyO3/maturin)
- [Handlebars.rs](https://github.com/sunng87/handlebars-rust)

---

Feel free to customize this README further as needed. If you have any specific sections or additional examples you'd like to include, let me know!