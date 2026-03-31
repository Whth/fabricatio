"""This module contains the capabilities for the workspace."""

from abc import ABC

from fabricatio_core.capabilities.usages import UseLLM


class Workspace(UseLLM, ABC):
    """This class contains the capabilities for the workspace."""

    async def workspace(self, **kwargs) -> None:
        """Todo"""
