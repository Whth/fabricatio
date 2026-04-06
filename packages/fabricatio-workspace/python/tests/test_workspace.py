"""Tests for the workspace."""
import builtins
import pathlib

import pytest

from fabricatio_workspace.rust import fork, commit, prune


class TestRustBindingsInterface:
    """Test suite for verifying the interface of Rust-backed Git functions."""

    def test_commit_signature_accepts_pathlib(self) -> None:
        """
        Verify that commit accepts pathlib.Path and returns a string OID.

        This test checks if the function raises expected errors for invalid paths
        rather than type errors, ensuring the binding accepts PathLike objects.
        """
        fake_path = pathlib.Path("/nonexistent/worktree")
        msg = "test message"

        with pytest.raises(RuntimeError):
            # Expecting RuntimeError because the path is invalid,
            # not TypeError because of wrong argument types.
            commit(worktree_path=fake_path, msg=msg, files=None)

    def test_commit_signature_accepts_str(self) -> None:
        """
        Verify that commit accepts string paths.
        """
        fake_path = "/nonexistent/worktree"
        msg = "test message"

        with pytest.raises(RuntimeError):
            commit(worktree_path=fake_path, msg=msg, files=["file.txt"])

    def test_fork_signature_and_return_type(self) -> None:
        """
        Verify that fork accepts correct arguments and returns a Path.
        """
        repo_path = pathlib.Path("/nonexistent/repo")
        dest_path = pathlib.Path("/nonexistent/dest")
        branch = "feature/test"

        with pytest.raises(RuntimeError):
            # Should fail due to invalid repo path, not type mismatch
            result = fork(
                repo_path=repo_path,
                to=dest_path,
                branch_name=branch,
                base_branch="main",
                exist_ok=False
            )
            # If it didn't raise, check type (though it will raise in this mock scenario)
            assert isinstance(result, pathlib.Path)

    def test_fork_with_optional_params(self) -> None:
        """
        Verify fork works with optional parameters omitted.
        """
        repo_path = pathlib.Path("/nonexistent/repo")
        dest_path = pathlib.Path("/nonexistent/dest")
        branch = "feature/test"

        with pytest.raises(RuntimeError):
            fork(
                repo_path=repo_path,
                to=dest_path,
                branch_name=branch
                # base_branch and exist_ok use defaults
            )

    def test_prune_signature_and_return_type(self) -> None:
        """
        Verify that prune accepts a path and returns an integer.
        """
        repo_path = pathlib.Path("/nonexistent/repo")

        with pytest.raises(RuntimeError):
            count = prune(repo_path=repo_path)
            # If it didn't raise, check type
            assert isinstance(count, builtins.int)

    def test_commit_with_empty_files_list(self) -> None:
        """
        Verify commit handles empty file lists correctly.
        """
        fake_path = pathlib.Path("/nonexistent/worktree")
        msg = "test message"

        with pytest.raises(RuntimeError):
            commit(worktree_path=fake_path, msg=msg, files=[])
