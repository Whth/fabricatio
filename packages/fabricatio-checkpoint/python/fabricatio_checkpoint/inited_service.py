"""Module containing the shadow repo manager."""

from fabricatio_core.decorators import once

from fabricatio_checkpoint.config import checkpoint_config
from fabricatio_checkpoint.rust import CheckpointService


@once
def get_checkpoint_service() -> CheckpointService:
    """Get the singleton instance of the ShadowRepoManager."""
    return CheckpointService(stores_root=checkpoint_config.checkpoint_dir, cache_size=checkpoint_config.cache_size)


__all__ = ["get_checkpoint_service"]
