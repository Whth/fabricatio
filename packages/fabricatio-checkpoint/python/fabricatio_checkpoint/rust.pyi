"""Rust bindings for the Rust API of fabricatio-checkpoint."""

from pathlib import Path
from typing import Optional

class ShadowRepoManager:
    """Manages shadow Git repositories for file checkpointing.

    A shadow repository manager creates and maintains separate bare Git repositories
    for each worktree directory. This enables independent version control and checkpointing
    without interfering with any existing Git repositories in the worktree.
    """

    def __init__(self, shadow_root: Path, cache_size: int) -> None:
        """Creates a new ShadowRepoManager instance.

        Args:
            shadow_root: Root directory where shadow repositories will be stored.
            cache_size: Maximum number of repositories to keep in the cache.
        """

    def save(self, worktree_dir: Path, commit_msg: Optional[str] = None) -> str:
        """Saves the current state of the worktree as a new commit.

        This method stages all changes in the worktree directory and creates a new commit
        in the shadow repository. It acts as a checkpoint that can later be restored.

        Args:
            worktree_dir: The worktree directory to checkpoint.
            commit_msg: Optional commit message; defaults to empty string if not provided.

        Returns:
            The commit ID (OID) as a string.

        Raises:
            RuntimeError: If the shadow repository is not found or Git operations fail
                (staging, committing, etc.).
        """

    def drop(self, worktree_dir: Path) -> None:
        """Deletes the shadow repository associated with a worktree directory.

        This method deletes the shadow repository associated with the specified worktree directory.
        It removes the repository from the cache and deletes the directory.

        Args:
            worktree_dir: The worktree directory to delete.

        Raises:
            RuntimeError: If the shadow repository is not found or deletion fails.
        """

    def reset(self, worktree_dir: Path, commit_id: str) -> None:
        """Hard resets the worktree directory to a specific commit.

        This method resets the worktree directory to the specified commit,
        overwriting any changes made since the last save.

        Args:
            worktree_dir: The worktree directory to reset.
            commit_id: The commit ID (OID as string) to reset to.

        Raises:
            RuntimeError: If the shadow repository is not found or the commit ID is invalid.
        """

    def rollback(self, worktree_dir: Path, commit_id: str, file_path: Path | str) -> None:
        """Restores a specific file from a commit.

        This rolls back a single file to its state at the specified commit,
        checking out that file from the commit's tree.

        Args:
            worktree_dir: The worktree directory containing the file.
            commit_id: The commit ID (OID as string) to restore from.
            file_path: The relative path to the file within the worktree.

        Raises:
            RuntimeError: If the shadow repository is not found, the commit ID is invalid,
                the file is not found in the commit, or the checkout operation fails.
        """

    def get_file_diff(self, worktree_dir: Path, commit_id: str, file_path: Path | str) -> str:
        """Retrieves the diff for a specific file at a given commit.

        Compares the file state at the specified commit with its state in the parent commit,
        returning a patch-format diff string. If the commit has no parent (initial commit),
        it compares against an empty tree.

        Args:
            worktree_dir: The worktree directory containing the file.
            commit_id: The commit ID (OID as string) to get the diff from.
            file_path: The relative path to the file within the worktree.

        Returns:
            A string containing the unified diff in patch format.

        Raises:
            RuntimeError: If the shadow repository is not found, the commit ID is invalid,
                or Git diff operations fail.
        """

__all__ = ["ShadowRepoManager"]
