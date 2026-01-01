"""Tests for the team."""

import pytest
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.utils import make_roles
from fabricatio_team.capabilities.team import Cooperate


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
    team_role.update_team_roster_with_roles(roles)
    assert team_role.team_roster == {r.name for r in roles}

    # team_members must be a set
    assert isinstance(team_role.team_roster, set)


def test_roster_returns_names(team_role: TeamRole) -> None:
    """Test that the team roster returns the correct names.

    Args:
        team_role (TeamRole): The team role fixture.
    """
    names = ["alice", "bob", "carol"]
    roles = make_roles(names)
    team_role.update_team_roster_with_roles(roles)
    roster = team_role.team_roster
    assert roster is not None
    assert sorted(roster) == sorted(names)


def test_consult_team_member(team_role: TeamRole) -> None:
    """Test consulting a team member by name.

    Args:
        team_role (TeamRole): The team role fixture.
    """
    roles = make_roles(["alice", "bob"])
    team_role.update_team_roster_with_roles(roles)
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
    team_role.update_team_roster(roles)
    # Only unique objects will be kept in the set (by object id, not name)
    assert len(team_role.team_roster) == 2 or len({r.name for r in team_role.team_roster}) == 2


def test_update_with_empty(team_role: TeamRole) -> None:
    """Test updating team members with an empty list.

    Args:
        team_role (TeamRole): The team role fixture.
    """
    team_role.update_team_roster([])
    assert team_role.team_roster == set()
