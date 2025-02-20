"""Test cases for the config module."""

import pytest
from fabricatio.config import (
    DebugConfig,
    GeneralConfig,
    LLMConfig,
    MagikaConfig,
    PymitterConfig,
    Settings,
    TemplateConfig,
)
from pydantic import ValidationError  # Import ValidationError


def test_llm_config_initialization():
    llm_config = LLMConfig(api_endpoint="https://api.example.com")
    assert str(llm_config.api_endpoint) == "https://api.example.com/"  # Convert HttpUrl to string


def test_debug_config_initialization():
    import os

    temp_log_file = os.path.join(os.getcwd(), "fabricatio.log")
    with open(temp_log_file, "w") as f:
        f.write("")  # Create an empty log file for the test
    debug_config = DebugConfig(log_level="DEBUG", log_file=temp_log_file)
    assert debug_config.log_level == "DEBUG"
    assert str(debug_config.log_file) == temp_log_file  # Convert WindowsPath to string


def test_pymitter_config_initialization():
    pymitter_config = PymitterConfig()
    assert pymitter_config is not None


def test_template_config_initialization():
    template_config = TemplateConfig()
    assert template_config is not None


def test_magika_config_initialization():
    magika_config = MagikaConfig()
    assert magika_config is not None


def test_general_config_initialization():
    general_config = GeneralConfig()
    assert general_config is not None


def test_settings_initialization():
    settings = Settings()
    assert isinstance(settings.llm, LLMConfig)
    assert isinstance(settings.debug, DebugConfig)
    assert isinstance(settings.pymitter, PymitterConfig)
    assert isinstance(settings.templates, TemplateConfig)
    assert isinstance(settings.magika, MagikaConfig)
    assert isinstance(settings.general, GeneralConfig)


# New test cases
def test_llm_config_validation():
    with pytest.raises(ValidationError):
        LLMConfig(api_endpoint="invalid_url")


def test_debug_config_validation():
    with pytest.raises(ValidationError):
        DebugConfig(log_level="INVALID_LEVEL", log_file="fabricatio.log")
