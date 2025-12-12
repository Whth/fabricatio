"""Module containing configuration classes for fabricatio-agent."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class AgentConfig:
    """Configuration for fabricatio-agent."""

    memory: bool = False
    """Whether to use memory."""
    sequential_thinking: bool = False
    """Whether to think sequentially."""
    check_capable: bool = False
    """Whether to check if the agent is capable of performing the task."""
    fulfill_prompt_template: str = "built-in/fulfill_prompt"
    """The prompt template to use for fulfill."""


agent_config = CONFIG.load("agent", AgentConfig)

__all__ = ["agent_config"]
