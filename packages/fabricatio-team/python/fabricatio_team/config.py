"""Module containing configuration classes for fabricatio-team."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class TeamConfig:
    """Configuration for fabricatio-team."""


team_config = CONFIG.load("team", TeamConfig)

__all__ = ["team_config"]
