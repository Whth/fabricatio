"""This module contains the capabilities for the team."""

from abc import ABC
from typing import Iterable, List, Self, Set

from fabricatio_core import Role
from pydantic import BaseModel, PrivateAttr


class Cooperate(BaseModel, ABC):
    """Cooperate class provides the capability to manage a set of team_member roles."""

    _team_members: Set[Role] = PrivateAttr(default_factory=set)
    """A set of Role instances representing the team_member."""

    def update_team_members(self, team_member: Iterable[Role]) -> Self:
        """Updates the team_member set with the given iterable of roles.

        Args:
            team_member: An iterable of Role instances to set as the new team_member.

        Returns:
            Self: The updated instance with refreshed team_member.
        """
        self._team_members.clear()
        self._team_members.update(team_member)
        return self

    @property
    def team_members(self) -> Set[Role]:
        """Returns the team_member set."""
        return self._team_members

    def team_roster(self) -> List[str]:
        """Returns the team_member roster."""
        return [mate.name for mate in self._team_members]

    def consult_team_member(self, name: str) -> Role | None:
        """Returns the team_member with the given name."""
        return next((mate for mate in self._team_members if mate.name == name), None)
