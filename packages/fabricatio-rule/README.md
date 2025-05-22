# `fabricatio-rule`

A Python module for rule-based content validation, correction, and enforcement in LLM applications.

## 📦 Installation

This package is part of the `fabricatio` monorepo and can be installed as an optional dependency:

```bash
pip install fabricatio[rule]
```

Or install all components:

```bash
pip install fabricatio[full]
```

## 🔍 Overview

Provides robust tools for defining, applying, and enforcing rulesets across text and structured objects. Combines
capabilities from multiple packages to offer:

- Rule generation based on natural language requirements
- Content validation against rulesets
- Automatic correction suggestions
- Censoring/filtering of content

### Key Features:

- Asynchronous execution support
- Structured rule definition format
- Evidence-based judgment integration
- Content correction workflows
- Multiple input types (strings, Display/WithBriefing objects)

## 🧩 Usage Example

```python
from fabricatio_rule.actions.rules import DraftRuleSet
from fabricatio_rule.capabilities.censor import Censor
from fabricatio_rule.models.rule import RuleSet


class MyCensor(Censor):
    pass  # Implement custom logic if needed


async def example():
    # Generate a ruleset
    draft_action = DraftRuleSet(ruleset_requirement="Professional tone and grammar")
    ruleset: RuleSet = await draft_action._execute()

    # Use censor to validate and correct content
    censor = MyCensor()
    result = await censor.censor_string(
        "Ths is a verry bad exmple of txt.",
        ruleset
    )
    print(f"Corrected text: {result}")
```

## 📁 Structure

```
fabricatio-rule/
├── actions/
│   └── rules.py       - Rule set drafting/gathering actions
├── capabilities/
│   ├── check.py       - Core rule checking functionality
│   └── censor.py      - Content filtering/correction capabilities
└── models/
    ├── kwargs_types.py - Validation argument types
    ├── patch.py        - Metadata patching utilities
    └── rule.py         - Rule/RuleSet definitions
```

## 🔗 Dependencies

Built on top of other Fabricatio modules:

- `fabricatio-core` - Core interfaces and utilities
- `fabricatio-improve` - Correction suggestion mechanisms
- `fabricatio-judge` - Evidence-based decision making
- `fabricatio-capabilities` - Base capability patterns

## 📄 License

MIT – see [LICENSE](LICENSE)

GitHub: [github.com/Whth/fabricatio](https://github.com/Whth/fabricatio)