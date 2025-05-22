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
- Problem-solution pair generation
- Text correction and refinement
- Improvement prioritization based on severity
- Interactive feedback loops with users

Built on top of Fabricatio's agent framework with support for asynchronous execution.

## 🧩 Usage Example

```python
from fabricatio_improve.capabilities.correct import Correct
from fabricatio_improve.models.improve import Improvement
from fabricatio_improve.models.problem import Problem, Solution


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