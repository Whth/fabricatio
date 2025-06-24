"""Module containing configuration classes for fabricatio-mock."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class MockConfig:
    """Configuration for fabricatio-mock."""


mock_config = CONFIG.load("mock", MockConfig)
__all__ = ["mock_config"]
