# `fabricatio-memory`

An extension of fabricatio aiming to extend the context LLM could handle.

---

## 📦 Installation

This package is part of the `fabricatio` monorepo and can be installed as an optional dependency using either pip or uv:

```bash
pip install fabricatio[memory]
# or
uv pip install fabricatio[memory]
```

For a full installation that includes this package and all other components of `fabricatio`:

```bash
pip install fabricatio[full]
# or
uv pip install fabricatio[full]
```

## 🔍 Overview

Provides comprehensive memory management capabilities for fabricatio agents, enabling extended context handling and intelligent information retrieval. The package combines long-term and short-term memory systems with agent integration for enhanced decision-making and context-aware processing.

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