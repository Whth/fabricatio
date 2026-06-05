# `fabricatio-rule`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-rule)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-rule)](https://pypi.org/project/fabricatio-rule/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-rule/week)](https://pepy.tech/projects/fabricatio-rule)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-rule)](https://pepy.tech/projects/fabricatio-rule)
[![Build Tool: uv](https://img.shields.io/badge/built%20with-uv-orange)](https://github.com/astral-sh/uv)

LLM-backed rule drafting, content validation, and correction enforcement for Fabricatio agents.

## Installation

```bash
pip install fabricatio[rule]
# or
uv pip install fabricatio[rule]
```

## Overview

`fabricatio-rule` provides capability mixins and actions that let Fabricatio agents validate and correct content against structured, machine-readable rulesets. Rulesets are drafted from natural language requirements using the agent's configured LLM, then applied to strings or structured objects (implementing `Display`/`WithBriefing`). Violations produce typed `Improvement` objects — making downstream correction workflows fully automated.

## Key Types

| Class | Role |
|---|---|
| `Rule` | A single rule: name, description, plus lists of `violation_examples` and `compliance_examples`. Extends `WithBriefing`, `Language`, `SketchedAble`, `PersistentAble`. |
| `RuleSet` | A named collection of `Rule` instances. Has a `gather(*rulesets)` classmethod to merge multiple rulesets into one. Extends the same base classes as `Rule`. |
| `RuleSetMetadata` | A `Patch[RuleSet]` for updating a ruleset's name and description fields, used internally during drafting. |
| `CheckKwargs` | Typed kwargs for check operations; extends `ReferencedKwargs[Improvement]` with a `ruleset: RuleSet` field. |

## Capabilities

### `Check` — rule-based validation

`from fabricatio_rule.capabilities.check import Check`

An ABC mixin (extends `EvidentlyJudge`, `Propose`) that adds rule-aware validation to any agent:

```python
class Check(EvidentlyJudge, Propose, ABC):
    async def draft_ruleset(
        self, ruleset_requirement: str, rule_count: int = 0, **kwargs
    ) -> Optional[RuleSet]: ...

    async def check_string_against_rule(
        self, input_text: str, rule: Rule, reference: str = "", **kwargs
    ) -> Optional[Improvement]: ...

    async def check_obj_against_rule(
        self, obj: M, rule: Rule, reference: str = "", **kwargs
    ) -> Optional[Improvement]: ...

    async def check_string(
        self, input_text: str, ruleset: RuleSet, reference: str = "", **kwargs
    ) -> Optional[List[Improvement]]: ...

    async def check_obj(
        self, obj: M, ruleset: RuleSet, reference: str = "", **kwargs
    ) -> Optional[List[Improvement]]: ...
```

- `draft_ruleset` breaks a natural language requirement into individual rule requirements, proposes `Rule` instances and a `RuleSetMetadata` patch, then assembles the final `RuleSet`.
- `check_string` / `check_obj` validate content against every rule in a ruleset concurrently, returning a list of `Improvement` objects (one per violation).
- `check_string_against_rule` / `check_obj_against_rule` validate against a single rule. They use `evidently_judge` to confirm a violation, then propose an `Improvement` if one is found.

### `Censor` — check-then-correct workflows

`from fabricatio_rule.capabilities.censor import Censor`

An ABC mixin (extends `Correct`, `Check`) that combines validation and correction:

```python
class Censor(Correct, Check, ABC):
    async def censor_string(
        self, input_text: str, ruleset: RuleSet, **kwargs
    ) -> Optional[str]: ...

    async def censor_obj(
        self, obj: M, ruleset: RuleSet, **kwargs
    ) -> Optional[M]: ...

    async def censor_obj_inplace(
        self, obj: M, ruleset: RuleSet, **kwargs
    ) -> Optional[M]: ...
```

Each method checks the input against the ruleset, gathers any `Improvement` results, then applies corrections via `fabricatio-improve`'s `Correct` capability. Returns the corrected value, or the original if no violations are found.

## Actions

### `DraftRuleSet`

`from fabricatio_rule.actions.rules import DraftRuleSet`

An `Action` (mixing in `Check` and `FromMapping`) that drafts a `RuleSet` from a natural language requirement and stores it in the agent's context under `output_key` (default `"drafted_ruleset"`). Supports batch creation via `from_mapping`.

### `GatherRuleset`

`from fabricatio_rule.actions.rules import GatherRuleset`

An `Action` (mixing in `FromMapping`) that gathers multiple `RuleSet` instances from the agent's context into a single merged ruleset via `RuleSet.gather()`. Validates that all named keys exist and reference `RuleSet` instances.

## Configuration

```python
from fabricatio_rule.config import rule_config

@dataclass
class RuleConfig:
    ruleset_requirement_breakdown_template: str  # template for breaking down requirements
    rule_requirement_template: str               # template for proposing individual rules
    check_string_template: str                   # template for check strings
```

Loaded via `fabricatio-core`'s `CONFIG.load("rule", RuleConfig)`. Customize template names at runtime to swap prompt strategies.

## Usage

```python
from fabricatio_rule.actions.rules import DraftRuleSet, GatherRuleset
from fabricatio_rule.capabilities.censor import Censor
from fabricatio_rule.models.rule import RuleSet


class MyCensor(Censor):
    """Agent that validates and corrects content against rules."""
    pass


async def example():
    # Generate a ruleset from a natural language requirement
    draft = DraftRuleSet(
        ruleset_requirement="Professional tone: no slang, no contractions, formal grammar",
        output_key="style_rules",
    )
    style_rules: RuleSet = await draft._execute()

    # Check and correct content
    censor = MyCensor()
    result = await censor.censor_string(
        "this aint right lol",
        style_rules,
    )
    print(f"Corrected: {result}")
```

Merging multiple rulesets:

```python
async def merge_example(cxt):
    gather = GatherRuleset(
        to_gather=["style_rules", "grammar_rules"],
        output_key="all_rules",
    )
    combined = await gather._execute(**cxt)
    # combined is RuleSet.gather(style_rules, grammar_rules)
```

## Package Structure

```
fabricatio-rule/
├── python/fabricatio_rule/
│   ├── actions/
│   │   └── rules.py           # DraftRuleSet, GatherRuleset
│   ├── capabilities/
│   │   ├── check.py           # Check mixin
│   │   └── censor.py          # Censor mixin
│   ├── models/
│   │   ├── rule.py            # Rule, RuleSet
│   │   ├── patch.py           # RuleSetMetadata
│   │   └── kwargs_types.py    # CheckKwargs
│   └── config.py              # RuleConfig, rule_config
└── python/tests/
    ├── test_check.py
    └── test_ruleset.py
```

## Dependencies

- `fabricatio-core` — base interfaces, templates, action infrastructure
- `fabricatio-improve` — `Improvement` model and `Correct` capability
- `fabricatio-judge` — `EvidentlyJudge` for violation detection
- `fabricatio-capabilities` — base capability patterns (`Patch`, `ProposedUpdateAble`)

## License

MIT — see [LICENSE](LICENSE)
