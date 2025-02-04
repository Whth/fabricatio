from pydantic import HttpUrl

from fabricatio.config import LLMConfig, DebugConfig


def test_llm_config_defaults():
    llm_config = LLMConfig()
    assert llm_config.api_endpoint == HttpUrl("https://api.openai.com")
    assert llm_config.api_key.get_secret_value() == ""
    assert llm_config.timeout == 300
    assert llm_config.max_retries == 3
    assert llm_config.model == "gpt-3.5-turbo"
    assert llm_config.temperature == 1.0
    assert llm_config.stop_sign == ""
    assert llm_config.top_p == 0.35
    assert llm_config.generation_count == 1
    assert llm_config.stream is False
    assert llm_config.max_tokens == 8192


def test_debug_config_defaults():
    debug_config = DebugConfig()
    assert debug_config.log_level == "INFO"
    assert debug_config.log_file.endswith(".log")


def test_settings_defaults(settings):
    assert settings.llm.api_endpoint == HttpUrl("https://api.openai.com")
    assert settings.debug.log_level == "INFO"
