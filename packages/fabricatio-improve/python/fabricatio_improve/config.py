"""Module containing configuration classes for fabricatio-improve."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass
class ImproveConfig:
    """Configuration for fabricatio-improve."""

    review_string_template: str = "review_string"
    """The name of the review string template which will be used to review a string."""

    fix_troubled_string_template: str = "fix_troubled_string"
    """The name of the fix troubled string template which will be used to fix a troubled string."""

    fix_troubled_obj_template: str = "fix_troubled_obj"
    """The name of the fix troubled object template which will be used to fix a troubled object."""


improve_config = CONFIG.load("improve", ImproveConfig)
__all__ = ["improve_config"]
