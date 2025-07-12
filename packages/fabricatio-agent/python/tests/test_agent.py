"""Tests for the agent."""

from fabricatio_agent.capabilities.agent import Agent
from fabricatio_mock.models.mock_role import LLMTestRole


class AgentRole(LLMTestRole, Agent):
    """Test role that combines LLMTestRole with Agent for testing."""
