# `fabricatio-tagging`

An extension of fabricatio, provide capalability to tag on data.

---

## 📦 Installation

This package is part of the `fabricatio` monorepo and can be installed as an optional dependency using either pip or uv:

```bash
pip install fabricatio[tagging]
# or
uv pip install fabricatio[tagging]
```

For a full installation that includes this package and all other components of `fabricatio`:

```bash
pip install fabricatio[full]
# or
uv pip install fabricatio[full]
```

## 🔍 Overview

Provides essential tools for:

### Data Tagging
This package enables the tagging of data. It can analyze the input data, whether it's text, numerical data, or structured objects, and assign relevant tags based on predefined rules or machine - learning algorithms. For example, in a text document, it can tag entities such as names, locations, and dates.

### Tag Management
It offers features for managing the tags. This includes creating, editing, and deleting tags, as well as organizing them into hierarchies or categories. For instance, users can group related tags together for easier management and retrieval.

### Integration with Fabricatio
The package is designed to work seamlessly with the Fabricatio framework. It can integrate with other modules in the Fabricatio ecosystem, such as the agent framework, to use the tagged data in more complex workflows.

## 🧩 Key Features

- **Intelligent Tagging**: Advanced algorithms to automatically assign semantically relevant tags to data based on content analysis
- **Customizable Tagging Rules**: User-defined rules for flexible tagging strategies tailored to specific use cases and data types
- **Tag Search and Retrieval**: Efficient search functionality for finding data by tags, supporting complex tag combinations and queries
- **Tag Management**: Comprehensive tools for organizing, categorizing, and maintaining tag hierarchies
- **Multi-format Support**: Support for tagging various data types including text, structured objects, and numerical data
- **Agent Integration**: Seamless integration with fabricatio agents for automated tagging workflows

## 🔗 Dependencies
Core dependencies:

- `fabricatio-core` - Core interfaces and utilities

No additional dependencies required.
## 📄 License

MIT – see [LICENSE](LICENSE)

GitHub: [github.com/Whth/fabricatio](https://github.com/Whth/fabricatio)