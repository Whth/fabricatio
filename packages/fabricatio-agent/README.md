# `fabricatio-agent`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-agent)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-agent)](https://pypi.org/project/fabricatio-agent/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-agent/week)](https://pepy.tech/projects/fabricatio-agent)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-agent)](https://pepy.tech/projects/fabricatio-agent)
[![Bindings: PyO3](https://img.shields.io/badge/bindings-pyo3-green)](https://github.com/PyO3/pyo3)
[![Build Tool: uv + maturin](https://img.shields.io/badge/built%20with-uv%20%2B%20maturin-orange)](https://github.com/astral-sh/uv)



An extension of fabricatio.

---

## 📦 Installation


This package is part of the `fabricatio` monorepo and can be installed as an optional dependency:

```bash
pip install fabricatio[agent]

# or with uv
# uv pip install fabricatio[agent]
```

Or install `fabricatio-diff` along with all other components of `fabricatio`:

```bash
pip install fabricatio[full]

# or with uv
# uv pip install fabricatio[full]
```
## 🔍 Overview

Provides a comprehensive AI agent framework that integrates multiple capabilities for autonomous task fulfillment. The agent combines thinking, memory, team cooperation, and various specialized capabilities to process and execute complex requests, making it a central orchestrator in the fabricatio ecosystem for intelligent workflow automation.
## 🧩 Key Features

- **Multi-Capability Integration**: Combines thinking, memory, judgment, task dispatching, and team cooperation capabilities
- **Autonomous Task Fulfillment**: Processes requests through sequential thinking and task decomposition
- **Memory-Augmented Processing**: Recalls relevant information to enhance decision making and context awareness
- **Team Collaboration**: Supports cooperative workflows with multiple specialized agents
- **Configurable Behavior**: Customizable settings for thinking mode, memory usage, and capability checking
- **Template-Driven Execution**: Uses configurable prompt templates for consistent and adaptable behavior


## 🔗 Dependencies
Core dependencies:

- `fabricatio-core` - Core interfaces and utilities
- `fabricatio-digest` - Request digestion and task planning
- `fabricatio-memory` - Memory management and recall
- `fabricatio-improve` - Content improvement capabilities
- `fabricatio-rule` - Rule-based content processing
- `fabricatio-judge` - Advanced judgment and evaluation
- `fabricatio-capabilities` - Base capability patterns
- `fabricatio-diff` - Difference editing operations
- `fabricatio-thinking` - Sequential thinking processes
- `fabricatio-question` - Interactive questioning
- `fabricatio-tool` - Tool handling and execution
- `fabricatio-team` - Team cooperation mechanisms
- `fabricatio-capable` - Capability assessment
## 📄 License

This project is licensed under the MIT License.