"""This module contains the capabilities for the team."""

from abc import ABC
from typing import Iterable, List, Self, Set

from fabricatio_core import Role
from pydantic import BaseModel, PrivateAttr


class Cooperate(BaseModel, ABC):
    """Cooperate class provides the capability to manage a set of teammate roles.

    Example:
        .. code-block:: python

            from fabricatio_core import Role
            from fabricatio_team.capabilities.team import Cooperate

            class MyRole(Cooperate,Role):
                pass

            class OtherRole(Role):
                ...
            my_role = MyRole()
            other_role = OtherRole()
            my_role.update_teammates([other_role])
            assert other_role in my_role.teammates
    """

    _teammates: Set[Role] = PrivateAttr(default_factory=set)
    """A set of Role instances representing the teammates."""

    def update_teammates(self, teammates: Iterable[Role]) -> Self:
        """Updates the teammates set with the given iterable of roles.

        Args:
            teammates: An iterable of Role instances to set as the new teammates.

        Returns:
            Self: The updated instance with refreshed teammates.
        """
        self._teammates.clear()
        self._teammates.update(teammates)
        return self

    @property
    def teammates(self) -> Set[Role]:
        """Returns the teammates set."""
        return self._teammates

    def teammate_roster(self) -> List[str]:
        """Returns the teammate roster."""
        return [mate.name for mate in self._teammates]

    def consult_teammate(self, name: str) -> Role | None:
        """Returns the teammate with the given name."""
        return next((mate for mate in self._teammates if mate.name == name), None)
