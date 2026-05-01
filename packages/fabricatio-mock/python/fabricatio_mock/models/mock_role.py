"""Mock class representing a test role with LLM capabilities.

This class combines the base Role class with LLM usage capabilities for testing purposes.
It provides default implementations and test values for LLM-related attributes.
"""

from typing import Optional

from fabricatio_core import Role
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.capabilities.usages import UseLLM

from fabricatio_mock import DUMMY_LLM_GROUP


class LLMTestRole(Role, UseLLM):
    """Test class combining Role and UseLLM functionality.

    A concrete implementation of Role mixed with UseLLM capabilities
    for testing purposes.
    """

    llm_send_to: Optional[str] = DUMMY_LLM_GROUP
    llm_no_cache: Optional[bool] = True


class ProposeTestRole(LLMTestRole, Propose):
    """Test class combining LLMTestRole and Propose functionality."""
