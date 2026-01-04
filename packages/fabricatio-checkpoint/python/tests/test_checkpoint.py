"""Tests for the checkpoint."""

from pathlib import Path
from typing import Generator

import pytest
from fabricatio_checkpoint.capabilities.checkpoint import Checkpoint
from fabricatio_checkpoint.inited_manager import get_shadow_repo_manager
from fabricatio_mock.models.mock_role import LLMTestRole


class CheckpointRole(LLMTestRole, Checkpoint):
    """Test role that combines LLMTestRole with Checkpoint for testing."""


@pytest.fixture
def tmp_worktree_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary worktree directory."""
    p = tmp_path / "worktree"
    p.mkdir(parents=True, exist_ok=True)
    yield p
    get_shadow_repo_manager().drop(p)


@pytest.fixture
def role(tmp_worktree_dir: Path) -> CheckpointRole:
    """Create a test role."""
    return CheckpointRole(worktree_dir=tmp_worktree_dir)


def test_save(role: CheckpointRole, tmp_worktree_dir: Path) -> None:
    """Test saving a checkpoint."""
    tmp_worktree_dir.joinpath("test.txt").write_text("hello world")
    assert role.save_checkpoint("test1") == role.save_checkpoint(
        "test2"
    )  # two consecutive checkpoints should have the same id


def test_drop(role: CheckpointRole, tmp_worktree_dir: Path) -> None:
    """Test dropping a checkpoint."""
    role.save_checkpoint("test")
    role.drop_checkpoint()


def test_rollback(role: CheckpointRole, tmp_worktree_dir: Path) -> None:
    """Test rolling back a single file to a checkpoint while leaving others unchanged."""
    file1 = tmp_worktree_dir / "test1.txt"
    file2 = tmp_worktree_dir / "test2.txt"

    # Initial content
    content_v1_file1 = "hello world"
    content_v1_file2 = "nice to meet you"

    file1.write_text(content_v1_file1)
    file2.write_text(content_v1_file2)

    # Save first checkpoint
    id_1 = role.save_checkpoint("test1")
    assert id_1 is not None

    # Modify both files
    content_v2_file1 = content_v1_file1 * 3  # "hello worldhello worldhello world"
    content_v2_file2 = content_v1_file2 * 3

    file1.write_text(content_v2_file1)
    file2.write_text(content_v2_file2)

    # Save second checkpoint
    role.save_checkpoint("test2")

    # Rollback only 'test1.txt' to the first checkpoint
    role.rollback(id_1, "test1.txt")

    # Assert: only test1.txt is reverted; test2.txt remains modified
    assert file1.read_text() == content_v1_file1
    assert file2.read_text() == content_v2_file2  # Unaffected by rollback


def test_rollback_with_absolute_path(role: CheckpointRole, tmp_worktree_dir: Path, tmp_path: Path) -> None:
    """Test rolling back with absolute path."""
    texts = "hello world"
    file1 = tmp_worktree_dir / "test1.txt"
    file1.write_text(texts)
    id_1 = role.save_checkpoint("test1")
    file1.write_text(texts * 3)

    role.rollback(id_1, file1.absolute())
    assert file1.read_text() == texts


def test_rollback_with_external_absolute_path(role: CheckpointRole, tmp_worktree_dir: Path, tmp_path: Path) -> None:
    """Test rolling back with absolute path."""
    texts = "hello world"
    file1 = tmp_worktree_dir / "test1.txt"
    file1.write_text(texts)
    id_1 = role.save_checkpoint("test1")
    file1.write_text(texts * 3)

    external_file = tmp_path / "test1.txt"
    external_file.write_text(texts * 3)

    with pytest.raises(OSError, match="prefix not found"):
        role.rollback(id_1, external_file.absolute())
    role.rollback(id_1, file1.absolute())


def test_reset(role: CheckpointRole, tmp_worktree_dir: Path) -> None:
    """Test resetting the entire working directory to a checkpoint."""
    file1 = tmp_worktree_dir / "test1.txt"
    file2 = tmp_worktree_dir / "test2.txt"

    # Initial content
    content_v1_file1 = "hello world"
    content_v1_file2 = "nice to meet you"

    file1.write_text(content_v1_file1)
    file2.write_text(content_v1_file2)

    # Create initial checkpoint
    id_1 = role.save_checkpoint("test1")
    assert id_1 is not None

    # Modify both files
    content_v2_file1 = content_v1_file1 * 3
    content_v2_file2 = content_v1_file2 * 3

    file1.write_text(content_v2_file1)
    file2.write_text(content_v2_file2)

    # Save second checkpoint
    role.save_checkpoint("test2")

    # Reset entire worktree to first checkpoint
    role.reset_to_checkpoint(id_1)

    # Verify all changes are undone
    assert file1.read_text() == content_v1_file1
    assert file2.read_text() == content_v1_file2
