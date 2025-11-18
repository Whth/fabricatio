# `fabricatio-checkpoint`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-checkpoint)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-checkpoint)](https://pypi.org/project/fabricatio-checkpoint/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-checkpoint/week)](https://pepy.tech/projects/fabricatio-checkpoint)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-checkpoint)](https://pepy.tech/projects/fabricatio-checkpoint)
[![Bindings: PyO3](https://img.shields.io/badge/bindings-pyo3-green)](https://github.com/PyO3/pyo3)
[![Build Tool: uv + maturin](https://img.shields.io/badge/built%20with-uv%20%2B%20maturin-orange)](https://github.com/astral-sh/uv)



An extension of fabricatio.

---

## 📦 Installation


This package is part of the `fabricatio` monorepo and can be installed as an optional dependency:

```bash
pip install fabricatio[checkpoint]

# or with uv
# uv pip install fabricatio[checkpoint]
```

Or install `fabricatio-diff` along with all other components of `fabricatio`:

```bash
pip install fabricatio[full]

# or with uv
# uv pip install fabricatio[full]
```
## 🔍 Overview

Provides version control and checkpointing capabilities for fabricatio workflows, allowing users to save, rollback, and manage states of their worktrees using a git-like shadow repository system. It enables seamless state management during complex AI-driven processes, supporting both individual file rollbacks and full worktree resets to maintain workflow consistency and enable experimentation.
## 🧩 Key Features

- **Checkpoint Saving**: Save current worktree state with custom messages to preserve progress at any point
- **Selective Rollback**: Rollback individual files to previous checkpoints without affecting other files
- **Full Reset**: Reset entire worktree to any saved checkpoint state for complete state restoration
- **Diff Tracking**: Retrieve file differences between checkpoints to understand changes over time
- **Shadow Repository Management**: Automatic handling of git-like shadow repositories with configurable caching
- **Workflow Integration**: Seamless integration with fabricatio agents for reliable state management in AI workflows


## 🔗 Dependencies
Core dependencies:

- `fabricatio-core` - Core interfaces and utilities

No additional dependencies required.
## 📄 License

This project is licensed under the MIT License.