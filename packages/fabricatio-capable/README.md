# `fabricatio-capable`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-capable)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-capable)](https://pypi.org/project/fabricatio-capable/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-capable/week)](https://pepy.tech/projects/fabricatio-capable)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-capable)](https://pepy.tech/projects/fabricatio-capable)
[![Build Tool: uv](https://img.shields.io/badge/built%20with-uv-orange)](https://github.com/astral-sh/uv)


An extension of fabricatio.

---

## 📦 Installation

This package is part of the `fabricatio` monorepo and can be installed as an optional dependency:

```bash
pip install fabricatio[capable]

# or with uv
# uv pip install fabricatio[capable]
```

Or install `fabricatio-diff` along with all other components of `fabricatio`:

```bash
pip install fabricatio[full]

# or with uv
# uv pip install fabricatio[full]
```
## 🔍 Overview

Provides capability assessment and validation framework for fabricatio agents, enabling intelligent evaluation of whether specific tasks can be performed using available tools and context. It integrates judgment capabilities with tool usage assessment to determine agent feasibility for complex requests.
## 🧩 Key Features

- **Capability Assessment**: Evaluate whether agents can handle specific requests based on available tools and context
- **Intelligent Judgment**: Use advanced judgment mechanisms to assess task feasibility and requirements
- **Tool Integration**: Seamlessly work with toolboxes to validate capability against available resources
- **Batch Processing**: Support both single and batch capability assessments for multiple requests
- **Template-Driven Evaluation**: Configurable assessment templates for consistent capability evaluation
- **Context-Aware Validation**: Leverage briefing and context information for accurate capability determination


## 🔗 Dependencies
Core dependencies:

- `fabricatio-core` - Core interfaces and utilities
- `fabricatio-tool` - Tool usage and toolbox management
- `fabricatio-judge` - Advanced judgment and evaluation capabilities

No additional dependencies required.
## 📄 License

This project is licensed under the MIT License.