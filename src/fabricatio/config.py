from typing import Literal

from appdirs import user_config_dir
from pydantic import BaseModel, ConfigDict, Field, FilePath, HttpUrl, NonNegativeFloat, PositiveInt, SecretStr
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    PyprojectTomlConfigSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)


class LLMConfig(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True)
    api_endpoint: HttpUrl = Field(default=HttpUrl("https://api.openai.com"))
    """
    OpenAI API Endpoint.
    """

    api_key: SecretStr = Field(default=SecretStr(""))
    """
    OpenAI API key. Empty by default for security reasons, should be set before use.
    """

    timeout: PositiveInt = Field(default=300)
    """
    The timeout of the LLM model in seconds. Default is 300 seconds as per request.
    """

    max_retries: PositiveInt = Field(default=3)
    """
    The maximum number of retries. Default is 3 retries.
    """

    model: str = Field(default="gpt-3.5-turbo")
    """
    The LLM model name. Set to 'gpt-3.5-turbo' as per request.
    """

    temperature: NonNegativeFloat = Field(default=1.0)
    """
    The temperature of the LLM model. Controls randomness in generation. Set to 1.0 as per request.
    """

    stop_sign: str = Field(default="")
    """
    The stop sign of the LLM model. No default stop sign specified.
    """

    top_p: NonNegativeFloat = Field(default=0.35)
    """
    The top p of the LLM model. Controls diversity via nucleus sampling. Set to 0.35 as per request.
    """

    generation_count: PositiveInt = Field(default=1)
    """
    The number of generations to generate. Default is 1.
    """

    stream: bool = Field(default=False)
    """
    Whether to stream the LLM model's response. Default is False.
    """

    max_tokens: PositiveInt = Field(default=8192)
    """
    The maximum number of tokens to generate. Set to 8192 as per request.
    """


class PymitterConfig(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True)
    delimiter: str = Field(default=".", frozen=True)
    """
    The delimiter used to separate the event name into segments.
    """

    new_listener_event: bool = Field(default=False, frozen=True)
    """
    If set, a newListener event is emitted when a new listener is added.
    """

    max_listeners: int = Field(default=-1, frozen=True)
    """
    The maximum number of listeners per event.
    """


class DebugConfig(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True)

    log_level: Literal["DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")
    """
    The log level of the application.
    """

    log_file: FilePath = Field(default=f"{user_config_dir("fabricatio", roaming=True)}.log")
    """
    The log file of the application.
    """


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FABRIK_",
        env_nested_delimiter="__",
        pyproject_toml_depth=1,
        pyproject_toml_table_header=("tool", "fabricatio"),
        toml_file=["fabricatio.toml", f"{user_config_dir("fabricatio", roaming=True)}.toml"],
        env_file=[".env", ".envrc"],
        use_attribute_docstrings=True,
    )

    llm: LLMConfig = Field(default_factory=LLMConfig)
    """
    LLM Configuration
    """

    debug: DebugConfig = Field(default_factory=DebugConfig)
    """
    Debug Configuration
    """

    pymitter: PymitterConfig = Field(default_factory=PymitterConfig)
    """
    Pymitter Configuration
    """

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            DotEnvSettingsSource(settings_cls),
            EnvSettingsSource(settings_cls),
            TomlConfigSettingsSource(settings_cls),
            PyprojectTomlConfigSettingsSource(settings_cls),
        )


configs: Settings = Settings()
