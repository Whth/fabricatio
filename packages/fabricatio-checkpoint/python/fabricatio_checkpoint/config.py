"""Module containing configuration classes for fabricatio-checkpoint."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class CheckpointConfig:
    """Configuration for fabricatio-checkpoint."""


checkpoint_config = CONFIG.load("checkpoint", CheckpointConfig)

__all__ = ["checkpoint_config"]
