"""Tests for the Check capability."""

import pytest
from fabricatio_core.models.generic import Display, WithBriefing
from fabricatio_improve.models.improve import Improvement
from fabricatio_improve.models.problem import Problem, ProblemSolutions, Solution
from fabricatio_judge.models.judgement import JudgeMent
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_model_json_string, return_string
from fabricatio_mock.utils import install_router
from fabricatio_rule.capabilities.check import Check
from fabricatio_rule.models.patch import RuleSetMetadata
from fabricatio_rule.models.rule import Rule, RuleSet


class MockDisplayObject(Display):
    """Mock object that implements Display interface."""

    content: str


class MockBriefingObject(WithBriefing):
    """Mock object that implements WithBriefing interface."""

    name: str = "Mock Briefing Object"
    description: str = "A mock object for testing"


class CheckRole(LLMTestRole, Check):
    """A test role that implements the Check capability."""


@pytest.fixture
def check_role() -> CheckRole:
    """Create a CheckRole instance for testing.

    Returns:
        CheckRole: CheckRole instance
    """
    return CheckRole()


@pytest.fixture
def sample_rule() -> Rule:
    """Create a sample rule for testing.

    Returns:
        Rule: Sample rule instance
    """
    return Rule(
        name="No Profanity Rule",
        description="Content must not contain profane or offensive language",
        violation_examples=["This is damn bad", "What the hell"],
        compliance_examples=["This is very bad", "What on earth"],
        language="en",
    )


@pytest.fixture
def sample_ruleset(sample_rule: Rule) -> RuleSet:
    """Create a sample ruleset for testing.

    Returns:
        RuleSet: Sample ruleset instance
    """
    return RuleSet(
        name="Content Guidelines", description="Guidelines for appropriate content", rules=[sample_rule], language="en"
    )


@pytest.fixture
def sample_improvement() -> Improvement:
    """Create a sample improvement for testing.

    Returns:
        Improvement: Sample improvement instance
    """
    problem = Problem(
        cause="Content contains inappropriate language", name="Profanity Issue", severity_level=7, location="Line 5"
    )
    solution = Solution(
        mechanism="Replace profane words with appropriate alternatives",
        name="Replace Profanity",
        execute_steps=["Identify profane words", "Replace with alternatives", "Review content"],
        feasibility_level=9,
        impact_level=8,
    )
    problem_solution = ProblemSolutions(problem=problem, solutions=[solution])
    return Improvement(focused_on="Language Appropriateness", problem_solutions=[problem_solution])


@pytest.fixture
def sample_judgment() -> JudgeMent:
    """Create a sample judgment for testing.

    Returns:
        JudgeMent: Sample judgment instance
    """
    return JudgeMent(
        issue_to_judge="Profanity check",
        affirm_evidence=["Contains word 'damn'"],
        deny_evidence=["Context is mild"],
        final_judgement=True,
    )


@pytest.fixture
def ruleset_metadata() -> RuleSetMetadata:
    """Create sample ruleset metadata for testing.

    Returns:
        RuleSetMetadata: Sample metadata instance
    """
    return RuleSetMetadata(name="Test Ruleset", description="A test ruleset for validation")


class TestDraftRuleset:
    """Test cases for draft_ruleset method."""

    @pytest.mark.asyncio
    async def test_draft_ruleset_success(
        self, check_role: CheckRole, sample_rule: Rule, ruleset_metadata: RuleSetMetadata
    ) -> None:
        """Test successful ruleset drafting.

        Args:
            check_role (CheckRole): CheckRole fixture
            sample_rule (Rule): Sample rule fixture
            ruleset_metadata (RuleSetMetadata): Metadata fixture
        """
        requirement = "Create rules for code quality"

        router = return_model_json_string(sample_rule, ruleset_metadata)

        with install_router(router):
            result = await check_role.draft_ruleset(requirement, rule_count=1)

            assert result is not None
            assert isinstance(result, RuleSet)
            assert result.name == "Test Ruleset"
            assert len(result.rules) >= 1

    @pytest.mark.asyncio
    async def test_draft_ruleset_single_rule(
        self, check_role: CheckRole, sample_rule: Rule, ruleset_metadata: RuleSetMetadata
    ) -> None:
        """Test drafting ruleset with single rule.

        Args:
            check_role (CheckRole): CheckRole fixture
            sample_rule (Rule): Sample rule fixture
            ruleset_metadata (RuleSetMetadata): Metadata fixture
        """
        requirement = "Simple rule"

        router = return_model_json_string(sample_rule, ruleset_metadata)

        with install_router(router):
            result = await check_role.draft_ruleset(requirement, rule_count=1)

            assert result is not None
            assert len(result.rules) == 1

    @pytest.mark.asyncio
    async def test_draft_ruleset_none_response(self, check_role: CheckRole) -> None:
        """Test draft_ruleset when rule generation returns None.

        Args:
            check_role (CheckRole): CheckRole fixture
        """
        router = return_string("null")

        with install_router(router):
            result = await check_role.draft_ruleset("Test requirement")

            assert result is None


class TestCheckStringAgainstRule:
    """Test cases for check_string_against_rule method."""

    @pytest.mark.asyncio
    async def test_check_string_violation_found(
        self, check_role: CheckRole, sample_rule: Rule, sample_judgment: JudgeMent, sample_improvement: Improvement
    ) -> None:
        """Test checking string that violates a rule.

        Args:
            check_role (CheckRole): CheckRole fixture
            sample_rule (Rule): Sample rule fixture
            sample_judgment (JudgeMent): Sample judgment fixture
            sample_improvement (Improvement): Sample improvement fixture
        """
        input_text = "This is damn bad content"

        router = return_model_json_string(sample_judgment, sample_improvement)

        with install_router(router):
            result = await check_role.check_string_against_rule(input_text, sample_rule)

            assert result is not None
            assert isinstance(result, Improvement)
            assert result.focused_on == "Language Appropriateness"

    @pytest.mark.asyncio
    async def test_check_string_no_violation(self, check_role: CheckRole, sample_rule: Rule) -> None:
        """Test checking string that doesn't violate a rule.

        Args:
            check_role (CheckRole): CheckRole fixture
            sample_rule (Rule): Sample rule fixture
        """
        input_text = "This is appropriate content"
        false_judgment = JudgeMent(
            issue_to_judge="Profanity check",
            affirm_evidence=[],
            deny_evidence=["No inappropriate language found"],
            final_judgement=False,
        )

        router = return_model_json_string(false_judgment)

        with install_router(router):
            result = await check_role.check_string_against_rule(input_text, sample_rule)

            assert result is None

    @pytest.mark.asyncio
    async def test_check_string_with_reference(
        self, check_role: CheckRole, sample_rule: Rule, sample_judgment: JudgeMent, sample_improvement: Improvement
    ) -> None:
        """Test checking string with reference text.

        Args:
            check_role (CheckRole): CheckRole fixture
            sample_rule (Rule): Sample rule fixture
            sample_judgment (JudgeMent): Sample judgment fixture
            sample_improvement (Improvement): Sample improvement fixture
        """
        input_text = "Bad content"
        reference = "Good reference content"

        router = return_model_json_string(sample_judgment, sample_improvement)

        with install_router(router):
            result = await check_role.check_string_against_rule(input_text, sample_rule, reference)

            assert result is not None
            assert isinstance(result, Improvement)


class TestCheckObjAgainstRule:
    """Test cases for check_obj_against_rule method."""

    @pytest.mark.asyncio
    async def test_check_display_obj_violation(
        self, check_role: CheckRole, sample_rule: Rule, sample_judgment: JudgeMent, sample_improvement: Improvement
    ) -> None:
        """Test checking Display object that violates a rule.

        Args:
            check_role (CheckRole): CheckRole fixture
            sample_rule (Rule): Sample rule fixture
            sample_judgment (JudgeMent): Sample judgment fixture
            sample_improvement (Improvement): Sample improvement fixture
        """
        obj = MockDisplayObject(content="This damn content is bad")

        router = return_model_json_string(sample_judgment, sample_improvement)

        with install_router(router):
            result = await check_role.check_obj_against_rule(obj, sample_rule)

            assert result is not None
            assert isinstance(result, Improvement)

    @pytest.mark.asyncio
    async def test_check_briefing_obj_violation(
        self, check_role: CheckRole, sample_rule: Rule, sample_judgment: JudgeMent, sample_improvement: Improvement
    ) -> None:
        """Test checking WithBriefing object that violates a rule.

        Args:
            check_role (CheckRole): CheckRole fixture
            sample_rule (Rule): Sample rule fixture
            sample_judgment (JudgeMent): Sample judgment fixture
            sample_improvement (Improvement): Sample improvement fixture
        """
        obj = MockBriefingObject(briefing="This damn briefing is inappropriate")

        router = return_model_json_string(sample_judgment, sample_improvement)

        with install_router(router):
            result = await check_role.check_obj_against_rule(obj, sample_rule)

            assert result is not None
            assert isinstance(result, Improvement)

    @pytest.mark.asyncio
    async def test_check_obj_no_violation(self, check_role: CheckRole, sample_rule: Rule) -> None:
        """Test checking object that doesn't violate a rule.

        Args:
            check_role (CheckRole): CheckRole fixture
            sample_rule (Rule): Sample rule fixture
        """
        obj = MockDisplayObject(content="This is appropriate content")
        false_judgment = JudgeMent(
            issue_to_judge="Profanity check",
            affirm_evidence=[],
            deny_evidence=["No inappropriate language found"],
            final_judgement=False,
        )

        router = return_model_json_string(false_judgment)

        with install_router(router):
            result = await check_role.check_obj_against_rule(obj, sample_rule)

            assert result is None

    def test_check_obj_invalid_type(self, check_role: CheckRole, sample_rule: Rule) -> None:
        """Test checking object with invalid type.

        Args:
            check_role (CheckRole): CheckRole fixture
            sample_rule (Rule): Sample rule fixture
        """
        import asyncio

        invalid_obj = "Not a Display or WithBriefing object"

        async def run_test() -> None:
            with pytest.raises(TypeError, match="obj must be either Display or WithBriefing"):
                await check_role.check_obj_against_rule(invalid_obj, sample_rule)  # type: ignore

        asyncio.run(run_test())


class TestCheckString:
    """Test cases for check_string method."""

    @pytest.mark.asyncio
    async def test_check_string_multiple_violations(
        self,
        check_role: CheckRole,
        sample_ruleset: RuleSet,
        sample_judgment: JudgeMent,
        sample_improvement: Improvement,
    ) -> None:
        """Test checking string against ruleset with violations.

        Args:
            check_role (CheckRole): CheckRole fixture
            sample_ruleset (RuleSet): Sample ruleset fixture
            sample_judgment (JudgeMent): Sample judgment fixture
            sample_improvement (Improvement): Sample improvement fixture
        """
        input_text = "This damn content has issues"

        router = return_model_json_string(sample_judgment, sample_improvement)

        with install_router(router):
            result = await check_role.check_string(input_text, sample_ruleset)

            assert result is not None
            assert isinstance(result, list)
            assert len(result) > 0
            assert all(isinstance(imp, Improvement) for imp in result)

    @pytest.mark.asyncio
    async def test_check_string_no_violations(self, check_role: CheckRole, sample_ruleset: RuleSet) -> None:
        """Test checking string against ruleset with no violations.

        Args:
            check_role (CheckRole): CheckRole fixture
            sample_ruleset (RuleSet): Sample ruleset fixture
        """
        input_text = "This is perfectly appropriate content"
        false_judgment = JudgeMent(
            issue_to_judge="Check", affirm_evidence=[], deny_evidence=["No issues found"], final_judgement=False
        )

        router = return_model_json_string(false_judgment)

        with install_router(router):
            result = await check_role.check_string(input_text, sample_ruleset)

            assert result is not None
            assert isinstance(result, list)
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_check_string_with_reference(
        self,
        check_role: CheckRole,
        sample_ruleset: RuleSet,
        sample_judgment: JudgeMent,
        sample_improvement: Improvement,
    ) -> None:
        """Test checking string with reference against ruleset.

        Args:
            check_role (CheckRole): CheckRole fixture
            sample_ruleset (RuleSet): Sample ruleset fixture
            sample_judgment (JudgeMent): Sample judgment fixture
            sample_improvement (Improvement): Sample improvement fixture
        """
        input_text = "Content to check"
        reference = "Reference content"

        router = return_model_json_string(sample_judgment, sample_improvement)

        with install_router(router):
            result = await check_role.check_string(input_text, sample_ruleset, reference)

            assert result is not None
            assert isinstance(result, list)


class TestCheckObj:
    """Test cases for check_obj method."""

    @pytest.mark.asyncio
    async def test_check_obj_multiple_violations(
        self,
        check_role: CheckRole,
        sample_ruleset: RuleSet,
        sample_judgment: JudgeMent,
        sample_improvement: Improvement,
    ) -> None:
        """Test checking object against ruleset with violations.

        Args:
            check_role (CheckRole): CheckRole fixture
            sample_ruleset (RuleSet): Sample ruleset fixture
            sample_judgment (JudgeMent): Sample judgment fixture
            sample_improvement (Improvement): Sample improvement fixture
        """
        obj = MockDisplayObject(content="This damn object has issues")

        router = return_model_json_string(sample_judgment, sample_improvement)

        with install_router(router):
            result = await check_role.check_obj(obj, sample_ruleset)

            assert result is not None
            assert isinstance(result, list)
            assert len(result) > 0
            assert all(isinstance(imp, Improvement) for imp in result)

    @pytest.mark.asyncio
    async def test_check_obj_no_violations(self, check_role: CheckRole, sample_ruleset: RuleSet) -> None:
        """Test checking object against ruleset with no violations.

        Args:
            check_role (CheckRole): CheckRole fixture
            sample_ruleset (RuleSet): Sample ruleset fixture
        """
        obj = MockDisplayObject(content="This is appropriate object content")
        false_judgment = JudgeMent(
            issue_to_judge="Check", affirm_evidence=[], deny_evidence=["No issues found"], final_judgement=False
        )

        router = return_model_json_string(false_judgment)

        with install_router(router):
            result = await check_role.check_obj(obj, sample_ruleset)

            assert result is not None
            assert isinstance(result, list)
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_check_briefing_obj(
        self,
        check_role: CheckRole,
        sample_ruleset: RuleSet,
        sample_judgment: JudgeMent,
        sample_improvement: Improvement,
    ) -> None:
        """Test checking WithBriefing object against ruleset.

        Args:
            check_role (CheckRole): CheckRole fixture
            sample_ruleset (RuleSet): Sample ruleset fixture
            sample_judgment (JudgeMent): Sample judgment fixture
            sample_improvement (Improvement): Sample improvement fixture
        """
        obj = MockBriefingObject(briefing="Briefing with damn inappropriate language")

        router = return_model_json_string(sample_judgment, sample_improvement)

        with install_router(router):
            result = await check_role.check_obj(obj, sample_ruleset)

            assert result is not None
            assert isinstance(result, list)
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_check_obj_with_reference(
        self,
        check_role: CheckRole,
        sample_ruleset: RuleSet,
        sample_judgment: JudgeMent,
        sample_improvement: Improvement,
    ) -> None:
        """Test checking object with reference against ruleset.

        Args:
            check_role (CheckRole): CheckRole fixture
            sample_ruleset (RuleSet): Sample ruleset fixture
            sample_judgment (JudgeMent): Sample judgment fixture
            sample_improvement (Improvement): Sample improvement fixture
        """
        obj = MockDisplayObject(content="Object to check")
        reference = "Reference content"

        router = return_model_json_string(sample_judgment, sample_improvement)

        with install_router(router):
            result = await check_role.check_obj(obj, sample_ruleset, reference)

            assert result is not None
            assert isinstance(result, list)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_draft_ruleset_zero_rules(
        self, check_role: CheckRole, sample_rule: Rule, ruleset_metadata: RuleSetMetadata
    ) -> None:
        """Test drafting ruleset with zero rule count.

        Args:
            check_role (CheckRole): CheckRole fixture
            sample_rule (Rule): Sample rule fixture
            ruleset_metadata (RuleSetMetadata): Metadata fixture
        """
        requirement = "Simple requirement"

        router = return_model_json_string(sample_rule, ruleset_metadata)

        with install_router(router):
            result = await check_role.draft_ruleset(requirement, rule_count=0)

            assert result is not None
            assert len(result.rules) == 1  # Should default to single rule

    @pytest.mark.asyncio
    async def test_empty_ruleset(self, check_role: CheckRole) -> None:
        """Test operations with empty ruleset.

        Args:
            check_role (CheckRole): CheckRole fixture
        """
        empty_ruleset = RuleSet(name="Empty Ruleset", description="A ruleset with no rules", rules=[])

        router = return_string("null")

        with install_router(router):
            result = await check_role.check_string("Any content", empty_ruleset)

            assert result is not None
            assert isinstance(result, list)
            assert len(result) == 0
