from appdirs import user_config_dir
from pydantic import Field, BaseModel, HttpUrl, SecretStr
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
    PydanticBaseSettingsSource,
    TomlConfigSettingsSource,
    PyprojectTomlConfigSettingsSource,
    EnvSettingsSource,
    DotEnvSettingsSource,
)


class LLMConfig(BaseModel):
    api_endpoint: HttpUrl = Field(default=HttpUrl("https://api.openai.com/v1"), description="OpenAI API Endpoint")
    api_key: SecretStr = Field(default=SecretStr("sk-xxx"), description="OpenAI API Key")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FABRIK_",
        env_nested_delimiter="__",
        pyproject_toml_depth=1,
        toml_file=["fabrik.toml", f"{user_config_dir("fabrik",roaming=True)}.toml"],
        env_file=[".env", ".envrc"],
    )

    llm: LLMConfig = Field(default_factory=LLMConfig, description="LLM Config")

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
