# `fabricatio-question`

An extension of fabricatio, which provide the capability to question user to make better planning and etc..

---

## 📦 Installation

This package is part of the `fabricatio` monorepo and can be installed as an optional dependency:

```bash
pip install fabricatio[question]
```

Or install all components:

```bash
pip install fabricatio[full]
```

## 🔍 Overview

Provides essential tools for:

### User Questioning
This package enables the system to ask relevant questions to the user. It analyzes the current state of the task or conversation and determines what information is needed to make better planning decisions. For example, in a project planning scenario, it might ask about the project's budget, timeline, or specific requirements.

### Information Gathering
By asking questions, it can gather crucial information from the user. This information is then used to improve the accuracy and effectiveness of the planning process. It can handle different types of responses and integrate the collected data into the overall system.

### Integration with Fabricatio
It is designed to work seamlessly with the Fabricatio framework. It can communicate with other modules in the Fabricatio ecosystem to ensure that the questions asked are relevant to the overall context and that the gathered information is used appropriately.

...



## 🧩 Key Features

### Intelligent Question Generation
The package uses advanced algorithms to generate intelligent questions. It takes into account the current context, the user's previous responses, and the overall goal of the task. This ensures that the questions are relevant, clear, and likely to elicit useful information.

### Response Analysis
It can analyze the user's responses to the questions. It can extract relevant information from the responses, understand the user's intentions, and use this information to guide the next steps in the planning process.

### Context Awareness
The system is context - aware, meaning it can adapt the questions based on the current state of the conversation or task. It can remember previous questions and responses, and use this knowledge to ask more targeted and meaningful questions.

...


## 🔗 Dependencies

Core dependencies:

- `fabricatio-core` - Core interfaces and utilities
This dependency provides the fundamental building blocks for the Fabricatio framework. It includes interfaces for task management, event handling, and data models. The `fabricatio-question` package uses these interfaces to interact with other modules in the Fabricatio ecosystem and ensure that the questioning process is integrated with the overall system.
  ...

## 📄 License

MIT – see [LICENSE](LICENSE)

GitHub: [github.com/Whth/fabricatio](https://github.com/Whth/fabricatio)