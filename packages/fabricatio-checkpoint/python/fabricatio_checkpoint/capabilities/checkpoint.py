"""This module contains the capabilities for the checkpoint."""

from abc import ABC
from pathlib import Path
from typing import Optional

from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.utils import ok

from fabricatio_checkpoint.inited_manager import SHADOW_REPO_MANAGER


class Checkpoint(UseLLM, ABC):
    """This class contains the capabilities for the checkpoint."""

    worktree_dir: Optional[Path] = None
    """The worktree directory."""

    def save(self, msg: str) -> str:
        """Save a checkpoint."""
        return SHADOW_REPO_MANAGER.save(ok(self.worktree_dir), msg)

    def rollback(self, commit_id: str, file_path: Path) -> None:
        """Rollback to a checkpoint."""
        SHADOW_REPO_MANAGER.rollback(ok(self.worktree_dir), commit_id, file_path)

    def reset(self, commit_id: str) -> None:
        """Reset the checkpoint."""
        SHADOW_REPO_MANAGER.reset(ok(self.worktree_dir), commit_id)
