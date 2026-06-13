"""Tests for the team."""

import pytest
from fabricatio_core import Role
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.utils import make_roles
from fabricatio_team.capabilities.team import Cooperate
from fabricatio_team.models.team import Team


class TeamRole(LLMTestRole, Cooperate):
    """Test role that combines LLMTestRole with Team for testing."""


@pytest.fixture
def team_role() -> TeamRole:
    """Create a TeamRole instance for testing."""
    return TeamRole()


# ---------------------------------------------------------------------------
# Cooperate capability tests
# ---------------------------------------------------------------------------


class TestCooperate:
    """Tests for Cooperate capability."""

    def test_update_and_members(self, team_role: TeamRole) -> None:
        """Test updating team members and verifying the members are stored correctly."""
        roles = make_roles(["alice", "bob", "carol"])
        team_role.update_team_roster_with_roles(roles)
        assert team_role.team_roster == {r.name for r in roles}
        assert isinstance(team_role.team_roster, set)

    def test_roster_returns_names(self, team_role: TeamRole) -> None:
        """Test that the team roster returns the correct names."""
        names = ["alice", "bob", "carol"]
        roles = make_roles(names)
        team_role.update_team_roster_with_roles(roles)
        roster = team_role.team_roster
        assert roster is not None
        assert sorted(roster) == sorted(names)

    def test_consult_team_member(self, team_role: TeamRole) -> None:
        """Test consulting a team member by name."""
        roles = make_roles(["alice", "bob"])
        team_role.update_team_roster_with_roles(roles)
        found = team_role.consult_team_member("alice")
        assert found is not None
        assert found.name == "alice"
        assert team_role.consult_team_member("nonexistent") is None

    def test_update_with_duplicates(self, team_role: TeamRole) -> None:
        """Test updating team members with duplicate roles."""
        roles = make_roles(["bob", "bob", "alice"])
        team_role.update_team_roster(roles)
        assert len(team_role.team_roster) == 2 or len({r.name for r in team_role.team_roster}) == 2

    def test_update_with_empty(self, team_role: TeamRole) -> None:
        """Test updating team members with an empty list."""
        team_role.update_team_roster([])
        assert team_role.team_roster == set()

    def test_update_roster_with_myself_excludes_self(self, team_role: TeamRole) -> None:
        """Test that other_member_roster excludes the 'myself' role."""
        roles = make_roles(["alice", "bob", "carol"])
        team_role.update_team_roster([r.name for r in roles], myself="alice")
        assert "alice" not in team_role.other_member_roster
        assert "bob" in team_role.other_member_roster
        assert "carol" in team_role.other_member_roster

    def test_team_members_property(self, team_role: TeamRole) -> None:
        """Test that team_members returns actual Role objects."""
        roles = make_roles(["alice", "bob"])
        team_role.update_team_roster_with_roles(roles)
        members = team_role.team_members
        assert len(members) == 2
        member_names = {m.name for m in members}
        assert member_names == {"alice", "bob"}

    def test_gather_accept_events(self, team_role: TeamRole) -> None:
        """Test gather_accept_events collects events from all members."""
        roles = make_roles(["alice", "bob"])
        team_role.update_team_roster_with_roles(roles)
        events = team_role.gather_accept_events()
        assert isinstance(events, list)


# ---------------------------------------------------------------------------
# Team model tests
# ---------------------------------------------------------------------------


class TestTeam:
    """Tests for Team dataclass."""

    def test_team_default_members_empty(self) -> None:
        """Test that Team starts with empty members."""
        team = Team()
        assert team.members == set()

    def test_team_join_by_role_name(self) -> None:
        """Test joining a team by role name string."""
        team = Team()
        result = team.join("alice")
        assert result is team
        assert "alice" in team.members

    def test_team_join_by_role_object(self) -> None:
        """Test joining a team by Role object."""
        role = Role(name="bob", description="test")
        team = Team()
        team.join(role)
        assert "bob" in team.members

    def test_team_join_duplicate_raises(self) -> None:
        """Test joining with a duplicate member raises ValueError."""
        team = Team()
        team.join("alice")
        with pytest.raises(ValueError, match="already a member"):
            team.join("alice")

    def test_team_resign(self) -> None:
        """Test resigning from a team."""
        team = Team(members={"alice", "bob"})
        result = team.resign("alice")
        assert result is team
        assert "alice" not in team.members
        assert "bob" in team.members

    def test_team_resign_by_role_object(self) -> None:
        """Test resigning by Role object."""
        role = Role(name="bob", description="test")
        team = Team(members={"alice", "bob"})
        team.resign(role)
        assert "bob" not in team.members

    def test_team_resign_non_member_raises(self) -> None:
        """Test resigning a non-member raises ValueError."""
        team = Team(members={"alice"})
        with pytest.raises(ValueError, match="not a member"):
            team.resign("bob")

    def test_team_chaining(self) -> None:
        """Test that join and resign support method chaining."""
        team = Team()
        result = team.join("alice").join("bob").resign("alice")
        assert result is team
        assert team.members == {"bob"}

    def test_team_inform_no_cooperate_members(self) -> None:
        """Test inform with no Cooperate members logs a warning and returns self."""
        team = Team(members=set())
        result = team.inform()
        assert result is team

    def test_team_dispatch_empty_team(self) -> None:
        """Test dispatch with empty team returns self."""
        team = Team(members=set())
        result = team.dispatch()
        assert result is team

    def test_team_members_set_initialization(self) -> None:
        """Test Team with pre-set members."""
        team = Team(members={"x", "y", "z"})
        assert len(team.members) == 3
        assert team.members == {"x", "y", "z"}
