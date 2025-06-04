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

...



## 🧩 Key Features

### Long - Term Memory Storage
The long - term memory storage feature allows the LLM to store information over an extended period. It can save important data such as user profiles, historical conversations, and domain knowledge. This information can be retrieved later to provide more personalized and context - aware responses.

### Short - Term Memory Buffer
The short - term memory buffer is used to store the most recent information. It helps the LLM to maintain a context for the current conversation and respond more coherently. For example, it can remember the last few messages in a chat session.

### Memory Retrieval Mechanisms
The package provides efficient memory retrieval mechanisms. It can search through the stored memory based on keywords, context, or other criteria to find the relevant information. This ensures that the LLM can access the necessary data quickly and accurately.

...


## 🔗 Dependencies

Core dependencies:

- `fabricatio-core` - Core interfaces and utilities
This dependency provides the fundamental building blocks for the Fabricatio framework. It includes interfaces for task management, event handling, and data models. The `fabricatio-memory` package uses these interfaces to interact with other modules in the Fabricatio ecosystem and manage the memory effectively.
...

## 📄 License

MIT – see [LICENSE](LICENSE)

GitHub: [github.com/Whth/fabricatio](https://github.com/Whth/fabricatio)