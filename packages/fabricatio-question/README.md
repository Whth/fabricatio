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

## 🧩 Key Features

- **Intelligent Question Generation**: Advanced algorithms to create relevant, context-aware questions based on task requirements and current state
- **Response Analysis**: Extract and process user responses to enhance planning and decision-making capabilities
- **Context Awareness**: Maintain conversation context to ask increasingly targeted and meaningful questions
- **Interactive Planning**: Enable collaborative planning through strategic questioning and information gathering
- **Dynamic Adaptation**: Adjust questioning strategy based on evolving task requirements and user responses
- **Integration Support**: Seamless communication with other fabricatio modules for enhanced workflow orchestration

## 🔗 Dependencies
Core dependencies:

- `fabricatio-core` - Core interfaces and utilities

No additional dependencies required.
## 📄 License

MIT – see [LICENSE](LICENSE)

GitHub: [github.com/Whth/fabricatio](https://github.com/Whth/fabricatio)