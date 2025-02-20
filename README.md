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

---

### Additional Features and Modules

#### Advanced Models and Functionalities

The `advanced.py` module provides advanced models and functionalities for handling complex tasks and workflows.

```python
from fabricatio.models.advanced import ProposeTask, HandleTask

class ProposeTaskExample(ProposeTask):
    pass

class HandleTaskExample(HandleTask):
    pass
```


#### Toolboxes

Fabricatio includes various toolboxes for different types of operations. For example, the `arithmetic.py` toolbox provides arithmetic operations.

```python
from fabricatio.toolboxes.arithmetic import add, subtract, multiply, divide

result = add(1, 2)
print(result)  # Output: 3
```


#### File System Operations

The `fs.py` toolbox offers tools for file system operations such as copying, moving, deleting files, and creating directories.

```python
from fabricatio.toolboxes.fs import copy_file, move_file, delete_file, create_directory

copy_file("source.txt", "destination.txt")
move_file("old_location.txt", "new_location.txt")
delete_file("file_to_delete.txt")
create_directory("new_directory")
```


#### Logging Setup

The logging setup in Fabricatio is handled by the `journal.py` module, which configures Loguru for logging.

```python
from fabricatio.journal import logger

logger.debug("This is a debug message.")
logger.info("This is an info message.")
logger.success("This is a success message.")
logger.warning("This is a warning message.")
logger.error("This is an error message.")
logger.critical("This is a critical message.")
```


#### Configuration Management

The configuration management in Fabricatio is handled by the `config.py` module, which uses Pydantic for defining and validating configurations.

```python
from fabricatio.config import Settings, LLMConfig, DebugConfig

settings = Settings()
llm_config = LLMConfig(api_endpoint="https://api.example.com")
debug_config = DebugConfig(log_level="DEBUG", log_file="fabricatio.log")
```


#### Testing

Fabricatio includes a suite of test cases to ensure the stability and correctness of the codebase. The tests are located in the `tests` directory and cover various modules and functionalities.

```python
# Example of a test case for the config module
import pytest
from fabricatio.config import DebugConfig

def test_debug_config_initialization():
    temp_log_file = "fabricatio.log"
    debug_config = DebugConfig(log_level="DEBUG", log_file=temp_log_file)
    assert debug_config.log_level == "DEBUG"
    assert str(debug_config.log_file) == temp_log_file
```


---

### Conclusion

Fabricatio is a versatile and powerful framework for managing tasks, actions, and workflows. It provides a robust set of tools and features to facilitate task automation and orchestration. Whether you're building a simple script or a complex application, Fabricatio has the capabilities to meet your needs.

For more detailed information and examples, please refer to the [official documentation](https://fabricatio.readthedocs.io).

---

If you have any questions or need further assistance, feel free to reach out to the community or open an issue on the GitHub repository.

Happy coding!

