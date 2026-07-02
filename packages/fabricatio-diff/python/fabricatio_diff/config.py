"""Module containing configuration classes for fabricatio-diff."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class DiffConfig:
    """Configuration for fabricatio-diff."""

    match_precision: float = 1.0
    """Precision threshold for matching."""

    diff_template: str = "built-in/diff"
    """Template string for diff output."""

    hashline_diff_template: str = "built-in/hashline_diff"
    """Template for the LLM-driven hashline edit loop (self-correcting)."""

    hashline_judge_template: str = "built-in/hashline_judge"
    """Template for the YES/NO satisfaction judge inside the hashline edit loop."""

    hashline_diff_max_iterations: int = 5
    """Maximum LLM iterations for the hashline edit loop before giving up."""


diff_config = CONFIG.load("diff", DiffConfig)

__all__ = ["diff_config"]
