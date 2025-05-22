# `fabricatio-core`

A foundational Python library providing core components for building LLM-driven applications using an event-based agent
structure.

## 📦 Installation

This package is part of the `fabricatio` monorepo and is available as a single package:

```bash
pip install fabricatio
```

## 🔍 Overview

Provides essential tools for:

- Event-based architecture patterns
- Role-based agent execution framework
- Task scheduling and management
- File system operations and content detection
- Logging and diagnostics
- Template rendering and configuration handling
- Type-safe data models for common entities
- Asynchronous execution utilities

Built on a hybrid Rust/Python foundation for performance-critical operations.

## 🧩 Key Features

- **Event System**: Reactive architecture with event emitters and listeners
- **Role Framework**: Agent roles with workflow dispatching capabilities
- **Task Engine**: Status-aware task management with dependencies
- **Toolbox System**: Callable tool registry with rich metadata
- **Type Models**: Pydantic-based models for consistent data structures
- **File Utilities**: Smart file operations with content type detection
- **Template Engine**: Handlebars-based template rendering system
- **Language Tools**: Language detection and text processing utilities

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