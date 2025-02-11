# Fabricatio

---

Fabricatio is a powerful framework designed to facilitate the creation and management of tasks, actions, and workflows. It leverages modern Python features and libraries to provide a robust and flexible environment for building applications that require task automation and orchestration.

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
    - [Defining a Task](#defining-a-task)
    - [Creating an Action](#creating-an-action)
    - [Assigning a Role](#assigning-a-role)
    - [Logging](#logging)
- [Configuration](#configuration)
    - [LLM Configuration](#llm-configuration)
    - [Debug Configuration](#debug-configuration)
- [Examples](#examples)
    - [Simple Task Example](#simple-task-example)
    - [Complex Workflow Example](#complex-workflow-example)
- [Contributing](#contributing)
- [License](#license)

## Installation
To install Fabricatio, you can use pip:

```bash
pip install fabricatio
```

Alternatively, you can clone the repository and install it manually:

```bash
git clone https://github.com/your-repo/fabricatio.git
cd fabricatio
pip install .
```


## Usage

### Defining a Task

A task in Fabricatio is defined using the `Task` class. You can specify the name, goal, and description of the task.

```python
from fabricatio.models.task import Task

task = Task(name="say hello", goal="say hello", description="say hello to the world")
```


### Creating an Action

Actions are the building blocks of workflows. They perform specific tasks and can be asynchronous.

```python
from fabricatio import Action, logger
from fabricatio.models.task import Task

class Talk(Action):
    async def _execute(self, task_input: Task[str], **_) -> str:
        ret = "Hello fabricatio!"
        logger.info("executing talk action")
        return ret
```


### Assigning a Role

Roles in Fabricatio are responsible for executing workflows. You can define a role with a set of actions.

```python
from fabricatio.models.role import Role
from fabricatio.models.action import WorkFlow

class TestWorkflow(WorkFlow):
    pass

role = Role(name="Test Role", actions=[TestWorkflow()])
```


### Logging

Fabricatio uses Loguru for logging. You can configure the log level and file in the `config.py` file.

```python
from fabricatio.config import DebugConfig

debug_config = DebugConfig(log_level="DEBUG", log_file="fabricatio.log")
```


## Configuration

Fabricatio uses Pydantic for configuration management. You can define your settings in the `config.py` file.

### LLM Configuration

The Large Language Model (LLM) configuration is managed by the `LLMConfig` class.

```python
from fabricatio.config import LLMConfig

llm_config = LLMConfig(api_endpoint="https://api.example.com")
```


### Debug Configuration

The debug configuration is managed by the `DebugConfig` class.

```python
from fabricatio.config import DebugConfig

debug_config = DebugConfig(log_level="DEBUG", log_file="fabricatio.log")
```


## Examples

### Simple Task Example

Here is a simple example of a task that prints "Hello fabricatio!".

```python
import asyncio
from fabricatio import Action, Role, Task, WorkFlow, logger

task = Task(name="say hello", goal="say hello", description="say hello to the world")

class Talk(Action):
    async def _execute(self, task_input: Task[str], **_) -> Any:
        ret = "Hello fabricatio!"
        logger.info("executing talk action")
        return ret

class TestWorkflow(WorkFlow):
    pass

role = Role(name="Test Role", actions=[TestWorkflow()])

async def main() -> None:
    await role.act(task)

if __name__ == "__main__":
    asyncio.run(main())
```


### Complex Workflow Example

Here is a more complex example that demonstrates how to create a workflow with multiple actions.

```python
import asyncio
from fabricatio import Action, Role, Task, WorkFlow, logger

task = Task(name="complex task", goal="perform complex operations", description="a task with multiple actions")

class ActionOne(Action):
    async def _execute(self, task_input: Task[str], **_) -> Any:
        ret = "Action One executed"
        logger.info(ret)
        return ret

class ActionTwo(Action):
    async def _execute(self, task_input: Task[str], **_) -> Any:
        ret = "Action Two executed"
        logger.info(ret)
        return ret

class ComplexWorkflow(WorkFlow):
    actions = [ActionOne(), ActionTwo()]

role = Role(name="Complex Role", actions=[ComplexWorkflow()])

async def main() -> None:
    await role.act(task)

if __name__ == "__main__":
    asyncio.run(main())
```


## Contributing

Contributions to Fabricatio are welcome! Please submit a pull request with your changes.

## License

Fabricatio is licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.
