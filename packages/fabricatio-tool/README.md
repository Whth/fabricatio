# `fabricatio-tool`

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-tool)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-tool)](https://pypi.org/project/fabricatio-tool/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-tool/week)](https://pepy.tech/projects/fabricatio-tool)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-tool)](https://pepy.tech/projects/fabricatio-tool)
[![Bindings: PyO3](https://img.shields.io/badge/bindings-pyo3-green)](https://github.com/PyO3/pyo3)
[![Build Tool: uv + maturin](https://img.shields.io/badge/built%20with-uv%20%2B%20maturin-orange)](https://github.com/astral-sh/uv)

An extension of fabricatio, which brings up the capability to use tools with native Python.

---

## 📦 Installation

This package is part of the `fabricatio` monorepo and can be installed as an optional dependency using either pip or uv:

```bash
pip install fabricatio[tool]
# or
uv pip install fabricatio[tool]
```

For a full installation that includes this package and all other components of `fabricatio`:

```bash
pip install fabricatio[full]
# or
uv pip install fabricatio[full]
```

## 🔍 Overview

Provides native tool execution capabilities for fabricatio agents, enabling seamless integration and usage of
Python-based tools within LLM workflows. It supports dynamic tool discovery, code generation for tool usage, and
execution of complex tool chains with result collection and management.

## 🧩 Key Features

- **Dynamic Tool Discovery**: Automatic gathering and selection of relevant tools based on task requirements
- **Code Generation**: AI-powered generation of Python code for tool usage and execution
- **Tool Chain Execution**: Support for executing sequences of tools with data flow between operations
- **Result Collection**: Structured collection and management of tool execution results
- **Fine-Grained Control**: Configurable tool selection with box and tool-level filtering options
- **Error Handling**: Robust error handling and validation for tool execution workflows

## 🔗 Dependencies

Core dependencies:

- `fabricatio-core` - Core interfaces and utilities

No additional dependencies required.

## 📄 License

MIT – see [LICENSE](../../LICENSE)

