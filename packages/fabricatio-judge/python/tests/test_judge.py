"""Test the judge method."""

import tempfile
from pathlib import Path
from typing import Any

import pytest
from fabricatio_core import Role
from fabricatio_core.models.generic import SketchedAble
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.utils import ok
from fabricatio_judge.capabilities.advanced_judge import EvidentlyJudge, VisuallyJudge, VoteJudge
from fabricatio_judge.models.judgement import ImageVerdict, JudgeMent
from fabricatio_mock import MockScript, Value, make_test_role
from pydantic import Field


def jd(passed: bool | list[bool]) -> JudgeMent | list[JudgeMent]:
    """Create JudgeMent or list of JudgeMents with test data.

    Args:
        passed (bool | List[bool]): Boolean or list of booleans indicating judgment result

    Returns:
        JudgeMent | List[JudgeMent]: JudgeMent object or list of JudgeMent objects
    """
    if isinstance(passed, list):
        return [jd(judgement) for judgement in passed]
    return JudgeMent(issue_to_judge="test", affirm_evidence=["test"], deny_evidence=["test"], final_judgement=passed)


@pytest.fixture
def responses(ret_value: SketchedAble) -> MockScript:
    """Create mock router responses that return a specific value.

    Args:
        ret_value (SketchedAble): Value to be returned by the router

    Returns:
        MockScript: Scripted responses, one per call the test makes
    """
    return MockScript.from_values(
        Value.from_model(ret_value, name="judgement"),
        Value.from_model(ret_value, name="proposal 1"),
        Value.from_model(ret_value, name="proposal 2"),
        Value.from_model(ret_value, name="proposal 3"),
    )


@pytest.fixture
def role() -> Role:
    """Create the judge role under test.

    Returns:
        Role: Composed judge test role
    """
    return make_test_role(EvidentlyJudge, name="judge")


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
async def test_judge(responses: MockScript, role: Role, ret_value: SketchedAble, prompt: str) -> None:
    """Test the judge method with positive and negative cases.

    Args:
        responses (MockScript): Mocked router responses fixture
        role (Role): The judge role fixture
        ret_value (SketchedAble): Expected return value
        prompt (str): Input prompt for testing
    """
    with responses:
        jud = ok(await role.evidently_judge(prompt))
        assert jud.model_dump_json() == ret_value.model_dump_json()
        assert bool(jud) == bool(ret_value)

        jud_sq = ok(await role.propose(ret_value.__class__, ["test"] * 3))

        assert all(ok(proposal).model_dump_json() == ret_value.model_dump_json() for proposal in jud_sq)
        assert all(bool(proposal) == bool(ret_value) for proposal in jud_sq)
        assert len(jud_sq) == 3


class ScriptedVote(VoteJudge):
    """VoteJudge carrying the voting weights and pass threshold the vote tests script.

    ``VoteLLMConfig`` leaves ``vote_llm`` required, so the scripted preferences stay on a
    capability of their own instead of on the composed test role.
    """

    vote_llm: dict[float, ValidateKwargs[JudgeMent]] = Field(
        default_factory=lambda: {
            0.5: {"temperature": 0.5},
            0.7: {"temperature": 0.7},
            0.9: {"temperature": 0.9},
        },
    )
    vote_pass_threshold: float | None = 0.5  # Default threshold


# Fixtures
@pytest.fixture
def vote_role() -> Role:
    """Create the vote-judge role under test.

    Returns:
        Role: Composed vote-judge test role
    """
    return make_test_role(ScriptedVote, name="vote-judge")


# Helper to generate a script returning specific judgments
def vote_script(*judgments: JudgeMent) -> MockScript:
    """Create a script that returns predefined judgments in order.

    Args:
        *judgments (JudgeMent): Judgments to be returned

    Returns:
        MockScript: Scripted responses, one per declared judgment
    """
    return MockScript.from_values(
        *(Value.from_model(judgment, name=f"vote {position}") for position, judgment in enumerate(judgments, start=1))
    )


# Test data
class Case:
    """Test case class for vote_judge method."""

    def __init__(
        self,
        judgments: list[dict[str, Any]],
        threshold: float | None,
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
    Case(
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
    Case(
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
    Case(
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
async def test_vote_judge(vote_role: Role, case: Case) -> None:
    """Test the vote_judge method with various judgment and threshold combinations.

    Args:
        vote_role (Role): The vote-judge role fixture
        case (Case): Test case containing judgments, threshold and expected result
    """
    with vote_script(*case.judgments):
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
def test_resolve_pass(weights: list[float], judgments: list[JudgeMent], threshold: float, expected: bool) -> None:
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
async def test_vote_judge_empty_prompt(vote_role: Role) -> None:
    """Test the vote_judge method with an empty prompt input.

    Args:
        vote_role (Role): The vote-judge role fixture
    """
    result = await vote_role.vote_judge([])  # type: ignore[arg-type]
    assert result == []


# Test multiple prompts
@pytest.mark.asyncio
async def test_vote_judge_multiple_prompts(vote_role: Role) -> None:
    """Test the vote_judge method with multiple prompts.

    Args:
        vote_role (Role): The vote-judge role fixture
    """
    judgments = [
        jd(True),
        jd(False),
    ] * 3
    with vote_script(*judgments):
        result = await vote_role.vote_judge(["prompt1", "prompt2"])  # type: ignore[arg-type]
        assert result == [True, False]


def iv(passed: bool) -> ImageVerdict:
    """Create an ImageVerdict with test data.

    Args:
        passed (bool): Whether the verdict passes

    Returns:
        ImageVerdict: The verdict under test
    """
    return ImageVerdict(
        issue_to_judge="test",
        affirm_evidence=["clean render"] if passed else [],
        deny_evidence=[] if passed else ["drift"],
        final_judgement=passed,
        glitch_reasons=[] if passed else ["extra finger"],
        coherence_reasons=[] if passed else ["wrong background"],
    )


@pytest.fixture
def visual_role() -> Role:
    """Create the visual-judge role under test.

    Returns:
        Role: Composed visual-judge test role
    """
    return make_test_role(VisuallyJudge, name="visual-judge")


@pytest.mark.parametrize("passed", [True, False])
@pytest.mark.asyncio
async def test_visually_judge(passed: bool, visual_role: Role) -> None:
    """Test visually_judge with a mocked router and a real PNG file.

    Args:
        passed (bool): Whether the mocked verdict passes
        visual_role (Role): The role under test
    """
    expected = iv(passed)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
        handle.write(b"\x89PNG\r\n\x1a\nfake-bytes")
        image_path = Path(handle.name)
    try:
        with MockScript.from_values(Value.from_model(expected, name="image verdict")):
            verdict = ok(await visual_role.visually_judge(image_path, issue_to_judge="test"))
            assert verdict.model_dump_json() == expected.model_dump_json()
            assert bool(verdict) == passed
    finally:
        image_path.unlink()


@pytest.mark.asyncio
async def test_visually_judge_missing_image(visual_role: Role) -> None:
    """Test visually_judge fails loudly on a missing image path.

    Args:
        visual_role (Role): The role under test
    """
    verdict = await visual_role.visually_judge(Path("Z:/definitely/missing.png"), issue_to_judge="test")
    assert verdict is None


@pytest.mark.parametrize(
    ("verdict", "expected_feedback"),
    [
        (iv(True), ""),
        (iv(False), "extra finger; wrong background"),
    ],
)
def test_image_verdict_feedback(verdict: ImageVerdict, expected_feedback: str) -> None:
    """Test the feedback property joins reasons and stays empty on pass.

    Args:
        verdict (ImageVerdict): The verdict under test
        expected_feedback (str): The expected feedback string
    """
    assert verdict.feedback == expected_feedback
