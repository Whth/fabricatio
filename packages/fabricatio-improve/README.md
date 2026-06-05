# `fabricatio-improve`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-improve)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-improve)](https://pypi.org/project/fabricatio-improve/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-improve/week)](https://pepy.tech/projects/fabricatio-improve)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-improve)](https://pepy.tech/projects/fabricatio-improve)
[![Build Tool: uv](https://img.shields.io/badge/built%20with-uv-orange)](https://github.com/astral-sh/uv)

Content review, correction, and improvement for LLM applications built on Fabricatio's agent framework.

## Installation

```bash
pip install fabricatio[improve]
# or
uv pip install fabricatio[improve]
```

For a full installation with all Fabricatio components:

```bash
pip install fabricatio[full]
# or
uv pip install fabricatio[full]
```

## Overview

`fabricatio-improve` provides two capability classes that integrate into the Fabricatio agent architecture:

- **Review** — analyzes text, tasks, or objects to identify problems and propose solutions using LLM-driven evaluation against configurable criteria.
- **Correct** — applies reviewed problems and solutions to fix troubled text or objects, including best-solution selection and template-based correction.

## Key Classes

### Capabilities

| Class | Base Classes | Description |
|-------|-------------|-------------|
| `Review` | `Rating`, `Propose` | Reviews content against a topic and criteria, producing an `Improvement` with identified problems and proposed solutions. |
| `Correct` | `Rating` | Decides best solutions from review results, then applies fixes to troubled objects or strings using templates. |

### Models

| Model | Description |
|-------|-------------|
| `Improvement` | Result of a review — holds `focused_on` topic and a list of `ProblemSolutions`. Supports interactive supervisor filtering and gathering multiple improvements. |
| `Problem` | A detected issue with `description` (cause), `severity_level` (0-10), and `location`. |
| `Solution` | A proposed fix with `description` (mechanism), `execute_steps`, `feasibility_level`, and `impact_level`. |
| `ProblemSolutions` | A pair of one `Problem` with its candidate `Solution` list. Supports deciding the final solution and interactive editing. |

### KWArgs Types

| Type | Used By | Description |
|------|---------|-------------|
| `ReviewKwargs` | `Review` | Review parameters including required `topic`, optional `criteria` set, and `rating_manual` dict. |
| `CorrectKwargs` | `Correct` | Correction parameters including the `improvement` to apply. |

### Configuration

`ImproveConfig` (loaded via `fabricatio_core.CONFIG`) exposes configurable template names:

- `review_string_template` — template for review operations
- `fix_troubled_string_template` — template for string correction
- `fix_troubled_obj_template` — template for object correction

## Usage

### Review

```python
from fabricatio_improve.capabilities.review import Review


class MyAgent(Review):
    """An agent that can review content."""


async def review_content():
    agent = MyAgent()
    improvement = await agent.review_string(
        "The quick brown fox jump over the lazy dog.",
        topic="grammar",
        criteria={"subject-verb agreement", "spelling"},
        rating_manual={"spelling": "no typos: 10, minor typos: 5, many typos: 0"},
    )

    for ps in improvement.problem_solutions:
        print(f"Problem: {ps.problem.description} (severity: {ps.problem.severity_level}/10)")
        for sol in ps.solutions:
            print(f"  Solution: {sol.description}")
            print(f"  Steps: {', '.join(sol.execute_steps)}")
```

### Correct

```python
from fabricatio_improve.capabilities.correct import Correct
from fabricatio_improve.models.improve import Improvement
from fabricatio_improve.models.problem import Problem, ProblemSolutions, Solution


class MyCorrector(Correct):
    """An agent that can correct content."""


async def correct_content():
    corrector = MyCorrector()

    # Build an improvement from prior review
    problem = Problem(
        name="subject-verb agreement",
        cause="'jump' should be 'jumps' for third-person singular",
        severity_level=7,
        location="line 1",
    )
    solution = Solution(
        name="fix verb",
        mechanism="Change 'jump' to 'jumps'",
        execute_steps=["locate the verb 'jump'", "replace with 'jumps'"],
        feasibility_level=10,
        impact_level=5,
    )
    improvement = Improvement(
        focused_on="grammar",
        problem_solutions=[ProblemSolutions(problem=problem, solutions=[solution])],
    )

    corrected = await corrector.correct_string(
        "The quick brown fox jump over the lazy dog.",
        improvement,
    )
    print(corrected)
```

## Structure

```
fabricatio-improve/
├── capabilities/
│   ├── correct.py       — Correct capability (apply fixes to content)
│   └── review.py        — Review capability (detect problems, propose solutions)
└── models/
    ├── improve.py        — Improvement result model
    ├── problem.py        — Problem, Solution, ProblemSolutions models
    └── kwargs_types.py   — KWArgs types for correction and review
```

## Dependencies

- `fabricatio-core` — core interfaces and utilities
- `fabricatio-capabilities` — base capability patterns (Rating, Propose)
- `fabricatio-question` — interactive prompts for supervisor check

## License

MIT — see [LICENSE](../../LICENSE)
