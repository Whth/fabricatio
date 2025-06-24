"""Mock class representing a test role with LLM capabilities.

This class combines the base Role class with LLM usage capabilities for testing purposes.
It provides default implementations and test values for LLM-related attributes.
"""

from typing import Optional

from fabricatio_core import Role
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.capabilities.usages import UseLLM
from pydantic import SecretStr


class LLMTestRole(Role, UseLLM):
    """Test class combining Role and UseLLM functionality.

    A concrete implementation of Role mixed with UseLLM capabilities
    for testing purposes.
    """

    llm_api_key: Optional[SecretStr] = SecretStr("sk-123456789")
    llm_model: Optional[str] = "openai/gpt-3.5-turbo"
    llm_api_endpoint: Optional[str] = "https://api.openai.com/v1"


class ProposeTestRole(LLMTestRole, Propose):
    """Test class combining LLMTestRole and Propose functionality."""
