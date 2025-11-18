# `fabricatio-core`

A foundational Python library providing core components for building LLM-driven applications using an event-based agent
structure.

## 📦 Installation

This package is part of the `fabricatio` monorepo and is available as a single package using either pip or uv:

```bash
pip install fabricatio
# or
uv pip install fabricatio
```

For a full installation that includes this package and all other components of `fabricatio`:

```bash
pip install fabricatio[full]
# or
uv pip install fabricatio[full]
```

## 🔍 Overview

Provides essential tools for:

- Event-based architecture patterns
The event-based architecture patterns in this library enable a reactive programming model. Events are used to trigger actions and communicate between different components of the application. For example, when a certain condition is met, an event can be emitted, and other parts of the application can listen for this event and respond accordingly. This pattern helps in building scalable and modular applications.
- Role-based agent execution framework
The role-based agent execution framework allows for the definition of different roles for agents in the application. Each role has specific permissions and responsibilities, and agents can be assigned to these roles. For example, in a multi - user application, there could be roles like 'admin', 'user', and 'guest', each with different levels of access to resources and functionality.
- Task scheduling and management
The task scheduling and management feature is responsible for organizing and executing tasks in the application. It can handle task dependencies, prioritize tasks, and ensure that tasks are executed in the correct order. For example, in a data processing application, tasks like data ingestion, transformation, and analysis can be scheduled and managed using this framework.
- File system operations and content detection
This feature provides functionality for performing file system operations such as reading, writing, and deleting files. It also includes content detection capabilities, which can identify the type of content in a file, such as text, image, or binary data. For example, it can automatically detect the encoding of a text file or the format of an image file.
- Logging and diagnostics
The logging and diagnostics feature helps in monitoring the application's behavior and troubleshooting issues. It can record important events, errors, and warnings in a log file, which can be used for debugging and auditing purposes. For example, if an error occurs during the execution of a task, the log can provide detailed information about the error, including the stack trace and the values of relevant variables.
- Template rendering and configuration handling
The template rendering and configuration handling feature allows for the use of templates to generate dynamic content and manage application configuration. Templates can be used to generate HTML pages, emails, or other types of documents. Configuration handling ensures that the application can be easily configured with different settings, such as database connections and API keys.
- Type-safe data models for common entities
The type-safe data models for common entities ensure that the data used in the application has a well - defined structure. These models are based on Pydantic, which provides type validation and serialization capabilities. For example, in a user management application, a data model can be defined for the 'User' entity, with attributes like 'name', 'email', and 'password', and Pydantic can be used to validate the input data and ensure that it conforms to the defined model.
- Asynchronous execution utilities
The asynchronous execution utilities enable the application to perform tasks asynchronously, which can improve the performance and responsiveness of the application. For example, in a web application, asynchronous I/O operations can be used to handle multiple requests simultaneously without blocking the main thread. This feature uses Python's asyncio library to implement asynchronous programming.

Built on a hybrid Rust/Python foundation for performance-critical operations.

## 🧩 Key Features

- **Event System**: Reactive architecture with event emitters and listeners
The event system is the core of the event - based architecture. Event emitters are responsible for generating events, and event listeners are registered to listen for specific events. When an event is emitted, all the registered listeners are notified, and they can perform their respective actions. For example, in a game application, an event emitter can be used to emit an event when a player scores a goal, and event listeners can be used to update the scoreboard and play a sound effect.
- **Role Framework**: Agent roles with workflow dispatching capabilities
The role framework defines the different roles that agents can have in the application. Each role has a set of permissions and a workflow associated with it. When an agent is assigned a role, the workflow dispatching capabilities ensure that the agent follows the correct sequence of actions. For example, in a project management application, a 'project manager' role may have a workflow that includes tasks like creating a project plan, assigning tasks to team members, and monitoring progress.
- **Task Engine**: Status-aware task management with dependencies
The task engine is responsible for managing tasks in the application. It keeps track of the status of each task, such as 'pending', 'in progress', or 'completed'. It also handles task dependencies, ensuring that tasks are executed in the correct order. For example, in a software development project, a task to test a module may depend on the completion of the coding task for that module.
- **Toolbox System**: Callable tool registry with rich metadata
The toolbox system maintains a registry of callable tools in the application. Each tool has rich metadata associated with it, such as its name, description, input parameters, and output format. This metadata can be used to discover and use tools in a more efficient way. For example, in a data analysis application, a tool for calculating statistical measures can be registered in the toolbox, and other parts of the application can use this tool by providing the appropriate input parameters.
- **Type Models**: Pydantic-based models for consistent data structures
The type models are based on Pydantic, which provides a way to define and validate data structures. These models ensure that the data used in the application is consistent and conforms to the defined schema. For example, in a financial application, a type model can be used to define the structure of a transaction, including attributes like 'amount', 'date', and 'description', and Pydantic can be used to validate the input data and ensure that it is in the correct format.
- **File Utilities**: Smart file operations with content type detection
The file utilities provide a set of functions for performing file system operations. They include features like content type detection, which can automatically identify the type of content in a file. This can be useful for handling different types of files in a more intelligent way. For example, when reading a file, the file utilities can determine if it is a text file or a binary file and handle it accordingly.
- **Template Engine**: Handlebars-based template rendering system
The template engine uses the Handlebars library to render templates. Templates are used to generate dynamic content by replacing placeholders with actual values. For example, in a web application, a template can be used to generate HTML pages with dynamic content like user names and product information. The Handlebars syntax allows for easy customization and reuse of templates.
- **Language Tools**: Language detection and text processing utilities
The language tools provide capabilities for detecting the language of a text and performing text processing tasks. Language detection can be used to determine the language of a user - input text, which can be useful for providing language - specific services. Text processing utilities include functions for tasks like tokenization, stemming, and part - of - speech tagging, which can be used for natural language processing applications.

## 📁 Structure

```
fabricatio-core/
├── capabilities/     - Core capability definitions
├── decorators.py     - Common function decorators
├── emitter.py        - Event emission and handling
├── fs/               - File system operations
├── journal.py        - Logging infrastructure
├── models/           - Core data models
│   ├── action.py     - Action base classes
│   ├── generic.py    - Base traits (Named, Described, etc.)
│   ├── role.py       - Role definitions
│   ├── task.py       - Task abstractions
│   └── tool.py       - Tool interfaces
├── parser.py         - Text parsing utilities
├── rust.pyi          - Rust extension interfaces
├── utils.py          - General utility functions
└── __init__.py       - Package entry point
```

## 📄 License

MIT – see [LICENSE](LICENSE)

GitHub: [github.com/Whth/fabricatio](https://github.com/Whth/fabricatio)