# `fabricatio-capabilities`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-capabilities)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-capabilities)](https://pypi.org/project/fabricatio-capabilities/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-capabilities/week)](https://pepy.tech/projects/fabricatio-capabilities)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-capabilities)](https://pepy.tech/projects/fabricatio-capabilities)
[![Build Tool: uv](https://img.shields.io/badge/built%20with-uv-orange)](https://github.com/astral-sh/uv)

A foundational Python library providing core capabilities for building LLM-driven applications using an event-based
agent structure.

## 📦 Installation

This package is part of the `fabricatio` monorepo and can be installed as an optional dependency using either pip or uv:

```bash
pip install fabricatio[capabilities]
# or
uv pip install fabricatio[capabilities]
```

For a full installation that includes this package and all other components of `fabricatio`:

```bash
pip install fabricatio[full]
# or
uv pip install fabricatio[full]
```

## 🔍 Overview

Provides core capabilities for content extraction, proposal generation, task execution, and quality assessment in
LLM-driven applications. The package enables structured information gathering, intelligent decision-making, and
comprehensive workflow management with built-in evaluation systems.

## 🧩 Key Features

- **Extract Capability**: Extract structured information from unstructured text using advanced NLP techniques
- **Propose Capability**: Generate proposals and suggestions based on context and available data
- **Task Management**: Execute and manage complex workflows with dependencies and status tracking
- **Rating System**: Evaluate content quality and effectiveness using predefined metrics
- **Type Models**: Pydantic-based models for consistent data structures and validation
- **Async Support**: Built-in asynchronous execution with Rust extensions for performance

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

MIT – see [LICENSE](../../LICENSE)

