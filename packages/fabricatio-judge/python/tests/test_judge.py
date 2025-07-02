"""Test the judge method."""

from typing import Any, Dict, List, Optional

import pytest
from fabricatio_core.models.generic import SketchedAble
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.utils import ok
from fabricatio_judge.capabilities.advanced_judge import EvidentlyJudge, VoteJudge
from fabricatio_judge.models.judgement import JudgeMent
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_model_json_string
from fabricatio_mock.utils import install_router
from litellm import Router
from pydantic import Field


def jd(passed: bool | List[bool]) -> JudgeMent | List[JudgeMent]:
    """Create JudgeMent or list of JudgeMents with test data.

    Args:
        passed (bool | List[bool]): Boolean or list of booleans indicating judgment result

    Returns:
        JudgeMent | List[JudgeMent]: JudgeMent object or list of JudgeMent objects
    """
    if isinstance(passed, list):
        return [jd(judgement) for judgement in passed]
    return JudgeMent(issue_to_judge="test", affirm_evidence=["test"], deny_evidence=["test"], final_judgement=passed)


class JudgeRole(LLMTestRole, EvidentlyJudge):
    """A class that tests the judge method."""

    pass


@pytest.fixture
def router(ret_value: SketchedAble) -> Router:
    """Create a router fixture that returns a specific value.

    Args:
        ret_value (SketchedAble): Value to be returned by the router

    Returns:
        Router: Router instance
    """
    return return_model_json_string(ret_value)


@pytest.fixture
def role() -> JudgeRole:
    """Create a JudgeRole instance for testing.

    Returns:
        JudgeRole: JudgeRole instance
    """
    return JudgeRole()


@pytest.mark.parametrize(
    ("ret_value", "prompt"),
    [
        (
            jd(True),
            "positive",
        ),
        (
            jd(False),
            "negative",
        ),
    ],
)
@pytest.mark.asyncio
async def test_judge(router: Router, role: JudgeRole, ret_value: SketchedAble, prompt: str) -> None:
    """Test the judge method with positive and negative cases.

    Args:
        router (Router): Mocked router fixture
        role (JudgeRole): JudgeRole fixture
        ret_value (SketchedAble): Expected return value
        prompt (str): Input prompt for testing
    """
    with install_router(router):
        jud = ok(await role.evidently_judge(prompt))
        assert jud.model_dump_json() == ret_value.model_dump_json()
        assert bool(jud) == bool(ret_value)

        jud_sq = ok(await role.propose(ret_value.__class__, ["test"] * 3))

        assert all(ok(proposal).model_dump_json() == ret_value.model_dump_json() for proposal in jud_sq)
        assert all(bool(proposal) == bool(ret_value) for proposal in jud_sq)
        assert len(jud_sq) == 3


class VoteJudgeRole(LLMTestRole, VoteJudge):
    """A class that tests the vote_judge method with different configurations.

    The class has predefined voting weights and thresholds for testing purposes.
    """

    vote_llm: Dict[float, ValidateKwargs[JudgeMent]] = Field(
        default_factory=lambda: {
            0.5: {"temperature": 0.5},
            0.7: {"temperature": 0.7, "model": "openai/gpt-3.5-turbo"},
            0.9: {"temperature": 0.9},
        }
    )
    vote_pass_threshold: float = 0.5  # Default threshold


# Fixtures
@pytest.fixture
def vote_role() -> VoteJudgeRole:
    """Create a VoteJudgeRole instance for testing.

    Returns:
        VoteJudgeRole: VoteJudgeRole instance
    """
    return VoteJudgeRole()


# Helper to generate a mock router returning specific judgments
def make_vote_router(judgments: List[JudgeMent]) -> Router:
    """Create a router that returns predefined judgments.

    Args:
        judgments (List[JudgeMent]): List of judgments to be returned

    Returns:
        Router: Router instance
    """
    return return_model_json_string(*judgments)


# Test data
class TestCase:
    """Test case class for vote_judge method."""

    def __init__(
        self,
        judgments: List[Dict[str, Any]],
        threshold: Optional[float],
        expected_result: bool,
    ) -> None:
        """Initialize test case with judgments, threshold and expected result.

        Args:
            judgments (List[Dict[str, Any]]): List of judgment dictionaries
            threshold (Optional[float]): Pass threshold for voting
            expected_result (bool): Expected outcome of the vote
        """
        self.judgments = [JudgeMent(**j) for j in judgments]
        self.threshold = threshold
        self.expected_result = expected_result


# Parametrized test cases
vote_test_cases = [
    # Case 1: Two out of three votes pass (threshold 0.5)
    TestCase(
        judgments=[
            {"final_judgement": True, "affirm_evidence": ["test"], "deny_evidence": ["test"], "issue_to_judge": "test"},
            {"final_judgement": True, "affirm_evidence": ["test"], "deny_evidence": ["test"], "issue_to_judge": "test"},
            {
                "final_judgement": False,
                "affirm_evidence": ["test"],
                "deny_evidence": ["test"],
                "issue_to_judge": "test",
            },
        ],
        threshold=0.5,
        expected_result=True,
    ),
    # Case 2: Only one vote passes (threshold 0.5)
    TestCase(
        judgments=[
            {"final_judgement": True, "affirm_evidence": ["test"], "deny_evidence": ["test"], "issue_to_judge": "test"},
            {
                "final_judgement": False,
                "affirm_evidence": ["test"],
                "deny_evidence": ["test"],
                "issue_to_judge": "test",
            },
            {
                "final_judgement": False,
                "affirm_evidence": ["test"],
                "deny_evidence": ["test"],
                "issue_to_judge": "test",
            },
        ],
        threshold=0.5,
        expected_result=False,
    ),
    # Case 3: Exact threshold match
    TestCase(
        judgments=[
            {"final_judgement": True, "affirm_evidence": ["test"], "deny_evidence": ["test"], "issue_to_judge": "test"},
            {
                "final_judgement": False,
                "affirm_evidence": ["test"],
                "deny_evidence": ["test"],
                "issue_to_judge": "test",
            },
            {"final_judgement": True, "affirm_evidence": ["test"], "deny_evidence": ["test"], "issue_to_judge": "test"},
        ],
        threshold=0.666,
        expected_result=True,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", vote_test_cases)
async def test_vote_judge(vote_role: VoteJudgeRole, case: TestCase) -> None:
    """Test the vote_judge method with various judgment and threshold combinations.

    Args:
        vote_role (VoteJudgeRole): VoteJudgeRole fixture
        case (TestCase): Test case containing judgments, threshold and expected result
    """
    router = return_model_json_string(*case.judgments)
    with install_router(router):
        result = await vote_role.vote_judge("test prompt", vote_pass_threshold=case.threshold)
        assert result == case.expected_result


# Directly test resolve_pass logic
@pytest.mark.parametrize(
    ("weights", "judgments", "threshold", "expected"),
    [
        ([0.5, 0.7, 0.9], jd([True, True, False]), 0.5, True),
        ([0.5, 0.7, 0.9], jd([True, False, False]), 0.5, False),
        ([1.0, 1.0], jd([True, True]), 1.0, True),
        ([1.0, 1.0], jd([True, False]), 1.0, False),
    ],
)
def test_resolve_pass(weights: List[float], judgments: List[JudgeMent], threshold: float, expected: bool) -> None:
    """Test the static resolve_pass method directly with different weight and judgment combinations.

    Args:
        weights (List[float]): Weights for each vote
        judgments (List[JudgeMent]): List of judgments to evaluate
        threshold (float): Threshold to determine if the vote passes
        expected (bool): Expected result
    """
    assert VoteJudge.resolve_pass(weights, judgments, threshold) == expected


# Test empty prompt
@pytest.mark.asyncio
async def test_vote_judge_empty_prompt(vote_role: VoteJudgeRole) -> None:
    """Test the vote_judge method with an empty prompt input.

    Args:
        vote_role (VoteJudgeRole): VoteJudgeRole fixture
    """
    result = await vote_role.vote_judge([])  # type: ignore
    assert result == []


# Test multiple prompts
@pytest.mark.asyncio
async def test_vote_judge_multiple_prompts(vote_role: VoteJudgeRole) -> None:
    """Test the vote_judge method with multiple prompts.

    Args:
        vote_role (VoteJudgeRole): VoteJudgeRole fixture
    """
    judgments = [
        jd(True),
        jd(False),
    ] * 3
    router = return_model_json_string(*judgments)
    with install_router(router):
        result = await vote_role.vote_judge(["prompt1", "prompt2"])  # type: ignore
        assert result == [True, False]
