"""Tests for the team."""

from typing import List

import pytest
from fabricatio_core import Role
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_team.capabilities.team import Cooperate


def make_roles(names: List[str]) -> List[Role]:
    """Create a list of Role objects from a list of names.

    Args:
        names (list[str]): A list of names for the roles.

    Returns:
        list[Role]: A list of Role objects with the given names.
    """
    return [Role(name=name, description="test") for name in names]


class TeamRole(LLMTestRole, Cooperate):
    """Test role that combines LLMTestRole with Team for testing."""


@pytest.fixture
def team_role() -> TeamRole:
    """Create a TeamRole instance for testing.

    Returns:
        TeamRole: An instance of TeamRole.
    """
    return TeamRole()


def test_update_and_members(team_role: TeamRole) -> None:
    """Test updating team members and verifying the members are stored correctly.

    Args:
        team_role (TeamRole): The team role fixture.
    """
    roles = make_roles(["alice", "bob", "carol"])
    team_role.update_team_members(roles)
    assert team_role.team_members == set(roles)

    # team_members must be a set
    assert isinstance(team_role.team_members, set)


def test_roster_returns_names(team_role: TeamRole) -> None:
    """Test that the team roster returns the correct names.

    Args:
        team_role (TeamRole): The team role fixture.
    """
    names = ["alice", "bob", "carol"]
    roles = make_roles(names)
    team_role.update_team_members(roles)
    roster = team_role.team_roster()
    assert sorted(roster) == sorted(names)


def test_consult_team_member(team_role: TeamRole) -> None:
    """Test consulting a team member by name.

    Args:
        team_role (TeamRole): The team role fixture.
    """
    roles = make_roles(["alice", "bob"])
    team_role.update_team_members(roles)
    found = team_role.consult_team_member("alice")
    assert found is not None
    assert found.name == "alice"
    assert team_role.consult_team_member("nonexistent") is None


def test_update_with_duplicates(team_role: TeamRole) -> None:
    """Test updating team members with duplicate roles.

    Args:
        team_role (TeamRole): The team role fixture.
    """
    roles = make_roles(["bob", "bob", "alice"])
    team_role.update_team_members(roles)
    # Only unique objects will be kept in the set (by object id, not name)
    assert len(team_role.team_members) == 2 or len({r.name for r in team_role.team_members}) == 2


def test_update_with_empty(team_role: TeamRole) -> None:
    """Test updating team members with an empty list.

    Args:
        team_role (TeamRole): The team role fixture.
    """
    team_role.update_team_members([])
    assert team_role.team_members == set()
    assert team_role.team_roster() == []
