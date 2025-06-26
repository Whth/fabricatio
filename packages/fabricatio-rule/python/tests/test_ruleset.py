"""This module contains unit tests for the RuleSet class.

It verifies correct initialization and behavior of RuleSet objects,
as well as interactions between Rule and RuleSet instances.
"""

import pytest
from fabricatio_rule.models.rule import Rule, RuleSet


@pytest.fixture
def sample_rule() -> Rule:
    """Fixture that provides a sample Rule instance for testing.

    Returns:
        Rule: A test Rule object with predefined properties.
    """
    return Rule(
        name="Test Rule",
        description="A rule for testing purposes",
        violation_examples=["Example violation 1", "Example violation 2"],
        compliance_examples=["Example compliance 1", "Example compliance 2"],
    )


@pytest.fixture
def sample_rule_set(sample_rule: Rule) -> RuleSet:
    """Fixture that provides a sample RuleSet instance for testing.

    Args:
        sample_rule (Rule): A pre-configured Rule instance.

    Returns:
        RuleSet: A test RuleSet containing the provided Rule.
    """
    return RuleSet(name="Test RuleSet", description="A ruleset for testing purposes", rules=[sample_rule])


def test_rule_initialization(sample_rule: Rule) -> None:
    """Test the correct initialization of a Rule instance.

    Args:
        sample_rule (Rule): The Rule instance to be tested.
    """
    assert sample_rule.name == "Test Rule"
    assert sample_rule.description == "A rule for testing purposes"
    assert sample_rule.language == "English"
    assert len(sample_rule.violation_examples) == 2
    assert len(sample_rule.compliance_examples) == 2


def test_rule_set_initialization(sample_rule_set: RuleSet, sample_rule: Rule) -> None:
    """Test the correct initialization of a RuleSet instance.

    Args:
        sample_rule_set (RuleSet): The RuleSet instance to be tested.
        sample_rule (Rule): The sample Rule used in the RuleSet.
    """
    assert sample_rule_set.name == "Test RuleSet"
    assert sample_rule_set.description == "A ruleset for testing purposes"
    assert sample_rule_set.language == "English"
    assert len(sample_rule_set.rules) == 1
    assert sample_rule_set.rules[0] == sample_rule


def test_gather_method(sample_rule: Rule) -> None:
    """Test the gather method of RuleSet which combines multiple RuleSets.

    Args:
        sample_rule (Rule): A sample Rule used in both input RuleSets.
    """
    ruleset1 = RuleSet(name="Set 1", description="First ruleset", rules=[sample_rule])

    ruleset2 = RuleSet(name="Set 2", description="Second ruleset", rules=[sample_rule])

    combined = RuleSet.gather(ruleset1, ruleset2)

    assert combined.name == "Set 1;Set 2"
    assert combined.description == "First ruleset;Second ruleset"
    assert len(combined.rules) == 2
    assert combined.rules[0] == sample_rule
    assert combined.rules[1] == sample_rule


def test_gather_method_raises_error() -> None:
    """Test that the gather method raises ValueError when no arguments are provided."""
    with pytest.raises(ValueError, match="No rulesets provided"):
        RuleSet.gather()
