"""Module containing configuration classes for fabricatio-sandbox."""

from dataclasses import dataclass, field

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class SandboxConfig:
    """Configuration for the sandbox subpackage."""

    sandbox_template: str = "built-in/sandbox"
    """Template name for LLM sandbox prompts."""

    mounts: dict[str, str] = field(default_factory=dict)
    """Default mount mapping ``{"/virtual": "/real/path", ...}``."""


sandbox_config = CONFIG.load("sandbox", SandboxConfig)

__all__ = ["sandbox_config"]
