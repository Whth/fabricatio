"""This module contains the capabilities for the checkpoint."""

from abc import ABC
from pathlib import Path
from typing import Optional, Self

from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.utils import ok
from pydantic import Field, PrivateAttr

from fabricatio_checkpoint.inited_service import get_checkpoint_service
from fabricatio_checkpoint.rust import CheckPointStore


class Checkpoint(UseLLM, ABC):
    """This class contains the capabilities for the checkpoint."""

    worktree_dir: Path = Field(default_factory=Path.cwd)
    """The worktree directory. Use the current working directory by default."""

    _checkpoint_store: Optional[CheckPointStore] = PrivateAttr(None)

    def mount_checkpoint_store(self, checkpoint_store: Optional[CheckPointStore] = None) -> Self:
        """Mount a checkpoint store to the capability."""
        self._checkpoint_store = checkpoint_store or get_checkpoint_service().get_store(self.worktree_dir)
        return self

    def unmount_checkpoint_store(self) -> Self:
        """Unmount the checkpoint store."""
        self._checkpoint_store = None
        return self

    def access_checkpoint_store(self, fallback_default: Optional[CheckPointStore] = None) -> CheckPointStore:
        """Access the checkpoint store."""
        if self._checkpoint_store is None and fallback_default is not None:
            self.mount_checkpoint_store(fallback_default)
        return ok(self._checkpoint_store, "Checkpoint store is not mounted.")

    def save_checkpoint(self, msg: str = "Changes") -> str:
        """Save a checkpoint."""
        return self.access_checkpoint_store().save(msg)

    def rollback(self, commit_id: str, file_path: Path | str) -> None:
        """Rollback to a checkpoint."""
        self.access_checkpoint_store().rollback(commit_id, file_path)

    def reset_to_checkpoint(self, commit_id: str) -> None:
        """Reset the checkpoint."""
        self.access_checkpoint_store().reset(commit_id)

    def get_file_diff(self, commit_id: str, file_path: Path | str) -> str:
        """Get the diff for a specific file at a given commit."""
        return self.access_checkpoint_store().get_file_diff(commit_id, file_path)
