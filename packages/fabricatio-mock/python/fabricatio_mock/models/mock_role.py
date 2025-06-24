from typing import Optional

from pydantic import SecretStr

from fabricatio_core import Role
from fabricatio_core.capabilities.usages import UseLLM




class LLMTestRole(Role, UseLLM):
    """Test class combining Role and UseLLM functionality.

    A concrete implementation of Role mixed with UseLLM capabilities
    for testing purposes.
    """

    llm_api_key: Optional[SecretStr] = SecretStr("sk-123456789")
    llm_model: Optional[str] = "openai/gpt-3.5-turbo"
    llm_api_endpoint: Optional[str] = "https://api.openai.com/v1"
