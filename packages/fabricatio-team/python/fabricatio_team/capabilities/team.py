"""This module contains the capabilities for the team."""

from abc import ABC
from typing import Iterable, List, Optional, Self, Set

from fabricatio_core import Role, logger
from fabricatio_core.models.generic import ScopedConfig
from fabricatio_core.utils import ok
from more_itertools.recipes import flatten
from pydantic import Field


class Cooperate(ScopedConfig, ABC):
    """Cooperate class provides the capability to manage a set of team_member roles."""

    team_members: Optional[Set[Role]] = Field(default=None)
    """A set of Role instances representing the team_member."""

    def update_team_members(self, team_member: Iterable[Role]) -> Self:
        """Updates the team_member set with the given iterable of roles.

        Args:
            team_member: An iterable of Role instances to set as the new team_member.

        Returns:
            Self: The updated instance with refreshed team_member.
        """
        if self.team_members is None:
            self.team_members = set(team_member)
            return self
        self.team_members.clear()
        self.team_members.update(team_member)
        return self

    def team_roster(self) -> List[str]:
        """Returns the team_member roster."""
        if self.team_members is None:
            logger.warn("The `team_members` is still unset!")
            return []
        return [mate.name for mate in self.team_members]

    def consult_team_member(self, name: str) -> Role | None:
        """Returns the team_member with the given name."""
        if self.team_members is None:
            logger.warn("The `team_members` is still unset!")
            return None
        return next((mate for mate in self.team_members if mate.name == name), None)

    def gather_accept_events(self) -> List[str]:
        """Gathers all accept_events from all team_member roles."""
        return list(flatten(mate.accept_events for mate in ok(self.team_members, "Team member not specified!")))
