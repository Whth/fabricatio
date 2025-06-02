"""Module containing configuration classes for fabricatio-rule."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass
class RuleConfig:
    """Configuration for fabricatio-rule."""

    # Rule and Requirement Templates
    ruleset_requirement_breakdown_template: str = "ruleset_requirement_breakdown"
    """The name of the ruleset requirement breakdown template which will be used to breakdown a ruleset requirement."""

    rule_requirement_template: str = "rule_requirement"
    """The name of the rule requirement template which will be used to generate a rule requirement."""
    check_string_template: str = "check_string"
    """The name of the check string template which will be used to check a string."""


rule_config = CONFIG.load("rule", RuleConfig)
__all__ = ["rule_config"]
