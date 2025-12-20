"""Tests for the webui."""
import pytest
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_webui.capabilities.webui import Webui


class WebuiRole(LLMTestRole, Webui):
    """Test role that combines LLMTestRole with Webui for testing."""
