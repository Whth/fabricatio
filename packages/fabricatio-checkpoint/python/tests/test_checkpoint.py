"""Tests for the checkpoint."""

from fabricatio_checkpoint.capabilities.checkpoint import Checkpoint
from fabricatio_mock.models.mock_role import LLMTestRole


class CheckpointRole(LLMTestRole, Checkpoint):
    """Test role that combines LLMTestRole with Checkpoint for testing."""
