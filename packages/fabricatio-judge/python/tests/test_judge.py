"""Test the judge method."""

import pytest
from fabricatio_core.models.generic import SketchedAble
from fabricatio_core.utils import ok
from fabricatio_judge.capabilities.advanced_judge import AdvancedJudge
from fabricatio_judge.models.judgement import JudgeMent
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_model_json_string
from fabricatio_mock.utils import install_router
from litellm import Router


class JudgeRole(LLMTestRole, AdvancedJudge):
    """A class that tests the judge method."""


@pytest.fixture
def router(ret_value: SketchedAble) -> Router:
    """Returns the router instance."""
    return return_model_json_string(ret_value)


@pytest.fixture
def role() -> JudgeRole:
    """Returns the role instance."""
    return JudgeRole()


@pytest.mark.parametrize(
    "ret_value",
    [
        JudgeMent(issue_to_judge="test", affirm_evidence=["test"], deny_evidence=["test"], final_judgement=True),
        JudgeMent(issue_to_judge="test", affirm_evidence=["test"], deny_evidence=["test"], final_judgement=False),
    ],
)
@pytest.mark.asyncio
async def test_judge(router: Router, role: JudgeRole, ret_value: SketchedAble) -> None:
    """Test the judge method."""
    with install_router(router):
        proposal = ok(await role.propose(ret_value.__class__, "test"))
        assert proposal.model_dump_json() == ret_value.model_dump_json()

        proposals = ok(await role.propose(ret_value.__class__, ["test"] * 3))

        assert all(ok(proposal).model_dump_json() == ret_value.model_dump_json() for proposal in proposals)
        assert len(proposals) == 3
