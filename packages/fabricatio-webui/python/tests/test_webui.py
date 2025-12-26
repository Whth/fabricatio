"""Tests for the webui."""

from fabricatio_mock.models.mock_role import LLMTestRole


class WebuiRole(LLMTestRole):
    """Test role that combines LLMTestRole with Webui for testing."""
