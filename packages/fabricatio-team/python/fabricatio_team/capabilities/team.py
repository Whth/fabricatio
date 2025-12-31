"""This module contains the capabilities for the team."""

from abc import ABC
from typing import Iterable, List, Optional, Self, Set

from fabricatio_core import Role, logger
from fabricatio_core.models.generic import ScopedConfig
from fabricatio_core.models.role import RoleName, get_registered_role
from fabricatio_core.utils import ok
from more_itertools.recipes import flatten
from pydantic import Field


class Cooperate(ScopedConfig, ABC):
    """Cooperate class provides the capability to manage a set of team_member roles."""

    team_roster: Optional[Set[RoleName]] = Field(default=None)
    """A set of Role instances representing the team_member."""
    other_member_roster: Optional[Set[RoleName]] = Field(default=None)
    """A set of Role names representing other team members."""

    def update_team_roster(self, team_member: Iterable[RoleName], myself: Optional[RoleName] = None) -> Self:
        """Updates the team_member set with the given iterable of roles.

        Args:
            team_member: An iterable of Role instances to set as the new team_member.
            myself: The role name of the current role.

        Returns:
            Self: The updated instance with refreshed team_member.
        """
        new_team = set(team_member)
        self.team_roster = new_team

        if myself is not None:
            self.other_member_roster = new_team - {myself}

        return self

    def update_team_roster_with_roles(self, team_member: Iterable[Role]) -> Self:
        """Updates the team_member set with the given iterable of roles."""
        return self.update_team_roster([mate.name for mate in team_member])

    def consult_team_member(self, name: str) -> Role | None:
        """Returns the team_member with the given name."""
        if self.team_roster is None:
            logger.warn("The `team_members` is still unset!")
            return None
        team_member_name = next((mate for mate in self.team_roster if mate == name), None)
        if team_member_name is None:
            logger.warn(f"Team member `{name}` not found in the team!")
            return None
        return get_registered_role(team_member_name)

    @property
    def team_members(self) -> List[Role]:
        """Returns the team_member set."""
        return [get_registered_role(mate) for mate in ok(self.team_roster)]

    def gather_accept_events(self) -> List[str]:
        """Gathers all accept_events from all team_member roles."""
        return list(flatten(m.accept_events for m in self.team_members))
