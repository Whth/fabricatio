"""This module contains the models for the team."""

from dataclasses import dataclass, field
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

            # define the role that needs the member info
            class MyRole(Cooperate):
                ...

            # Create a team
            team = Team(members={role1, role2}).join(MyRole(name="MyRole"))

            # Inform the team members about each other accordingly
            team.inform()

    """

    members: Set[Role] = field(default_factory=set)
    """The team members."""

    def join(self, teammate: Role) -> Self:
        """Adds a teammate to the team.

        Args:
            teammate: The mate to be added to the team.

        Raises:
            ValueError: If the teammate is already a member of the team.
        """
        if teammate in self.members:
            raise ValueError(f"`{teammate.name}` is already a member of the team")
        self.members.add(teammate)
        return self

    def resign(self, teammate: Role) -> Self:
        """Removes a teammate from the team.

        Args:
            teammate: The mate to be removed from the team.

        Raises:
            ValueError: If the teammate is not a member of the team.
        """
        if teammate not in self.members:
            raise ValueError(f"`{teammate.name}` is not a member of the team.")
        self.members.remove(teammate)
        return self

    def inform(self) -> Self:
        r"""Updates teammates information for informed members.

        Returns:
            The updated team instance.
        """
        # only the members have slot to store member info.
        member_to_inform = [member for member in self.members if isinstance(member, Cooperate)]

        if not member_to_inform:
            logger.warn("No members that need to be informed found in the team. Skipping...")
            return self

        for m in member_to_inform:
            m.update_team_members(self.members)
            logger.debug(f"{m.name} is now informed with members: {m.team_roster()}")
        return self

    def dispatch(self, resolve_config: bool = True) -> Self:
        """Dispatches the team members.

        Returns:
            The updated team instance.
        """
        for m in self.members:
            if resolve_config:
                m.resolve_configuration()
            m.dispatch()
        return self
