# `fabricatio-thinking`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-thinking)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-thinking)](https://pypi.org/project/fabricatio-thinking/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-thinking/week)](https://pepy.tech/projects/fabricatio-thinking)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-thinking)](https://pepy.tech/projects/fabricatio-thinking)
[![Bindings: PyO3](https://img.shields.io/badge/bindings-pyo3-green)](https://github.com/PyO3/pyo3)
[![Build Tool: uv + maturin](https://img.shields.io/badge/built%20with-uv%20%2B%20maturin-orange)](https://github.com/astral-sh/uv)



An extension of fabricatio.

---

## 📦 Installation


This package is part of the `fabricatio` monorepo and can be installed as an optional dependency:

```bash
pip install fabricatio[thinking]

# or with uv
# uv pip install fabricatio[thinking]
```

Or install `fabricatio-diff` along with all other components of `fabricatio`:

```bash
pip install fabricatio[full]

# or with uv
# uv pip install fabricatio[full]
```
## 🔍 Overview

Provides structured thinking and reasoning capabilities for fabricatio agents, implementing a version-controlled thought process that enables iterative analysis, revision, and branching of ideas. It supports complex problem-solving through systematic thought progression with built-in revision and branching mechanisms.
## 🧩 Key Features

- **Sequential Thinking Process**: Step-by-step reasoning with version control for thought progression
- **Thought Revision**: Ability to revise and improve previous thoughts for better outcomes
- **Branching Support**: Create and manage thought branches for exploring alternative approaches
- **Version Control System**: Built-in VCS for tracking thought evolution and managing complex reasoning
- **Configurable Depth**: Adjustable maximum steps for thinking processes with automatic termination
- **Structured Thought Modeling**: Pydantic-based models for consistent thought representation and validation


## 🔗 Dependencies
Core dependencies:

- `fabricatio-core` - Core interfaces and utilities

No additional dependencies required.
## 📄 License

This project is licensed under the MIT License.