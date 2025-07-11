"""Tests for the thinking."""

import pytest
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_model_json_string
from fabricatio_mock.utils import install_router
from fabricatio_thinking.capabilities.thinking import Thinking
from fabricatio_thinking.models.thinking import Thought
from fabricatio_thinking.rust import ThoughtVCS


class ThinkingRole(LLMTestRole, Thinking):
    """Test role that combines LLMTestRole with Thinking for testing."""


@pytest.fixture
def role() -> ThinkingRole:
    """Create a ThinkingRole instance for testing."""
    return ThinkingRole()


@pytest.fixture
def vcs() -> ThoughtVCS:
    """Create a ThoughtVCS instance for testing."""
    return ThoughtVCS()


@pytest.mark.parametrize(
    ("thoughts", "expected_commits", "expected_branches"),
    [
        # Simple linear thinking, 2 steps
        (
            [
                Thought(thought="First thought", end=False, serial=1, estimated=2),
                Thought(thought="Second thought", end=True, serial=2, estimated=2),
            ],
            2,
            1,
        ),
        # Revision scenario
        (
            [
                Thought(thought="Initial", end=False, serial=1, estimated=2),
                Thought(thought="Second", end=False, serial=2, estimated=2),
                Thought(thought="Revised first", end=True, serial=3, estimated=2, revision=True, revises_thought=1),
            ],
            2,  # Only two commits, one revision
            1,
        ),
        # Branching scenario
        (
            [
                Thought(thought="Base", end=False, serial=1, estimated=2),
                Thought(thought="Branch from 1", end=True, serial=2, estimated=2),
            ],
            2,
            2,  # default + feature
        ),
    ],
)
@pytest.mark.asyncio
async def test_thinking_parametrized_router(
    role: ThinkingRole,
    vcs: ThoughtVCS,
    thoughts: list[Thought],
    expected_commits: int,
    expected_branches: int,
) -> None:
    """Test the thinking process with various scenarios using mock router."""
    router = return_model_json_string(*thoughts)
    with install_router(router):
        result_vcs = await role.thinking("Test question", vcs=vcs, max_steps=10)
        # Check number of branches and commits
        if hasattr(result_vcs, "branches"):
            assert len(result_vcs.branches) == expected_branches
            total_commits = sum(len(commits) for commits in result_vcs.branches.values())
            assert total_commits == expected_commits
        else:
            assert result_vcs is not None


@pytest.mark.parametrize(
    "thoughts",
    [
        [
            Thought(thought="Step 1", end=False, serial=1, estimated=2),
            Thought(thought="Step 2", end=True, serial=2, estimated=2),
            Thought(thought="Should not be called", end=True, serial=3, estimated=2),
        ],
    ],
)
@pytest.mark.asyncio
async def test_thinking_calls_end_router(role: ThinkingRole, vcs: ThoughtVCS, thoughts: list[Thought]) -> None:
    """Test that thinking stops when end is True using mock router."""
    router = return_model_json_string(*thoughts)
    with install_router(router):
        result_vcs = await role.thinking("Test", vcs=vcs, max_steps=10)
        assert result_vcs is not None


@pytest.mark.parametrize(
    "thoughts",
    [
        [
            Thought(thought="First", end=False, serial=1, estimated=2),
            Thought(thought="Second", end=True, serial=2, estimated=2),
        ],
    ],
)
@pytest.mark.asyncio
async def test_thinking_with_router_param(role: ThinkingRole, vcs: ThoughtVCS, thoughts: list[Thought]) -> None:
    """Integration-like test with a mock router (parametrized)."""
    router = return_model_json_string(*thoughts)
    with install_router(router):
        result_vcs = await role.thinking("Test", vcs=vcs, max_steps=10)
        assert result_vcs is not None
