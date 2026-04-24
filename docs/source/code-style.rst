Code Style Guide
================

This document outlines the code style conventions used in the Fabricatio project.

.. contents::
   :local:
   :depth: 3

-----

Rust Conventions
----------------

Edition and Build Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- **Edition 2024**: All Rust crates use ``edition = "2024"``

  .. code-block:: toml

     [package]
     name = "thryd"
     version = "0.2.6"
     edition = "2024"

- **CDYLIB for PyO3**: Python-bound crates use ``crate-type = ["cdylib"]``

  .. code-block:: toml

     [lib]
     crate-type = ["cdylib"]

Naming Conventions
~~~~~~~~~~~~~~~~~~

- **Functions and variables**: ``snake_case``

  .. code-block:: rust

     pub fn new(model: Box<M>) -> Deployment<M> { ... }
     let identifier = self.model.identifier();

- **Types and structs**: ``PascalCase``

  .. code-block:: rust

     pub struct Deployment<M: ?Sized + Model> { ... }
     pub enum ThrydError { ... }

- **Constants**: ``SCREAMING_SNAKE_CASE``

  .. code-block:: rust

     pub const MINUTE_MS: u64 = 60_000;
     pub const SEPARATE: char = '/';

Module Organization
~~~~~~~~~~~~~~~~~~~

- Use ``pub mod`` for public modules, ``mod`` for private

  .. code-block:: rust

     pub mod cache;
     pub mod connections;
     mod deployment;  // private

- Module files: Use ``mod.rs`` for submodules or individual ``.rs`` files

  .. code-block:: rust

     // In lib.rs
     pub mod models;
     
     // In models/mod.rs or models.rs

Error Handling
~~~~~~~~~~~~~~

- **Use ``thiserror``** for creating error enums with ``#[derive(Error)]``

  .. code-block:: rust

     use thiserror::Error;

     #[derive(Error, Debug)]
     pub enum ThrydError {
         #[error("Provider '{provider}' is not available: {reason}")]
         ProviderUnavailable { provider: String, reason: String },

         #[error("HTTP request failed: {0}")]
         Reqwest(#[from] ReqwestError),
     }

     pub type Result<T> = std::result::Result<T, ThrydError>;

- **Error variants** should have human-readable messages using ``#[error(...)]``

Doc Comments
~~~~~~~~~~~~

- **Crate-level**: Use ``//!`` at the top of lib.rs

  .. code-block:: rust

     //! Thryd - A lightweight, embedded LLM request router with caching.
     //!
     //! This library provides:
     //! - Multi-provider LLM request routing
     //! - Token usage tracking and rate limiting

- **Function-level**: Use ``///`` with markdown formatting

  .. code-block:: rust

     /// Represents the unified error types for the Thryd system.
     ///
     /// This enum consolidates various failure scenarios including network issues,
     /// provider unavailability, configuration faults, and data validation errors.

PyO3 Patterns
~~~~~~~~~~~~~~

- **PyModule**: ``#[pymodule]`` with `` Bound<'_, PyModule>`` parameter

  .. code-block:: rust

     #[pymodule]
     fn rust(_python: Python, _m: &Bound<'_, PyModule>) -> PyResult<()> {
         Ok(())
     }

- **PyClass**: ``#[pyclass]`` with optional ``#[cfg_attr(feature = "stubgen", ...)]``

  .. code-block:: rust

     #[derive(Default)]
     #[cfg_attr(feature = "stubgen", pyo3_stub_gen::derive::gen_stub_pyclass)]
     #[pyclass]
     pub struct Logger;

- **PyMethods**: ``#[pymethods]`` with ``#[cfg_attr(...)]`` for conditional stub generation

  .. code-block:: rust

     #[cfg_attr(feature = "stubgen", pyo3_stub_gen::derive::gen_stub_pymethods)]
     #[pymethods]
     impl Logger {
         fn info(&self, msg: &str) -> PyResult<()> { ... }
     }

Async Patterns
~~~~~~~~~~~~~~

- **Use ``async-trait``** for async methods in traits

  .. code-block:: rust

     use async_trait::async_trait;

     #[async_trait]
     pub trait CompletionModel: Model {
         async fn completion(&self, request: CompletionRequest) -> crate::Result<String>;
     }

- **Let chains** for conditional await

  .. code-block:: rust

     if let Some(tracker) = self.usage_tracker.as_ref()
         && res.is_ok()
     {
         tracker.lock().await.add_request_raw(input, "".to_string());
     }

- **Tokio** for async runtime with multi-thread features

  .. code-block:: toml

     tokio = { version = "1.51.0", features = ["rt-multi-thread", "macros"] }

Traits and Generics
~~~~~~~~~~~~~~~~~~~

- **Generic bounds** use ``?Sized`` when appropriate

  .. code-block:: rust

     pub struct Deployment<M: ?Sized + Model> {
         model: Box<M>,
     }

- **Builder pattern** with ``mut self`` and ``-> Self``

  .. code-block:: rust

     pub fn with_usage_constrain(mut self, rpm: Option<u64>, tpm: Option<u64>) -> Self {
         self.usage_tracker = Some(Mutex::new(UsageTracker::with_quota(tpm, rpm)));
         self
     }

Feature Flags
~~~~~~~~~~~~~

- Use ``#[cfg(feature = "...")]`` for optional functionality

  .. code-block:: rust

     #[cfg(feature = "pyo3")]
     impl_as_pyerr!(thryd::ThrydError, PyRuntimeError);

- Define features in ``[features]`` section

  .. code-block:: toml

     [features]
     pyo3 = ["dep:pyo3"]
     pystub = ["dep:pyo3-stub-gen"]

-----

Python Conventions
------------------

Type Hints
~~~~~~~~~~

- **Full annotations** required (project uses ``Typing :: Typed`` classifier)

  .. code-block:: python

     from typing import Any, ClassVar, Dict, Generator, Self, Sequence, Tuple, Type, Union, final

     async def _execute(self, *_: Any, **cxt) -> Any: ...

- **Generic type aliases** using ``type`` statement

  .. code-block:: python

     type NameSpace = Union[str, List[str]]
     type Callback[T] = Callable[[T], Coroutine[None, None, None]]

- **Self returns** for method chaining

  .. code-block:: python

     def update_init_context(self, /, **kwargs) -> Self: ...

Async Patterns
~~~~~~~~~~~~~~

- **``async def``** for all async functions

  .. code-block:: python

     @pytest.mark.asyncio
     async def test_router_completion(mock_router: Router, ret_value: str) -> None:
         response = await mock_router.completion(...)

- **Use asyncio primitives**: ``create_task``, ``Queue``, ``sleep``

  .. code-block:: python

     from asyncio import Queue, create_task

     act_task = create_task(step.act(context))

Naming Conventions
~~~~~~~~~~~~~~~~~~

- **Classes**: ``PascalCase``

  .. code-block:: python

     class Action(WithBriefing, ABC): ...
     class WorkFlow(WithBriefing): ...

- **Functions and variables**: ``snake_case``

  .. code-block:: python

     def update_init_context(self, /, **kwargs) -> Self: ...
     extra_init_context: Dict[str, Any] = Field(default_factory=dict)

- **Private attributes**: ``_prefix``

  .. code-block:: python

     _output: Queue[T | None] = PrivateAttr(default_factory=Queue)
     _status: TaskStatus = PrivateAttr(default=TaskStatus.Pending)

Docstring Style
~~~~~~~~~~~~~~~

- **Google-style docstrings** (configured in ruff: ``convention = "google"``)

  .. code-block:: python

     def update_init_context(self, /, **kwargs) -> Self:
         """Update the initial context with additional key-value pairs.

         Args:
             **kwargs: Key-value pairs to add to the initial context.

         Returns:
             Self: The workflow instance for method chaining.
         """
         self.extra_init_context.update(kwargs)
         return self

- **Module-level docstrings** at top of file

  .. code-block:: python

     """Module that contains the classes for defining and executing task workflows.

     This module provides the Action and WorkFlow classes for creating structured
     task execution pipelines.

     Classes:
         Action: Base class for defining executable actions with context management.
         WorkFlow: Manages action sequences, context propagation, and task lifecycle.
     """

Pydantic v2 Patterns
~~~~~~~~~~~~~~~~~~~~

- **``ConfigDict``** for model configuration

  .. code-block:: python

     model_config = ConfigDict(use_attribute_docstrings=True)

- **``Field``** for field definitions with docstrings as descriptions

  .. code-block:: python

     name: str = Field(default="")
     """The name of the action."""

     goals: List[str] = Field(default_factory=list)
     """Objectives the task aims to achieve."""

- **``PrivateAttr``** for private fields

  .. code-block:: python

     from pydantic import Field, PrivateAttr

     _context: Queue[Dict[str, Any]] = PrivateAttr(default_factory=lambda: Queue(maxsize=1))

- **Generic models** with ``[T]`` syntax

  .. code-block:: python

     class Task[T](WithBriefing, ProposedAble, WithDependency):
         """A class representing a task with status management and output handling."""

Imports Organization
~~~~~~~~~~~~~~~~~~~~

- **Type checking blocks** for circular imports

  .. code-block:: python

     from typing import TYPE_CHECKING

     if TYPE_CHECKING:
         from fabricatio_core.models.task import Task as _Task

- **typing extensions** for modern Python versions

  .. code-block:: python

     from typing import Self, Never, Literal

Decorators
~~~~~~~~~~

- **``@final``** from typing for preventing subclassing

  .. code-block:: python

     @final
     def model_post_init(self, __context: Any) -> None: ...

- **Custom decorators** in ``decorators.py``

  .. code-block:: python

     def cfg_on[**P, R](feats: Sequence[str]) -> Callable[[Callable[P, R]], Callable[P, R]]:
         """Synchronous version of the cfg_on decorator."""
         def _decorator(func: Callable[P, R]) -> Callable[P, R]:
             ...

-----

Git Conventions
---------------

Branch Naming
~~~~~~~~~~~~~

- **Feature branches**: ``feat/<feature-name>``

  .. code-block:: bash

     git checkout -b feat/new-feature

- **Bugfix branches**: ``fix/<bug-name>``

- **Chore branches**: ``chore/<task-name>``

Commit Messages
~~~~~~~~~~~~~~~

- **Subject line**: Short, descriptive summary (50 chars or less recommended)

- **Body**: Explain "why" not "what"

  .. code-block:: bash

     git commit -am 'Add new feature'

- **Types**: Use conventional commit prefixes

  - ``feat:`` - New feature
  - ``fix:`` - Bug fix
  - ``docs:`` - Documentation
  - ``refactor:`` - Code refactoring
  - ``test:`` - Adding tests
  - ``chore:`` - Maintenance tasks

-----

Documentation Conventions
-------------------------

Rust Documentation
~~~~~~~~~~~~~~~~~

- **Crate documentation** in ``lib.rs`` with module-level doc comments

- **README files** for each crate with:

  - Badges (crates.io, docs.rs, license)
  - Overview section
  - Key features list
  - Usage examples
  - Installation instructions
  - Configuration details

Python Documentation
~~~~~~~~~~~~~~~~~~~

- **Package README** in ``README.md`` with similar structure

- **Docstrings** on all public classes and functions

-----

Testing Conventions
-------------------

Python Testing (pytest)
~~~~~~~~~~~~~~~~~~~~~~~

- **Test file location**: ``python/tests/`` or ``python/<package>/tests/``

  .. code-block::

     packages/fabricatio-core/python/tests/test_usages.py

- **Test naming**: ``test_<functionality>.py``

  .. code-block:: python

     @pytest.mark.asyncio
     async def test_router_completion(mock_router: Router, ret_value: str) -> None:
         """Test basic router completion functionality."""
         response = await mock_router.completion(...)
         assert response == ret_value

- **Fixtures** with descriptive docstrings

  .. code-block:: python

     @pytest.fixture
     def mock_router(ret_value: str) -> Router:
         """Fixture to create a mocked router with predefined response.

         Args:
             ret_value: The value to be returned by the mocked completion
         Returns:
             Configured AsyncMock router object
         """
         return return_string(ret_value)

- **Parametrized tests** with ``@pytest.mark.parametrize``

  .. code-block:: python

     @pytest.mark.parametrize("ret_value", ["Hi", "Hello"])
     @pytest.mark.asyncio
     async def test_router_completion(mock_router: Router, ret_value: str) -> None: ...

- **Async mode**: ``asyncio_mode = "auto"`` in pytest config

  .. code-block:: toml

     [tool.pytest.ini_options]
     asyncio_mode = "auto"
     asyncio_default_fixture_loop_scope = "function"

Rust Testing
~~~~~~~~~~~~

- **Inline tests** with ``#[test]`` or ``#[cfg(test)]`` module

  .. code-block:: rust

     #[test]
     fn test_something() { ... }

- **Doc tests** in documentation comments

  .. code-block:: rust

     /// # Examples
     ///
     /// ```rust
     /// use thryd::*;
     /// ```

-----

Linting and Formatting
----------------------

Rust
~~~~

- **Formatting**: ``cargo fmt``

  .. code-block:: bash

     just fix  # Runs cargo fmt

- **Linting**: ``cargo clippy``

- **Applied automatically** via ``just fix``

Python
~~~~~~

- **Ruff** for linting and formatting

  .. code-block:: toml

     [tool.ruff]
     line-length = 120
     target-version = "py312"

     [tool.ruff.format]
     quote-style = "double"

     [tool.ruff.lint]
     select = ["F", "I", "N", "D", "W", "ANN", "ASYNC", ...]
     ignore = ["ANN401", "ANN003", ...]

     [tool.ruff.lint.pydocstyle]
     convention = "google"

- **Pyright** for type checking

  .. code-block:: toml

     [tool.pyright]
     include = ["python/fabricatio/**/*.py", "packages/**/*.py"]

- **Format command**:

  .. code-block:: bash

     just fix  # Runs: cargo fmt && ruff format && ruff check --fix

-----

Project Structure
-----------------

Python Package Structure
~~~~~~~~~~~~~~~~~~~~~~~~

::

    packages/<package-name>/
    ├── python/
    │   └── fabricatio_<name>/
    │       ├── __init__.py      # Package entry with exports
    │       ├── actions/
    │       │   └── __init__.py
    │       ├── capabilities/
    │       │   └── __init__.py
    │       ├── models/
    │       │   └── __init__.py
    │       └── workflows/
    │           └── __init__.py
    ├── pyproject.toml
    ├── README.md
    └── LICENSE

Rust Crate Structure
~~~~~~~~~~~~~~~~~~~~

::

    crates/<crate-name>/
    ├── src/
    │   ├── lib.rs          # Main entry with pub modules
    │   ├── error.rs        # Error types (optional)
    │   └── <feature>.rs    # Feature modules (optional)
    ├── Cargo.toml
    ├── README.md
    └── LICENSE

Module Exports
~~~~~~~~~~~~~~

- **Python**: Export in ``__init__.py``

  .. code-block:: python

     """Fabricatio is a Python library for building llm app using event-based agent structure."""

     from fabricatio_core import CONFIG, ROUTER, Action, Event, Role, Task, WorkFlow

     __all__ = ["CONFIG", "ROUTER", "Action", "Event", "Role", "Task", "WorkFlow"]

- **Rust**: Re-export in ``lib.rs``

  .. code-block:: rust

     pub use cache::*;
     pub use constants::*;
     pub use error::{Result, ThrydError};

-----

Development Commands
--------------------

.. code-block:: bash

    # Initialize development environment
    make init

    # Build in development mode
    make dev

    # Run tests
    make tests

    # Fix linting issues
    make fix

    # Using just (preferred)
    just init
    just dev
    just test
    just fix

-----

See Also
--------

- :doc:`contributing` - Contributing guidelines
- :doc:`development` - Development setup
- :doc:`architecture` - Project architecture
