# `fabricatio-capabilities`

A foundational Python library providing core capabilities for building LLM-driven applications using an event-based
agent structure.

## 📦 Installation

This package is part of the `fabricatio` monorepo and can be installed as an optional dependency using either pip or uv:

```bash
pip install fabricatio[capabilities]
# or
uv pip install fabricatio[capabilities]
```

For a full installation that includes this package and all other components of `fabricatio`:

```bash
pip install fabricatio[full]
# or
uv pip install fabricatio[full]
```

## 🔍 Overview

Provides essential tools for:

- Content extraction and information gathering
This feature allows the extraction of structured information from unstructured text sources. For example, it can parse through long documents and extract key facts, figures, and relationships. It uses natural language processing techniques to identify entities, such as names, dates, and locations, and can also extract semantic information like the main ideas and arguments in a text.
- Proposal generation and evaluation
The proposal generation feature takes into account the context and available data to generate relevant proposals. For instance, in a business context, it can generate project proposals based on market research and company goals. The evaluation part assesses the feasibility and potential success of these proposals using predefined criteria, such as cost - benefit analysis and risk assessment.
- Task execution and management
This feature enables the execution and management of complex workflows. It can break down large tasks into smaller subtasks, assign them to different agents or resources, and monitor their progress. For example, in a software development project, it can manage the tasks of coding, testing, and deployment, ensuring that each step is completed in a timely manner.
- Rating and quality assessment
The rating and quality assessment feature evaluates the quality and effectiveness of content or processes. It can assign ratings to different items based on predefined metrics, such as accuracy, completeness, and relevance. In a content - based application, it can rate articles or documents based on their information value and readability.
- Structured data modeling for capabilities
This feature is used to create structured data models for representing capabilities. It defines the attributes and relationships of different capabilities, making it easier to manage and analyze them. For example, in a manufacturing context, it can model the capabilities of different machines, including their production capacity, speed, and accuracy.

Built on top of Fabricatio's core framework with support for asynchronous execution and Rust extensions.

## 🧩 Key Features

- **Extract Capability**: Extract structured information from unstructured text
The extract capability uses advanced natural language processing algorithms to analyze unstructured text. It first identifies key entities and then extracts relevant information based on predefined patterns. For example, in a news article, it can extract the names of people involved, the location of an event, and the main points of the story.
- **Propose Capability**: Generate proposals and suggestions based on context
The propose capability analyzes the available data and context to generate relevant proposals. It can take into account factors such as user preferences, historical data, and current trends. For example, in a marketing campaign, it can propose different strategies based on the target audience and market conditions.
- **Task Management**: Execute and manage complex workflows
The task management feature uses a workflow engine to manage the execution of tasks. It can handle dependencies between tasks, schedule them based on resource availability, and provide real - time status updates. For example, in a project management application, it can manage the tasks of multiple teams, ensuring that the project is completed on time.
- **Rating System**: Evaluate content quality and effectiveness
The rating system uses a set of predefined metrics to evaluate the quality and effectiveness of content. It can consider factors such as accuracy, relevance, and readability. For example, in an e - learning platform, it can rate courses based on the quality of the content and the feedback from students.
- **Type Models**: Pydantic-based models for consistent data structures
The type models are based on Pydantic, which is a data validation library in Python. These models ensure that the data used in the application has a consistent structure. For example, in a data - driven application, it can define the structure of input and output data, making it easier to process and analyze.

## 📁 Structure

```
fabricatio-capabilities/
├── capabilities/     - Core capability implementations
│   ├── extract.py    - Content extraction capabilities
│   ├── propose.py    - Proposal generation capabilities
│   ├── rating.py     - Content rating capabilities
│   └── task.py       - Task execution capabilities
└── models/           - Data models for capabilities
    ├── generic.py    - Base models and common definitions
    └── kwargs_types.py - Validation argument types
```

## 🔗 Dependencies

Core dependencies:

- `fabricatio-core` - Core interfaces and utilities

## 📄 License

MIT – see [LICENSE](LICENSE)

GitHub: [github.com/Whth/fabricatio](https://github.com/Whth/fabricatio)