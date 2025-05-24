# `fabricatio-capabilities`

A foundational Python library providing core capabilities for building LLM-driven applications using an event-based
agent structure.

## 📦 Installation

This package is part of the `fabricatio` monorepo and can be installed as an optional dependency:

```bash
pip install fabricatio[capabilities]
```

Or install all components:

```bash
pip install fabricatio[full]
```

## 🔍 Overview

Provides essential tools for:

- Content extraction and information gathering
- Proposal generation and evaluation
- Task execution and management
- Rating and quality assessment
- Structured data modeling for capabilities

Built on top of Fabricatio's core framework with support for asynchronous execution and Rust extensions.

## 🧩 Key Features

- **Extract Capability**: Extract structured information from unstructured text
- **Propose Capability**: Generate proposals and suggestions based on context
- **Task Management**: Execute and manage complex workflows
- **Rating System**: Evaluate content quality and effectiveness
- **Type Models**: Pydantic-based models for consistent data structures

## 📁 Structure

```
fabricatio-capabilities/
├── capabilities/     - Core capability implementations
│   ├── extract.py    - Content extraction capabilities
│   ├── propose.py    - Proposal generation capabilities
│   ├── rating.py     - Content rating capabilities
│   └── task.py       - Task execution capabilities
└── models/           - Data models for capabilities
    ├── generic.py    - Base models and common definitions
    └── kwargs_types.py - Validation argument types
```

## 🔗 Dependencies

Core dependencies:

- `fabricatio-core` - Core interfaces and utilities

## 📄 License

MIT – see [LICENSE](LICENSE)

GitHub: [github.com/Whth/fabricatio](https://github.com/Whth/fabricatio)