"""This module contains the capabilities for the checkpoint."""

from abc import ABC
from pathlib import Path

from fabricatio_core.capabilities.usages import UseLLM
from pydantic import Field

from fabricatio_checkpoint.inited_manager import SHADOW_REPO_MANAGER


class Checkpoint(UseLLM, ABC):
    """This class contains the capabilities for the checkpoint."""

    worktree_dir: Path = Field(default_factory=Path.cwd)
    """The worktree directory. Use the current working directory by default."""

    def save_checkpoint(self, msg: str = "Changes") -> str:
        """Save a checkpoint."""
        return SHADOW_REPO_MANAGER.save(self.worktree_dir, msg)

    def drop_checkpoint(self) -> None:
        """Drop the checkpoint."""
        SHADOW_REPO_MANAGER.drop(self.worktree_dir)

    def rollback(self, commit_id: str, file_path: Path | str) -> None:
        """Rollback to a checkpoint."""
        SHADOW_REPO_MANAGER.rollback(self.worktree_dir, commit_id, file_path)

    def reset_to_checkpoint(self, commit_id: str) -> None:
        """Reset the checkpoint."""
        SHADOW_REPO_MANAGER.reset(self.worktree_dir, commit_id)

    def get_file_diff(self, commit_id: str, file_path: Path | str) -> str:
        """Get the diff for a specific file at a given commit."""
        return SHADOW_REPO_MANAGER.get_file_diff(self.worktree_dir, commit_id, file_path)
