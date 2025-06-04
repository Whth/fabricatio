# `fabricatio-digest`

A extension for fabricatio, providing capabilities to handle raw requirment, digesting it into a task list.

---

## 📦 Installation

This package is part of the `fabricatio` monorepo and can be installed as an optional dependency:

```bash
pip install fabricatio[digest]
```

Or install all components:

```bash
pip install fabricatio[full]
```

## 🔍 Overview

Provides essential tools for:

### Requirement Analysis
This package can analyze raw requirements provided in various formats, such as natural language descriptions or structured documents. It uses natural language processing techniques to understand the requirements and extract key information.

### Task List Generation
Based on the analyzed requirements, it can generate a detailed task list. Each task in the list is well - defined, with clear objectives, dependencies, and estimated time requirements.

### Integration with Fabricatio
It is designed to work seamlessly with the Fabricatio framework. It can communicate with other modules in the Fabricatio ecosystem to ensure that the generated task list is compatible with the overall system.

...



## 🧩 Key Features

### Intelligent Parsing
The package uses advanced parsing algorithms to understand the semantics of the raw requirements. It can handle complex sentences and extract relevant information accurately.

### Dependency Management
It can identify dependencies between tasks in the generated task list. This helps in scheduling the tasks in the correct order and ensuring that all prerequisites are met before a task is executed.

### Customization
Users can customize the task generation process according to their specific needs. For example, they can define their own rules for task categorization and prioritization.

...


## 🔗 Dependencies

Core dependencies:

- `fabricatio-core` - Core interfaces and utilities
This dependency provides the fundamental building blocks for the Fabricatio framework. It includes interfaces for task management, event handling, and data models. The `fabricatio-digest` package uses these interfaces to interact with other modules in the Fabricatio ecosystem and ensure the smooth generation of task lists.
  ...

## 📄 License

MIT – see [LICENSE](LICENSE)

GitHub: [github.com/Whth/fabricatio](https://github.com/Whth/fabricatio)