# `fabricatio-diff`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-diff)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-diff)](https://pypi.org/project/fabricatio-diff/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-diff/week)](https://pepy.tech/projects/fabricatio-diff)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-diff)](https://pepy.tech/projects/fabricatio-diff)
[![Bindings: PyO3](https://img.shields.io/badge/bindings-pyo3-green)](https://github.com/PyO3/pyo3)
[![Build Tool: uv + maturin](https://img.shields.io/badge/built%20with-uv%20%2B%20maturin-orange)](https://github.com/astral-sh/uv)

An extension of fabricatio.

---

## 📦 Installation

This package is part of the `fabricatio` monorepo and can be installed as an optional dependency using either pip or uv:

```bash
pip install fabricatio[diff]
# or
uv pip install fabricatio[diff]
```

For a full installation that includes this package and all other components of `fabricatio`:

```bash
pip install fabricatio[full]
# or
uv pip install fabricatio[full]
```

## 🔍 Overview

Provides intelligent diff-based editing capabilities for fabricatio workflows, enabling precise text modifications through AI-generated search and replace operations. It allows agents to perform targeted edits on source content based on natural language requirements, with configurable match precision for reliable transformations.

## 🧩 Key Features

- **Intelligent Diff Generation**: Generate precise search and replace operations from natural language requirements
- **Precision Control**: Configurable match precision for accurate text modifications
- **Template-Driven Processing**: Uses configurable prompt templates for consistent diff generation
- **Validation System**: Built-in validation to ensure generated diffs are syntactically correct
- **Source Content Analysis**: Analyzes source text to create contextually appropriate edits
- **Rust-Accelerated Performance**: High-performance diff application using Rust extensions

## 🔗 Dependencies

Core dependencies:

- `fabricatio-core` - Core interfaces and utilities

No additional dependencies required.

## 📄 License

MIT – see [LICENSE](LICENSE)

GitHub: [github.com/Whth/fabricatio](https://github.com/Whth/fabricatio)