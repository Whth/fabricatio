## Usage

### Defining a Task

```python
from fabricatio.models.task import Task

task = Task(name="say hello", goal="say hello", description="say hello to the world")
```


### Creating an Action

```python
from fabricatio import Action, logger
from fabricatio.models.task import Task

class Talk(Action):
    async def _execute(self, task_input: Task[str], **_) -> Any:
        ret = "Hello fabricatio!"
        logger.info("executing talk action")
        return ret
```


### Assigning a Role

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

```python
from fabricatio.config import Settings

settings = Settings(llm=LLMConfig(api_endpoint="https://api.example.com"))
```


## Testing

Fabricatio includes a set of tests to ensure the framework works as expected. You can run the tests using `pytest`.

```bash
pytest
```


## Contributing

Contributions to Fabricatio are welcome! Please submit a pull request with your changes.

## License

Fabricatio is licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.
