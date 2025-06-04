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
This feature allows users to define rulesets using natural language descriptions. The module parses the natural language input and converts it into a structured ruleset. For example, a user can describe a rule like "All sentences must end with a period" and the module will generate the corresponding rule for content validation.
- Content validation against rulesets
Once the rulesets are defined, the module can validate text and structured objects against these rules. It checks if the content adheres to all the rules in the ruleset. For instance, if a rule states that all words should be in lowercase, the module will flag any words in uppercase as violations.
- Automatic correction suggestions
When content violations are detected, the module can generate automatic correction suggestions. These suggestions are based on the defined rules and the nature of the violation. For example, if a spelling error is detected according to a spelling rule, it can suggest the correct spelling.
- Censoring/filtering of content
This feature enables the censoring or filtering of content based on the rulesets. It can remove or modify parts of the content that violate the rules. For example, if a rule prohibits the use of certain words, the module can censor those words in the content.

### Key Features:

- Asynchronous execution support
The module supports asynchronous execution, which means it can perform multiple tasks concurrently without blocking the main thread. This is useful for handling large amounts of content or multiple rulesets simultaneously. For example, it can validate multiple documents at the same time, improving the overall performance.
- Structured rule definition format
The rulesets are defined in a structured format, which makes them easy to manage and apply. Each rule has a clear definition, including the conditions and actions. This structured format also allows for easy combination and modification of rulesets. For example, users can combine multiple rulesets to create a more comprehensive set of rules.
- Evidence-based judgment integration
The module integrates evidence-based judgment capabilities. It can collect evidence about content violations and use this evidence to make more informed decisions. For example, if a rule violation occurs, it can record the location, the nature of the violation, and any relevant context as evidence.
- Content correction workflows
The content correction workflows define the steps for correcting content violations. It includes processes such as identifying violations, generating correction suggestions, and applying the corrections. These workflows ensure a systematic approach to content correction. For example, it can first identify all the spelling errors, then generate correction suggestions, and finally apply the corrections to the content.
- Multiple input types (strings, Display/WithBriefing objects)
The module can handle multiple input types, including plain strings and more complex Display/WithBriefing objects. This flexibility allows it to be used in different scenarios. For example, it can validate the text in a simple string or the content of a structured object with additional metadata.

## 🧩 Usage Example

```python
from fabricatio_rule.actions.rules import DraftRuleSet
The `DraftRuleSet` class is used to generate rulesets based on natural language requirements. It takes a natural language description as input and returns a structured `RuleSet` object. For example, it can convert a description like "All paragraphs should have at least three sentences" into a rule that can be used for content validation.
from fabricatio_rule.capabilities.censor import Censor
The `Censor` class is responsible for content filtering and correction. It can apply the defined rulesets to the input content and perform actions such as censoring inappropriate words or correcting grammar errors. It can be subclassed to implement custom logic for content handling.
from fabricatio_rule.models.rule import RuleSet
The `RuleSet` class represents a collection of rules. It provides methods for managing and applying the rules in the set. For example, it can check if a piece of content adheres to all the rules in the set and return the results of the validation.


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