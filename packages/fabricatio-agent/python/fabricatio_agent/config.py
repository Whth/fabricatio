"""Module containing configuration classes for fabricatio-agent."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class AgentConfig:
    """Configuration for fabricatio-agent."""

    sequential_thinking: bool = True
    """Whether to think sequentially."""

    fulfill_capable_check_template: str = "fulfill_capable_check"
    """Template for checking whether a capability is capable of fulfilling a request."""

agent_config = CONFIG.load("agent", AgentConfig)

__all__ = ["agent_config"]
