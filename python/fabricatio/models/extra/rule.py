"""A module containing classes related to rule sets and rules.

This module provides the `Rule` and `RuleSet` classes, which are used to define and manage
individual rules and collections of rules, respectively. These classes are designed to
facilitate the creation, organization, and application of rules in various contexts,
ensuring clarity, consistency, and enforceability. The module supports detailed
descriptions, examples, and metadata for each rule and rule set, making it suitable for
complex rule management systems.
"""


from typing import List

from fabricatio.models.generic import PersistentAble, SketchedAble, WithBriefing


class Rule(WithBriefing, SketchedAble):
    """Represents a rule or guideline for a specific topic.

    The `Rule` class encapsulates a single rule, providing detailed information about its
    purpose, scope, and application. It includes fields for a comprehensive description,
    examples of violations, and examples of compliance. This class is designed to ensure
    that rules are clearly defined, well-documented, and easy to understand and enforce.
    """

    description: str
    """A comprehensive description of the rule, including its purpose, scope, and context.
    This should clearly explain what the rule is about, why it exists, and in what situations
    it applies. The description should be detailed enough to provide full understanding of
    the rule's intent and application."""

    violation_examples: List[str]
    """A list of concrete examples demonstrating violations of this rule. Each example should
    be a clear scenario or case that illustrates how the rule can be broken, including the
    context, actions, and consequences of the violation. These examples should help in
    understanding the boundaries of the rule."""

    compliance_examples: List[str]
    """A list of concrete examples demonstrating proper compliance with this rule. Each example
    should be a clear scenario or case that illustrates how to correctly follow the rule,
    including the context, actions, and positive outcomes of compliance. These examples should
    serve as practical guidance for implementing the rule correctly."""


class RuleSet(SketchedAble, PersistentAble, WithBriefing):
    """Represents a collection of rules and guidelines for a particular topic.

    The `RuleSet` class is used to group related rules into a coherent set, providing a
    structured way to manage and apply multiple rules. It includes a description of the
    overall purpose and scope of the rule set, as well as a list of individual rules. This
    class is designed to ensure that rule sets are well-organized, consistent, and easy to
    navigate and enforce.
    """

    description: str
    """A comprehensive description of the rule set, including its overall purpose, scope, and
    context. This should explain why this collection of rules exists, what domain or topic it
    covers, and how the rules within the set are related to each other. The description should
    provide a clear understanding of the rule set's intent and application."""

    rules: List[Rule]
    """The collection of rules and guidelines contained in this rule set. Each rule should be
    a well-defined, specific guideline that contributes to the overall purpose of the rule set.
    The rules should be logically organized and consistent with each other, forming a coherent
    framework for the topic or domain covered by the rule set."""
