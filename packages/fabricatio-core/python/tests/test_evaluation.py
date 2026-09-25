"""The evaluation modality: verdicts, choices, and ratings through the evaluation route group."""

import pytest
from fabricatio_core.capabilities.evaluate import UseEvaluation
from fabricatio_mock.constants import DUMMY_EVALUATION_GROUP
from fabricatio_mock.models.evaluation import EvaluationResponse
from fabricatio_mock.utils import setup_dummy_evaluations

STATE: str = "The invoices page has been down since 09:00 and support has not replied yet."
LEVELS: tuple[str, ...] = ("not at all", "somewhat", "completely")
CANDIDATES: dict[str, str | None] = {
    "billing": "money is involved",
    "outage": "the service is unavailable",
}


def _role() -> UseEvaluation:
    """A role that evaluates against the dummy group without reading or writing the cache."""
    return UseEvaluation(
        evaluation_send_to=DUMMY_EVALUATION_GROUP,
        evaluation_no_cache=True,
        evaluation_no_store=True,
    )


async def test_evaluate_verdict_answers_with_a_verdict() -> None:
    """A probability of yes at or above one half is a yes, anything below it a no."""
    setup_dummy_evaluations(EvaluationResponse.judged(0.93), EvaluationResponse.judged(0.1))
    role = _role()

    assert await role.evaluate_verdict(STATE, "Does this need an answer within the hour?") is True
    assert await role.evaluate_verdict(STATE, "Does this need an answer within the hour?") is False


async def test_evaluate_choice_answers_with_the_candidate_it_picked() -> None:
    """The pick comes back as the option itself, not as the distribution behind it."""
    setup_dummy_evaluations(EvaluationResponse.picked("outage", probabilities={"billing": 0.2, "outage": 0.8}))

    picked = await _role().evaluate_choice(STATE, "What kind of request is this?", CANDIDATES)

    assert picked == "outage"


async def test_evaluate_rating_answers_with_what_every_level_weighs() -> None:
    """A rating comes back as the criteria, each mapped to the probability the model gave it."""
    setup_dummy_evaluations(EvaluationResponse.rated({"not at all": 0.05, "somewhat": 0.3, "completely": 0.65}))

    rated = await _role().evaluate_rating(STATE, "How badly is the user blocked?", LEVELS)

    assert rated == pytest.approx({"not at all": 0.05, "somewhat": 0.3, "completely": 0.65})


async def test_an_answer_of_another_kind_is_refused() -> None:
    """Being answered with the wrong kind of answer is an error, not a mis-read value."""
    setup_dummy_evaluations(EvaluationResponse.picked("outage"))

    with pytest.raises(ValueError, match="rating question"):
        await _role().evaluate_rating(STATE, "How badly is the user blocked?", LEVELS)


async def test_a_choice_without_candidates_is_refused() -> None:
    """The API's own limit comes back as the reason, before anything is asked."""
    setup_dummy_evaluations(EvaluationResponse.picked("outage"))

    with pytest.raises(ValueError, match="at least one option"):
        await _role().evaluate_choice(STATE, "Which team owns this?", {})


async def test_a_state_that_is_not_text_is_refused() -> None:
    """The evaluation asks about text, so anything else is refused before it travels."""
    setup_dummy_evaluations(EvaluationResponse.judged(0.9))

    with pytest.raises(TypeError):
        await _role().evaluate_verdict({"message": STATE}, "Does this need an answer?")  # ty: ignore[invalid-argument-type]
