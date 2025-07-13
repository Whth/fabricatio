"""This module contains the models for the team."""

from dataclasses import dataclass
from typing import Self, Set

from fabricatio_core import Role, logger

from fabricatio_team.capabilities.team import Cooperate


@dataclass
class Team:
    """A class representing a team of mates.

    Example:
        .. code-block:: python
            from fabricatio_core import Role
            from fabricatio_team.models import Team

            # Create roles
            role1 = Role(name="Role1", capabilities=["cap1"])
            role2 = Role(name="Role2", capabilities=["cap2"])

            class MyRole(InformedRole):
                ...

            # Create a team
            team = Team(teammates={role1, role2}).join(MyRole(name="MyRole"))

            # Inform the team members about each other accordingly
            team.inform()


    """

    teammates: Set[Role]
    """A set of Mate instances representing the teammates in the team."""

    def join(self, teammate: Role) -> Self:
        """Adds a teammate to the team.

        Args:
            teammate: The mate to be added to the team.

        Raises:
            ValueError: If the teammate is already a member of the team.
        """
        if teammate in self.teammates:
            raise ValueError(f"`{teammate.name}` is already a member of the team")
        self.teammates.add(teammate)
        return self

    def resign(self, teammate: Role) -> Self:
        """Removes a teammate from the team.

        Args:
            teammate: The mate to be removed from the team.

        Raises:
            ValueError: If the teammate is not a member of the team.
        """
        if teammate not in self.teammates:
            raise ValueError(f"`{teammate.name}` is not a member of the team.")
        self.teammates.remove(teammate)
        return self

    def inform(self) -> Self:
        r"""Updates teammates information for informed members.

        Returns:
            The updated team instance.
        """
        member_to_inform = [member for member in self.teammates if isinstance(member, Cooperate)]

        if not member_to_inform:
            logger.warning("No members that need to be informed found in the team. Skipping...")
            return self

        for m in member_to_inform:
            m.update_teammates(self.teammates)
            logger.debug(f"{m.name} is now informed with teammates: {m.teammate_roster()}")
        return self
