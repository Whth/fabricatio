"""Mock class representing a test role with LLM capabilities.

This class combines the base Role class with LLM usage capabilities for testing purposes.
It provides default implementations and test values for LLM-related attributes.
"""

from typing import Optional

from fabricatio_core import Role
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.capabilities.usages import UseLLM

from fabricatio_mock import DUMMY_LLM_GROUP
from fabricatio_mock.utils import setup_dummy_responses


class LLMTestRole(Role, UseLLM):
    """Test class combining Role and UseLLM functionality.

    A concrete implementation of Role mixed with UseLLM capabilities
    for testing purposes.
    """

    llm_send_to: Optional[str] = DUMMY_LLM_GROUP
    llm_no_cache: Optional[bool] = True

    def mock_llm_response(self, *responses: str) -> None:
        """Enqueue dummy LLM responses for this role's send_to group."""
        setup_dummy_responses(*responses, group=self.llm_send_to or DUMMY_LLM_GROUP)


class ProposeTestRole(LLMTestRole, Propose):
    """Test class combining LLMTestRole and Propose functionality."""
