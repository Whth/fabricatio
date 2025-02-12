from pydantic import HttpUrl

from fabricatio.config import DebugConfig, LLMConfig


def test_llm_config_defaults():
    llm_config = LLMConfig()
    assert llm_config.api_endpoint == HttpUrl("https://api.example.com")

def test_debug_config_defaults():
    debug_config = DebugConfig()
    assert debug_config.log_level == "DEBUG"
    assert debug_config.log_file == "fabricatio.log"

def test_settings_defaults(settings):
    assert settings.llm.api_endpoint == HttpUrl("https://api.example.com")
    assert settings.debug.log_level == "DEBUG"
    assert settings.debug.log_file == "fabricatio.log"
