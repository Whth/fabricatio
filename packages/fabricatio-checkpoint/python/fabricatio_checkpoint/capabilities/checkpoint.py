"""This module contains the capabilities for the checkpoint."""

from abc import ABC
from pathlib import Path

from fabricatio_core.capabilities.usages import UseLLM
from pydantic import Field

from fabricatio_checkpoint.inited_manager import get_shadow_repo_manager


class Checkpoint(UseLLM, ABC):
    """This class contains the capabilities for the checkpoint."""

    worktree_dir: Path = Field(default_factory=Path.cwd)
    """The worktree directory. Use the current working directory by default."""

    def save_checkpoint(self, msg: str = "Changes") -> str:
        """Save a checkpoint."""
        return get_shadow_repo_manager().save(self.worktree_dir, msg)

    def drop_checkpoint(self) -> None:
        """Drop the checkpoint."""
        get_shadow_repo_manager().drop(self.worktree_dir)

    def rollback(self, commit_id: str, file_path: Path | str) -> None:
        """Rollback to a checkpoint."""
        get_shadow_repo_manager().rollback(self.worktree_dir, commit_id, file_path)

    def reset_to_checkpoint(self, commit_id: str) -> None:
        """Reset the checkpoint."""
        get_shadow_repo_manager().reset(self.worktree_dir, commit_id)

    def get_file_diff(self, commit_id: str, file_path: Path | str) -> str:
        """Get the diff for a specific file at a given commit."""
        return get_shadow_repo_manager().get_file_diff(self.worktree_dir, commit_id, file_path)
