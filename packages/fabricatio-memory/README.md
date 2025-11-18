# `fabricatio-memory`

An Extension of fabricatio aiming to extend the context llm could handle..

---

## 📦 Installation

This package is part of the `fabricatio` monorepo and can be installed as an optional dependency:

```bash
pip install fabricatio[memory]
```

Or install all components:

```bash
pip install fabricatio[full]
```

## 🔍 Overview

Provides essential tools for:

### Context Expansion
This package enables the extension of the context that an LLM can handle. It does this by storing and retrieving relevant information from a memory system. For example, it can keep track of previous conversations, user preferences, and domain - specific knowledge, allowing the LLM to have a more comprehensive understanding of the current input.

### Memory Management
It offers features for managing the memory used by the LLM. This includes tasks such as memory allocation, deallocation, and optimization. It ensures that the memory is used efficiently and that the LLM can access the necessary information quickly.

### Integration with Fabricatio
The package is designed to work seamlessly with the Fabricatio framework. It can leverage the capabilities of Fabricatio's agent framework to manage the memory in a more intelligent way and integrate with other modules in the ecosystem.

## 🧩 Key Features

- **Long-Term Memory Storage**: Persistent storage of important information including user profiles, historical conversations, and domain knowledge for personalized responses
- **Short-Term Memory Buffer**: Maintains recent context and conversation history to ensure coherent and contextually appropriate responses
- **Intelligent Memory Retrieval**: Advanced search mechanisms to find relevant information based on keywords, context, and semantic similarity
- **Memory Optimization**: Efficient memory allocation and cleanup to maintain performance while maximizing context retention
- **Agent Integration**: Seamless integration with fabricatio agents for memory-augmented decision making and context awareness
- **Scalable Architecture**: Supports various storage backends and can handle large volumes of memory data

## 🔗 Dependencies
Core dependencies:

- `fabricatio-core` - Core interfaces and utilities

No additional dependencies required.
## 📄 License

MIT – see [LICENSE](LICENSE)

GitHub: [github.com/Whth/fabricatio](https://github.com/Whth/fabricatio)