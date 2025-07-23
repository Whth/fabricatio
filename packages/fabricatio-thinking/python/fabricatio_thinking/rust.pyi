"""Rust bindings for the Rust API of fabricatio-thinking."""

from typing import List, Optional

class ThoughtVCS:
    """Represents a simple version control system for managing branches and their commits."""

    def __int__(self) -> None:
        """Initializes a new instance of the ThoughtVCS class.

        Sets up a version control system capable of managing multiple branches,
        each with its own sequence of commits. The default branch is created
        automatically upon initialization.
        """

    def commit(
        self, content: str, serial: int, estimated: int, branch: Optional[str] = None, insert: bool = True
    ) -> Optional[int]:
        """Commits new content to a branch, creating the branch if necessary.

        Args:
            content: The content of the commit.
            serial: The serial number (1-based) for the commit.
            estimated: The estimated total number of commits for the branch.
            branch: The name of the branch, or None for the default branch.
            insert: Whether to create the branch if it does not exist.

        Returns:
            The new commit count if the commit was added, or None otherwise.
        """

    def revise(self, content: str, serial: int, branch: Optional[str] = None) -> Optional[int]:
        """Revises the content of an existing commit in a branch.

        Args:
            content: The new content for the commit.
            serial: The serial number (1-based) of the commit to revise.
            branch: The name of the branch, or None for the default branch.

        Returns:
            The serial if the commit was revised, or None otherwise.
        """

    def checkout(self, branch: str, serial: int) -> Optional[str]:
        """Checks out a branch at a specific commit serial, truncating it to that point.

        Args:
            branch: The name of the branch to checkout.
            serial: The number of commits to include in the checked-out branch.

        Returns:
            The branch name if the checkout was successful, or None otherwise.
        """

    def export_branch(self, branch: None | str = None) -> List[str]:
        """Exports the commits of a specified branch as a list of strings.

        Args:
            branch: The name of the branch to export, or None for the default branch.

        Returns:
            A list of strings representing the commit contents in the specified branch.
        """

    def export_branch_string(self, branch: None | str = None) -> str:
        """Exports the specified branch's commits as a concatenated string.

        Args:
            branch: The name of the branch to export, or None for the default branch.

        Returns:
            A string containing all commit contents in the specified branch,
            concatenated together.
        """
