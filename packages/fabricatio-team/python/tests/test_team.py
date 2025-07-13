"""Tests for the team."""

from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_team.capabilities.team import Team


class TeamRole(LLMTestRole, Team):
    """Test role that combines LLMTestRole with Team for testing."""
