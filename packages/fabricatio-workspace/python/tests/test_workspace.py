"""Tests for the workspace."""

from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_workspace.capabilities.workspace import Workspace


class WorkspaceRole(LLMTestRole, Workspace):
    """Test role that combines LLMTestRole with Workspace for testing."""
