"""Test propose method."""

from typing import List

import pytest
from fabricatio_core import Task
from fabricatio_core.models.generic import SketchedAble
from fabricatio_core.utils import ok
from fabricatio_mock.models.mock_role import ProposeTestRole
from fabricatio_mock.models.mock_router import return_model_json_string
from fabricatio_mock.utils import install_router
from litellm import Router


class TestModel(SketchedAble):
    """Test model for testing propose method."""

    attr1: str
    attr2: int
    attr: List[str]


@pytest.fixture
def mock_router(ret_value: SketchedAble) -> Router:
    """Fixture to create a mocked router with predefined response.

    Args:
        ret_value: The value to be returned by the mocked completion
    Returns:
        Configured AsyncMock router object
    """
    return return_model_json_string(ret_value)


@pytest.fixture(autouse=True)
def role() -> ProposeTestRole:
    """Fixture to create a role with propose capability."""
    return ProposeTestRole()


@pytest.mark.parametrize("ret_value", [Task(name="test"), TestModel(attr1="test", attr2=1, attr=["test"])])
@pytest.mark.asyncio
async def test_propose(mock_router: Router, ret_value: SketchedAble, role: ProposeTestRole) -> None:
    """Test propose method."""
    with install_router(mock_router):
        proposal = ok(await role.propose(ret_value.__class__, "test"))
        assert proposal.model_dump_json() == ret_value.model_dump_json()

        proposals = ok(await role.propose(ret_value.__class__, ["test"] * 3))

        assert all(ok(proposal).model_dump_json() == ret_value.model_dump_json() for proposal in proposals)
        assert len(proposals) == 3
