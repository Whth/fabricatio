"""This module contains the capabilities for the workspace."""

from pathlib import Path
from typing import List

from fabricatio_workspace.rust import commit, fork


class Workspace:
    """This class contains the capabilities for the workspace."""

    def fork(
        self,
        repo_path: str | Path,
        to: str | Path,
        branch_name: str,
        base_branch: str | None = None,
        exist_ok: bool = False,
    ) -> Path:
        """Fork a worktree."""
        return fork(repo_path, to, branch_name, base_branch, exist_ok)

    def commit(self, repo_path: str | Path, msg: str, files: None | List[str]) -> str:
        """Commit staged changes."""
        return commit(repo_path, msg, files)
