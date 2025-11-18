# `fabricatio-digest`

A extension for fabricatio, providing capabilities to handle raw requirment, digesting it into a task list.

---

## 📦 Installation

This package is part of the `fabricatio` monorepo and can be installed as an optional dependency using either pip or uv:

```bash
pip install fabricatio[digest]
# or
uv pip install fabricatio[digest]
```

For a full installation that includes this package and all other components of `fabricatio`:

```bash
pip install fabricatio[full]
# or
uv pip install fabricatio[full]
```

## 🔍 Overview

Provides essential tools for:

### Requirement Analysis
This package can analyze raw requirements provided in various formats, such as natural language descriptions or structured documents. It uses natural language processing techniques to understand the requirements and extract key information.

### Task List Generation
Based on the analyzed requirements, it can generate a detailed task list. Each task in the list is well - defined, with clear objectives, dependencies, and estimated time requirements.

### Integration with Fabricatio
It is designed to work seamlessly with the Fabricatio framework. It can communicate with other modules in the Fabricatio ecosystem to ensure that the generated task list is compatible with the overall system.

## 🧩 Key Features

- **Intelligent Parsing**: Advanced natural language processing to understand complex requirements and extract key information
- **Dependency Management**: Automatic identification of task dependencies and proper sequencing for execution
- **Customization**: Configurable rules for task categorization, prioritization, and workflow generation
- **Team Coordination**: Support for multi-agent task distribution and collaborative task execution
- **Validation System**: Built-in validation to ensure generated tasks are actionable and well-defined
- **Template-Driven Generation**: Uses configurable templates for consistent task breakdown and planning

## 🔗 Dependencies
Core dependencies:

- `fabricatio-core` - Core interfaces and utilities

No additional dependencies required.
## 📄 License

MIT – see [LICENSE](LICENSE)

GitHub: [github.com/Whth/fabricatio](https://github.com/Whth/fabricatio)