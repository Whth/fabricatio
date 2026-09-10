# `fabricatio-judge`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-judge)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-judge)](https://pypi.org/project/fabricatio-judge/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-judge/week)](https://pepy.tech/projects/fabricatio-judge)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-judge)](https://pepy.tech/projects/fabricatio-judge)
[![Build Tool: uv](https://img.shields.io/badge/built%20with-uv-orange)](https://github.com/astral-sh/uv)

Structured, evidence-based binary judgment for LLM applications.

## Installation

```bash
pip install fabricatio[judge]
# or
uv pip install fabricatio[judge]
```

## Overview

`fabricatio-judge` provides capability mixins that turn any Fabricatio agent into a structured judge. Instead of raw LLM calls that return arbitrary text, judgments produce typed `JudgeMent` objects — capturing the issue, affirmative and denying evidence, and a final boolean verdict — so downstream code can act on a reliable, machine-readable result.

Three capabilities are available:

- **Single-judge** (`EvidentlyJudge`): one LLM evaluates the prompt and returns a `JudgeMent`.
- **Weighted voting** (`VoteJudge`): multiple LLM configurations each produce a `JudgeMent`; their boolean verdicts are weighted and tallied against a configurable pass threshold.
- **Refine loop** (`RefineLoop`): bounded generate → judge → revise re-generation driven by a `Verdict`; the last attempt is always kept.

## Key Types

| Class | Role |
|---|---|
| `JudgeMent` | Pydantic model holding `issue_to_judge`, `affirm_evidence`, `deny_evidence`, and `final_judgement`. Truthy via `__bool__`. |
| `ImageVerdict` | `JudgeMent` extension with `glitch_reasons`/`coherence_reasons`; `.feedback` joins them into revision prose. Mixes in the `Verdict` contract. |
| `Verdict` | Nominal ABC (`passed` + `feedback`) mixed into verdict models the refine loop consumes. |
| `EvidentlyJudge` | ABC mixin (extends `Propose`). Adds `evidently_judge(prompt, **kwargs)`. |
| `VoteLLMConfig` | Config model (extends `ScopedConfig`). Declares `vote_llm` (weight → kwargs map) and `vote_pass_threshold`. |
| `VoteJudge` | ABC mixin (extends `EvidentlyJudge` + `VoteLLMConfig`). Adds `vote_judge(prompt, ...)` and `resolve_pass(…)`. |
| `RefineLoop` | ABC mixin (extends `Propose`). Adds `refine_until_accepted(cls, requirement, spec, plan, ...)` — the bounded judged re-generation loop. |
| `Attempt` / `AttemptHistory` | Frozen models recording rejected attempts; the history renders the feedback tail appended to revision requirements. |
| `RefinePlan` | Frozen model bundling the loop's consumer seams: `generate`, `judge`, `request_of`, optional `on_reject`, `label`. A failing `generate` raises; the exception propagates untouched through the loop. |

### `JudgeMent`

```python
class JudgeMent(SketchedAble):
    issue_to_judge: str          # The question or statement under evaluation
    affirm_evidence: List[str]   # Evidence supporting a True verdict
    deny_evidence: List[str]     # Evidence supporting a False verdict
    final_judgement: bool        # The binary verdict
```

### `EvidentlyJudge`

```python
class EvidentlyJudge(Propose, ABC):
    async def evidently_judge(
        self, prompt: str | List[str], **kwargs
    ) -> JudgeMent | List[JudgeMent] | None: ...
```

Accepts a single prompt (returns `JudgeMent | None`) or a list (returns `List[JudgeMent | None]`). Delegates to the agent's `propose` infrastructure, which invokes the configured LLM with structured output constrained to the `JudgeMent` schema.

### `VoteJudge`

```python
class VoteJudge(EvidentlyJudge, VoteLLMConfig, ABC):
    async def vote_judge(
        self, prompt: str | List[str],
        vote_pass_threshold: float | None = None, **kwargs
    ) -> bool | List[bool | None] | None: ...

    @staticmethod
    def resolve_pass(
        weights: List[float],
        judgments: List[JudgeMent],
        vote_pass_threshold: float,
    ) -> bool: ...
```

`vote_judge` runs `evidently_judge` concurrently across all configured LLM weights for each prompt, then calls `resolve_pass` to determine the final boolean. The pass criterion:

```
sum(weight[i] for i where judgment[i] is True) >= threshold * sum(all weights)
```

If any individual judgment returns `None`, the vote is treated as `False` with a warning.

### `RefineLoop`

```python
from abc import ABC

from fabricatio_judge.capabilities import RefineLoop
from fabricatio_judge.models import RefinePlan


class MyRefiner(RefineLoop, ABC):
    """Role that re-generates an artifact until its judge accepts it."""


plan = RefinePlan(generate=..., judge=..., request_of=..., label="the unit")
artifact = await my_refiner.refine_until_accepted(
    MySpec,
    "the base requirement",
    initial_spec,
    plan,
    max_tries=3,
    feedback_template="my_feedback_template",
)
```

`feedback_template` names a Handlebars template in the template store, rendered with
`{"history": [{"prompt": ..., "feedback": ...}, ...]}`: its output is the rejected-attempt tail
appended to the requirement before each revision.

The loop owns the invariants so consumers cannot get them wrong: `max_tries` counts
TOTAL generation attempts (`1` renders exactly once without judging — the gate-off
shape), the last attempt is kept unjudged (no retry budget remains), a failing
generation raises out of the loop (the consumer degrades at its own boundary),
a judge answering `None` degrades open (the artifact is kept), and every rejection
accumulates into the revision requirement so the next proposal sees all prior
defects. The varying parts — how to generate, judge, and describe an artifact —
arrive as the `RefinePlan` seams.

## Usage

### Single-judge

```python
from fabricatio_judge.capabilities.advanced_judge import EvidentlyJudge
from fabricatio_judge.models.judgement import JudgeMent


class MyAgent(EvidentlyJudge):
    """Agent that can judge evidence."""
    pass


async def main():
    agent = MyAgent()
    result: JudgeMent = await agent.evidently_judge("Is the PR safe to merge?")
    if result:
        print(f"Approved — evidence: {result.affirm_evidence}")
    else:
        print(f"Blocked — concerns: {result.deny_evidence}")
```

### Weighted voting

```python
from fabricatio_judge.capabilities.advanced_judge import VoteJudge
from fabricatio_judge.models.judgement import JudgeMent
from fabricatio_core.models.kwargs_types import ValidateKwargs
from typing import Dict


class MyVoter(VoteJudge):
    vote_llm: Dict[float, ValidateKwargs[JudgeMent]] = {
        0.5: {"temperature": 0.3},   # conservative
        0.7: {"temperature": 0.7},   # balanced
        0.9: {"temperature": 1.0},   # creative
    }
    vote_pass_threshold: float = 0.5


async def main():
    voter = MyVoter()
    passed = await voter.vote_judge("Should we deploy to production?")
    print(f"Deploy decision: {passed}")

    # Multiple prompts at once
    results = await voter.vote_judge([
        "Is service A healthy?",
        "Is service B healthy?",
    ])
    # results → [True, False]
```

## Package Structure

```
fabricatio-judge/
├── python/fabricatio_judge/
│   ├── capabilities/
│   │   ├── advanced_judge.py   # EvidentlyJudge, VoteJudge, VoteLLMConfig
│   │   └── refine.py           # RefineLoop
│   └── models/
│       ├── judgement.py        # JudgeMent, ImageVerdict, Verdict contract
│       └── refine.py           # Attempt, AttemptHistory, RefinePlan
└── python/tests/
    ├── test_judge.py
    └── test_refine.py
```

## License

MIT — see [LICENSE](LICENSE)
