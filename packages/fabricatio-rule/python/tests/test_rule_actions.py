"""Tests for fabricatio-rule actions and Censor capability."""

import pytest
from fabricatio_mock.models.mock_role import ProposeTestRole
from fabricatio_rule.actions.rules import DraftRuleSet, GatherRuleset
from fabricatio_rule.capabilities.censor import Censor
from fabricatio_rule.models.rule import Rule, RuleSet

# ---------------------------------------------------------------------------
# GatherRuleset action tests
# ---------------------------------------------------------------------------


class TestGatherRuleset:
    """Tests for GatherRuleset action."""

    def test_from_mapping(self) -> None:
        """Test creating GatherRuleset actions from a mapping."""
        mapping = {"out1": ["rs_a", "rs_b"], "out2": ["rs_c"]}
        actions = GatherRuleset.from_mapping(mapping)
        assert len(actions) == 2
        assert actions[0].output_key == "out1"
        assert actions[0].to_gather == ["rs_a", "rs_b"]
        assert actions[1].output_key == "out2"
        assert actions[1].to_gather == ["rs_c"]

    @pytest.mark.asyncio
    async def test_execute_gathers_rulesets(self) -> None:
        """Test _execute gathers rulesets from context."""
        rule_a = Rule(name="A", description="a", violation_examples=[], compliance_examples=[])
        rule_b = Rule(name="B", description="b", violation_examples=[], compliance_examples=[])
        rs1 = RuleSet(name="Set1", description="first", rules=[rule_a])
        rs2 = RuleSet(name="Set2", description="second", rules=[rule_b])

        action = GatherRuleset(to_gather=["rs1", "rs2"])
        result = await action._execute(rs1=rs1, rs2=rs2)
        assert isinstance(result, RuleSet)
        assert len(result.rules) == 2
        assert result.name == "Set1;Set2"

    @pytest.mark.asyncio
    async def test_execute_missing_key_raises(self) -> None:
        """Test _execute raises ValueError when key not in context."""
        action = GatherRuleset(to_gather=["missing_key"])
        with pytest.raises(ValueError, match="not found in context"):
            await action._execute()

    @pytest.mark.asyncio
    async def test_execute_invalid_type_raises(self) -> None:
        """Test _execute raises TypeError when value is not a RuleSet."""
        action = GatherRuleset(to_gather=["bad_key"])
        with pytest.raises(TypeError, match="Invalid RuleSet instance"):
            await action._execute(bad_key="not a ruleset")


# ---------------------------------------------------------------------------
# DraftRuleSet action tests
# ---------------------------------------------------------------------------


class TestDraftRuleSet:
    """Tests for DraftRuleSet action."""

    def test_from_mapping(self) -> None:
        """Test creating DraftRuleSet actions from a mapping."""
        mapping = {"out1": (3, "strict grammar rules"), "out2": (0, "style guide")}
        actions = DraftRuleSet.from_mapping(mapping)
        assert len(actions) == 2
        assert actions[0].output_key == "out1"
        assert actions[0].rule_count == 3
        assert actions[0].ruleset_requirement == "strict grammar rules"
        assert actions[1].output_key == "out2"
        assert actions[1].rule_count == 0
        assert actions[1].ruleset_requirement == "style guide"

    def test_default_values(self) -> None:
        """Test DraftRuleSet default field values."""
        action = DraftRuleSet()
        assert action.output_key == "drafted_ruleset"
        assert action.ruleset_requirement is None
        assert action.rule_count == 0


# ---------------------------------------------------------------------------
# Censor capability tests
# ---------------------------------------------------------------------------


class CensorRole(ProposeTestRole, Censor):
    """Test role combining ProposeTestRole with Censor capability."""


class TestCensor:
    """Tests for Censor capability."""

    @pytest.fixture
    def role(self) -> CensorRole:
        """Create a CensorRole instance."""
        return CensorRole()
        return CensorRole()

    @pytest.mark.asyncio
    async def test_censor_string_no_improvements(self, role: CensorRole) -> None:
        """Test censor_string returns text unchanged when check returns empty list."""
        from unittest.mock import AsyncMock, patch

        rule = Rule(name="R", description="r", violation_examples=[], compliance_examples=[])
        rs = RuleSet(name="Test", description="test", rules=[rule])

        with patch.object(type(role), "check_string", new_callable=AsyncMock, return_value=[]):
            result = await role.censor_string("clean text", rs)
        assert result == "clean text"

    @pytest.mark.asyncio
    async def test_censor_string_none_check(self, role: CensorRole) -> None:
        """Test censor_string returns None when check returns None."""
        from unittest.mock import AsyncMock, patch

        rule = Rule(name="R", description="r", violation_examples=[], compliance_examples=[])
        rs = RuleSet(name="Test", description="test", rules=[rule])

        with patch.object(type(role), "check_string", new_callable=AsyncMock, return_value=None):
            result = await role.censor_string("text", rs)
        assert result is None
