# `fabricatio-judge`

A Python module for evidence-based decision making in LLM applications.

## 📦 Installation

This package is part of the `fabricatio` monorepo and can be installed as an optional dependency:

```bash
pip install fabricatio[judge]
```

Or install all components:

```bash
pip install fabricatio[full]
```

## 🔍 Overview

Provides the `AdvancedJudge` class for structured judgment tasks, using collected evidence to determine a final boolean
The `AdvancedJudge` class is the core of this module. It uses a structured approach to collect and analyze evidence. It can handle different types of evidence, such as text, numerical data, and expert opinions. The evidence is then used to make a binary decision (true or false) based on predefined rules and algorithms.
verdict.

### Key Features:

- Asynchronous judgment execution
Asynchronous judgment execution allows the module to perform multiple judgment tasks simultaneously without blocking the main thread. This is particularly useful in applications where real - time responses are required. For example, in a chatbot application, the judge can evaluate multiple user queries concurrently, improving the overall performance and responsiveness.
- Evidence tracking (affirmative & denying)
The evidence tracking feature keeps a record of both affirmative and denying evidence. Affirmative evidence supports the positive outcome of the judgment, while denying evidence supports the negative outcome. This helps in making more informed decisions and provides transparency in the judgment process. For example, in a legal application, the judge can track the evidence presented by both the prosecution and the defense.
- Integration with Fabricatio agent framework
The integration with the Fabricatio agent framework allows the `AdvancedJudge` class to communicate and collaborate with other agents in the system. It can receive evidence from other agents, share its judgment results, and participate in complex workflows. This enables the creation of more sophisticated and intelligent applications. For example, in a multi - agent system for project management, the judge can interact with agents responsible for task management and resource allocation.
- Extensible for custom logic
The module is designed to be extensible, allowing users to implement custom logic. Users can subclass the `AdvancedJudge` class and override its methods to add their own rules and algorithms. This provides flexibility and adaptability to different application requirements. For example, in a domain - specific application, users can define their own evidence evaluation criteria and decision - making processes.

## 🧩 Usage

```python
from fabricatio.capabilities import AdvancedJudge
The `AdvancedJudge` class is imported from the `fabricatio.capabilities` module. It provides a set of methods for evidence collection, analysis, and judgment. To use it, you can create an instance of the class and call its methods to perform judgment tasks.
from fabricatio.models import JudgeMent
The `JudgeMent` model represents the result of a judgment task. It contains attributes such as the final verdict (a boolean value) and additional information about the judgment process, such as the evidence used and the decision - making steps.


class MyJudge(AdvancedJudge):
    pass  # Implement custom logic if needed


async def evaluate():
    judge = MyJudge()
    result: JudgeMent = await judge.evidently_judge("Is water wet?")
    The `evidently_judge` method is used to perform a judgment task. It takes a question or a statement as input and returns a `JudgeMent` object. In this example, the judge will collect evidence related to the question "Is water wet?" and make a decision based on the available evidence.
    print(f"Verdict: {result.final_judgement}")
```

## 📁 Structure

```
fabricatio-judge/
├── capabilities/     - Judgment logic (`AdvancedJudge`)
└── models/           - Judgment output model (`JudgeMent`)
```

## 📄 License

MIT – see [LICENSE](LICENSE)

GitHub: [github.com/Whth/fabricatio](https://github.com/Whth/fabricatio)

