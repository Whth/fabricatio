# `fabricatio-mock`

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-mock)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-mock)](https://pypi.org/project/fabricatio-mock/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-mock/week)](https://pepy.tech/projects/fabricatio-mock)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-mock)](https://pepy.tech/projects/fabricatio-mock)
[![Build Tool: uv](https://img.shields.io/badge/built%20with-uv-orange)](https://github.com/astral-sh/uv)


An extension of fabricatio, which provides mocks and other test utils..

---

## 📦 Installation

This package is part of the `fabricatio` monorepo and can be installed as an optional dependency:

```bash
pip install fabricatio[mock]
```

Or install all components:

```bash
pip install fabricatio[full]
```
## 🔍 Overview

Provides comprehensive testing utilities and mock implementations for fabricatio applications, enabling reliable unit testing and integration testing of AI-powered workflows. It offers mock roles, test fixtures, and utilities to simulate LLM interactions and agent behaviors without external dependencies.
## 🧩 Key Features

- **Mock LLM Roles**: Pre-configured test roles with mock LLM capabilities for isolated testing
- **Test Fixtures**: Ready-to-use fixtures for common testing scenarios in fabricatio applications
- **LLM Simulation**: Mock implementations of LLM interactions with configurable responses
- **Agent Testing**: Utilities for testing fabricatio agents without real LLM API calls
- **Integration Testing**: Support for testing complex workflows and agent interactions
- **Test Data Generation**: Tools for generating realistic test data and scenarios


## 🔗 Dependencies
Core dependencies:

- `fabricatio-core` - Core interfaces and utilities

No additional dependencies required.
## 📄 License

MIT – see [LICENSE](LICENSE)

GitHub: [github.com/Whth/fabricatio](https://github.com/Whth/fabricatio)