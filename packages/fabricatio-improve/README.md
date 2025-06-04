# `fabricatio-improve`

A Python library for content review, correction, and improvement in LLM applications.

## 📦 Installation

This package is part of the `fabricatio` monorepo and can be installed as an optional dependency:

```bash
pip install fabricatio[improve]
```

Or install all components:

```bash
pip install fabricatio[full]
```

## 🔍 Overview

Provides tools for:

- Content review and problem detection
The content review and problem detection tool analyzes the input text to identify various issues. It uses natural language processing techniques to check for grammar errors, spelling mistakes, and semantic inconsistencies. For example, it can detect incorrect word usage, missing punctuation, and unclear sentence structures. It also looks for logical problems in the content, such as contradictions or incomplete arguments.
- Problem-solution pair generation
Once problems are detected, this feature generates appropriate solutions. It takes into account the nature of the problem and the context of the text. For grammar and spelling errors, it can suggest the correct words or phrases. For semantic issues, it can propose alternative ways to express the ideas. The solutions are presented in a clear and actionable format, making it easy for users to implement them.
- Text correction and refinement
The text correction and refinement tool applies the generated solutions to the original text. It not only fixes the identified problems but also refines the overall quality of the text. This includes improving the readability, style, and coherence of the content. For example, it can rephrase sentences to make them more concise and clear, and adjust the tone of the text to be more appropriate for the intended audience.
- Improvement prioritization based on severity
This feature prioritizes the detected problems based on their severity. It assigns a severity level to each problem, taking into account factors such as the impact on the meaning of the text, the frequency of occurrence, and the importance of the context. High - severity problems are given higher priority, ensuring that users focus on fixing the most critical issues first.
- Interactive feedback loops with users
The interactive feedback loops allow users to participate in the improvement process. After the initial analysis and solution generation, the tool presents the problems and solutions to the users. Users can then provide their own feedback, accept or reject the proposed solutions, and suggest alternative approaches. This iterative process ensures that the final improved text meets the users' expectations.

Built on top of Fabricatio's agent framework with support for asynchronous execution.

## 🧩 Usage Example

```python
from fabricatio_improve.capabilities.correct import Correct
The `Correct` class is the core component for text correction. It uses a set of pre - trained models and rules to analyze the input text and generate correction suggestions. It can handle different types of text, including articles, reports, and emails.
from fabricatio_improve.models.improve import Improvement
The `Improvement` model represents the overall result of the text improvement process. It contains information about the detected problems, the proposed solutions, and the severity levels of each problem. It also provides methods for accessing and manipulating this information.
from fabricatio_improve.models.problem import Problem, Solution
The `Problem` class represents a detected issue in the text. It includes attributes such as the description of the problem, its location in the text, and its severity level. The `Solution` class represents the proposed solution for a problem. It contains the description of the solution and the steps to implement it.


async def improve_content():
    # Initialize corrector
    corrector = Correct()

    # Sample problematic text
    text = "Ths txt has many speling erors."

    # Get improvement suggestions
    improvement: Improvement = await corrector.correct(text)

    print(f"Found {len(improvement.problem_solutions)} issues:")
    for ps in improvement.problem_solutions:
        print(f"\nProblem: {ps.problem.description}")
        print(f"Location: {ps.problem.location}")
        print(f"Severity: {ps.problem.severity_level}/10")
        print(f"Solution: {ps.solution.description}")
        print(f"Steps: {', '.join(ps.solution.execute_steps)}")
```

## 📁 Structure

```
fabricatio-improve/
├── capabilities/     - Core improvement functionality
│   ├── correct.py    - Text correction capabilities
│   └── review.py     - Content review capabilities
└── models/           - Data models for improvements
    ├── improve.py    - Improvement result model
    ├── kwargs_types.py - Validation argument types
    └── problem.py    - Problem-solution pair definitions
```

## 🔗 Dependencies

Built on top of other Fabricatio modules:

- `fabricatio-core` - Core interfaces and utilities
- `fabricatio-capabilities` - Base capability patterns

## 📄 License

MIT – see [LICENSE](LICENSE)

GitHub: [github.com/Whth/fabricatio](https://github.com/Whth/fabricatio)