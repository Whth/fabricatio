"""Module containing configuration classes for fabricatio-checkpoint."""

from dataclasses import dataclass
from pathlib import Path

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class CheckpointConfig:
    """Configuration for fabricatio-checkpoint."""

    checkpoint_dir: Path = Path.home() / ".fabricatio-checkpoint"
    """Directory to store checkpoints. Aka the shadow repositories."""
    cache_size: int = 100
    """Maximum number of checkpoints to keep in memory."""


checkpoint_config = CONFIG.load("checkpoint", CheckpointConfig)

__all__ = ["checkpoint_config"]
