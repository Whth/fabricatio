"""Module containing configuration classes for fabricatio-capable."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class CapableConfig:
    """Configuration for fabricatio-capable."""

    capable_template: str = "built-in/capable"
    """Template for checking whether a capability is capable of fulfilling a request."""


capable_config = CONFIG.load("capable", CapableConfig)

__all__ = ["capable_config"]
