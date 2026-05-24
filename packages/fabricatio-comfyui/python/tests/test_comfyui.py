"""Tests for the comfyui."""
import pytest
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_comfyui.capabilities.comfyui import Comfyui


class ComfyuiRole(LLMTestRole, Comfyui):
    """Test role that combines LLMTestRole with Comfyui for testing."""
