"""Module containing configuration classes for fabricatio-digest."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass
class DigestConfig:
    """Configuration for fabricatio-digest."""

    digest_template: str = "digest"
    """Template name for digest"""

    task_list_explain_template: str = "task_list_explain"
    """Template name for task list explain."""


digest_config = CONFIG.load("digest", DigestConfig)
__all__ = ["digest_config"]
