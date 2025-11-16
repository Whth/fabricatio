"""Module containing the shadow repo manager."""

from fabricatio_checkpoint.config import checkpoint_config
from fabricatio_checkpoint.rust import ShadowRepoManager

SHADOW_REPO_MANAGER = ShadowRepoManager(
    shadow_root=checkpoint_config.checkpoint_dir, cache_size=checkpoint_config.cache_size
)


__all__ = ["SHADOW_REPO_MANAGER"]
