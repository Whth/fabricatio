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

    def save_checkpoint(self, msg: str) -> str:
        """Save a checkpoint."""
        return SHADOW_REPO_MANAGER.save(ok(self.worktree_dir), msg)

    def drop_checkpoint(self) -> None:
        """Drop the checkpoint."""
        SHADOW_REPO_MANAGER.drop(ok(self.worktree_dir))

    def rollback(self, commit_id: str, file_path: Path | str) -> None:
        """Rollback to a checkpoint."""
        SHADOW_REPO_MANAGER.rollback(ok(self.worktree_dir), commit_id, file_path)

    def reset_to_checkpoint(self, commit_id: str) -> None:
        """Reset the checkpoint."""
        SHADOW_REPO_MANAGER.reset(ok(self.worktree_dir), commit_id)

    def get_file_diff(self, commit_id: str, file_path: Path | str) -> str:
        """Get the diff for a specific file at a given commit."""
        return SHADOW_REPO_MANAGER.get_file_diff(ok(self.worktree_dir), commit_id, file_path)
