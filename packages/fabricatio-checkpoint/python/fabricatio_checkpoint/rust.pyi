"""Rust bindings for the Rust API of fabricatio-checkpoint."""

from pathlib import Path
from typing import List, Optional

class CheckpointService:
    """Manages shadow Git repositories for file checkpointing.

    A shadow repository manager creates and maintains separate bare Git repositories
    for each worktree directory. This enables independent version control and checkpointing
    without interfering with any existing Git repositories in the worktree.
    """

    def __init__(self, stores_root: Path, cache_size: int = 10) -> None:
        """Creates a new CheckpointService instance.

        Initializes a shadow repository manager with the specified root directory
        and cache size. Creates the shadow root directory if it doesn't exist.

        Args:
            stores_root: Root directory where shadow repositories will be stored.
            cache_size: Maximum number of repositories to keep in the in-memory cache.
        """

    def get_store(self, worktree_dir: Path) -> CheckPointStore:
        """Gets or creates a shadow repository for the given worktree directory.

        This method first checks the cache for an existing repository. If not found,
        it either opens an existing bare repository from disk or creates a new one.

        Args:
            worktree_dir: The directory to be tracked by the shadow repository.

        Returns:
            A CheckPointStore instance for the specified worktree.

        Raises:
            RuntimeError: If repository operations fail.
        """

    def workspaces(self) -> List[Path]:
        """Retrieves the list of worktree directories with shadow repositories.

        This method returns a list of worktree directories that have shadow repositories.

        Returns:
            A list of worktree directories with shadow repositories.

        Raises:
            RuntimeError: If the shadow repository storage root is not found.
        """

class CheckPointStore:
    """Manages the shadow repository for a specific worktree.

    This class provides methods to save, rollback, and retrieve checkpoint
    information for a single worktree directory.
    """

    @property
    def workspace(self) -> Path:
        """The workspace directory being tracked by this store."""

    def head(self) -> str:
        """The current HEAD commit ID (OID) of the shadow repository."""

    def save(self, commit_msg: Optional[str] = None) -> str:
        """Saves the current state of the worktree as a new commit.

        This method stages all changes in the worktree directory and creates a new commit
        in the shadow repository. It acts as a checkpoint that can later be restored.

        Args:
            commit_msg: Optional commit message; defaults to empty string if not provided.

        Returns:
            The commit ID (OID) as a string.

        Raises:
            RuntimeError: If the shadow repository is not found or Git operations fail.

        Notes:
            If there are no changes to commit, this method returns the ID of the last commit.
        """

    def commits(self) -> List[str]:
        """Lists all commit IDs in the shadow repository's history.

        This method retrieves the complete commit history from the current HEAD
        backwards through the parent commits. The commits are returned in reverse
        chronological order (newest first).

        Returns:
            A list of commit IDs (OIDs as strings) in reverse chronological order.

        Raises:
            RuntimeError: If the shadow repository is not found or Git operations fail.
        """

    def reset(self, commit_id: str) -> None:
        """Resets the worktree to a specific commit.

        Performs a hard reset of the worktree directory to match the state at the specified commit.
        This discards all changes in the working directory and index, making them match the commit.

        Args:
            commit_id: The commit ID (OID as string) to reset to.

        Raises:
            RuntimeError: If the shadow repository is not found, the commit ID is invalid,
                or the reset operation fails.
        """

    def rollback(self, commit_id: str, file_path: Path | str) -> None:
        """Restores a specific file from a commit.

        This rolls back a single file to its state at the specified commit,
        checking out that file from the commit's tree.

        Args:
            commit_id: The commit ID (OID as string) to restore from.
            file_path: The relative path to the file within the worktree.

        Raises:
            RuntimeError: If the shadow repository is not found, the commit ID is invalid,
                the file is not found in the commit, or the checkout operation fails.
        """

    def get_file_diff(self, commit_id: str, file_path: Path | str) -> str:
        """Retrieves the diff for a specific file at a given commit.

        Compares the file state at the specified commit with its state in the parent commit,
        returning a patch-format diff string. If the commit has no parent (initial commit),
        it compares against an empty tree.

        Args:
            commit_id: The commit ID (OID as string) to get the diff from.
            file_path: The relative path to the file within the worktree.

        Returns:
            A string containing the unified diff in patch format.

        Raises:
            RuntimeError: If the shadow repository is not found, the commit ID is invalid,
                or Git diff operations fail.
        """

    def get_changed_files(self, commit_id: Optional[str] = None) -> List[str]:
        """Gets the list of changed files in a specific commit.

        Args:
            commit_id: The commit ID (OID as string) to get the changed files from.

        Returns:
            A list of file paths that were changed in the commit.

        Raises:
            RuntimeError: If the shadow repository is not found or the commit ID is invalid.
        """

__all__ = ["CheckPointStore", "CheckpointService"]
