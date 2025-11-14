"""Tests for the checkpoint."""
import pytest
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_checkpoint.capabilities.checkpoint import Checkpoint


class CheckpointRole(LLMTestRole, Checkpoint):
    """Test role that combines LLMTestRole with Checkpoint for testing."""
