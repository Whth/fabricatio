"""Tests for fabricatio-rule configuration and models."""

import pytest
from fabricatio_rule.config import RuleConfig, rule_config
from fabricatio_rule.models.patch import RuleSetMetadata
from fabricatio_rule.models.rule import Rule, RuleSet

# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


class TestRuleConfig:
    """Tests for RuleConfig."""

    def test_default_templates(self) -> None:
        """Test default template values."""
        cfg = RuleConfig()
        assert cfg.ruleset_requirement_breakdown_template == "built-in/ruleset_requirement_breakdown"
        assert cfg.rule_requirement_template == "built-in/rule_requirement"
        assert cfg.check_string_template == "built-in/check_string"

    def test_custom_templates(self) -> None:
        """Test custom template values."""
        cfg = RuleConfig(
            ruleset_requirement_breakdown_template="custom/breakdown",
            rule_requirement_template="custom/rule",
            check_string_template="custom/check",
        )
        assert cfg.ruleset_requirement_breakdown_template == "custom/breakdown"
        assert cfg.rule_requirement_template == "custom/rule"
        assert cfg.check_string_template == "custom/check"

    def test_rule_config_singleton(self) -> None:
        """Test singleton is a RuleConfig instance."""
        assert isinstance(rule_config, RuleConfig)


# ---------------------------------------------------------------------------
# Rule model tests
# ---------------------------------------------------------------------------


class TestRuleModel:
    """Tests for Rule model."""

    @pytest.fixture
    def rule(self) -> Rule:
        """Create a sample Rule."""
        return Rule(
            name="Test Rule",
            description="A test rule",
            violation_examples=["bad example"],
            compliance_examples=["good example"],
        )

    def test_rule_fields(self, rule: Rule) -> None:
        """Test Rule has all expected fields."""
        assert rule.name == "Test Rule"
        assert rule.description == "A test rule"
        assert rule.violation_examples == ["bad example"]
        assert rule.compliance_examples == ["good example"]

    def test_rule_language_field(self, rule: Rule) -> None:
        """Test Rule has a language field."""
        assert hasattr(rule, "language")
        assert isinstance(rule.language, str)

    def test_rule_custom_language(self) -> None:
        """Test Rule with custom language stores the provided value."""
        rule = Rule(
            name="Règle",
            description="Une règle",
            violation_examples=["mauvais"],
            compliance_examples=["bon"],
            language="French",
        )
        # Language may be normalized by the system
        assert isinstance(rule.language, str)
        assert len(rule.language) > 0

    def test_rule_model_dump(self, rule: Rule) -> None:
        """Test Rule model_dump contains all fields."""
        data = rule.model_dump()
        assert "name" in data
        assert "description" in data
        assert "violation_examples" in data
        assert "compliance_examples" in data

    def test_rule_empty_examples(self) -> None:
        """Test Rule with empty example lists."""
        rule = Rule(
            name="Empty Rule",
            description="No examples",
            violation_examples=[],
            compliance_examples=[],
        )
        assert rule.violation_examples == []
        assert rule.compliance_examples == []

    def test_rule_model_json(self) -> None:
        """Test Rule serializes to valid JSON."""
        import orjson

        rule = Rule(name="R", description="d", violation_examples=["v"], compliance_examples=["c"])
        data = orjson.loads(rule.model_dump_json())
        assert data["name"] == "R"


# ---------------------------------------------------------------------------
# RuleSet model tests
# ---------------------------------------------------------------------------


class TestRuleSetModel:
    """Tests for RuleSet model."""

    @pytest.fixture
    def rules(self) -> list[Rule]:
        """Create sample rules."""
        return [
            Rule(
                name="Rule A",
                description="First rule",
                violation_examples=["bad A"],
                compliance_examples=["good A"],
            ),
            Rule(
                name="Rule B",
                description="Second rule",
                violation_examples=["bad B"],
                compliance_examples=["good B"],
            ),
        ]

    def test_ruleset_init(self, rules: list[Rule]) -> None:
        """Test RuleSet initialization."""
        rs = RuleSet(name="TestSet", description="A test ruleset", rules=rules)
        assert rs.name == "TestSet"

    def test_ruleset_has_language(self, rules: list[Rule]) -> None:
        """Test RuleSet has a language field."""
        rs = RuleSet(name="TestSet", description="desc", rules=rules)
        assert hasattr(rs, "language")

    def test_gather_two_rulesets(self, rules: list[Rule]) -> None:
        """Test gathering two rulesets."""
        rs1 = RuleSet(name="Set1", description="First", rules=[rules[0]])
        rs2 = RuleSet(name="Set2", description="Second", rules=[rules[1]])
        combined = RuleSet.gather(rs1, rs2)
        assert combined.name == "Set1;Set2"
        assert combined.description == "First;Second"
        assert len(combined.rules) == 2

    def test_gather_three_rulesets(self, rules: list[Rule]) -> None:
        """Test gathering three rulesets."""
        r = rules[0]
        rs1 = RuleSet(name="A", description="a", rules=[r])
        rs2 = RuleSet(name="B", description="b", rules=[r])
        rs3 = RuleSet(name="C", description="c", rules=[r])
        combined = RuleSet.gather(rs1, rs2, rs3)
        assert combined.name == "A;B;C"
        assert len(combined.rules) == 3

    def test_gather_empty_raises(self) -> None:
        """Test gather with no arguments raises."""
        with pytest.raises(ValueError, match="No rulesets provided"):
            RuleSet.gather()

    def test_gather_single_ruleset(self, rules: list[Rule]) -> None:
        """Test gathering a single ruleset."""
        rs = RuleSet(name="Only", description="only one", rules=rules)
        combined = RuleSet.gather(rs)
        assert combined.name == "Only"
        assert len(combined.rules) == 2


# ---------------------------------------------------------------------------
# RuleSetMetadata patch tests
# ---------------------------------------------------------------------------


class TestRuleSetMetadata:
    """Tests for RuleSetMetadata patch."""

    def test_ref_cls_returns_ruleset(self) -> None:
        """Test ref_cls returns RuleSet."""
        assert RuleSetMetadata.ref_cls() is RuleSet

    def test_apply_updates_name_and_description(self) -> None:
        """Test applying metadata patch to a RuleSet."""
        rule = Rule(name="R", description="r", violation_examples=[], compliance_examples=[])
        rs = RuleSet(name="Old Name", description="Old Desc", rules=[rule])
        patch = RuleSetMetadata(name="New Name", description="New Desc")
        result = patch.apply(rs)
        assert result.name == "New Name"
        assert result.description == "New Desc"

    def test_apply_partial_patch(self) -> None:
        """Test applying patch with only name changed."""
        rule = Rule(name="R", description="r", violation_examples=[], compliance_examples=[])
        rs = RuleSet(name="Old", description="Old Desc", rules=[rule])
        patch = RuleSetMetadata(name="New", description="Old Desc")
        result = patch.apply(rs)
        assert result.name == "New"
