"""Tests for the milvus."""

from fabricatio_milvus.capabilities.milvus import Milvus
from fabricatio_mock.models.mock_role import LLMTestRole


class MilvusRole(LLMTestRole, Milvus):
    """Test role that combines LLMTestRole with Milvus for testing."""
