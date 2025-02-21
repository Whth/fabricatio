"""Configuration module for the Fabricatio application."""

from typing import List, Literal, Optional

from appdirs import user_config_dir
from pydantic import (
    BaseModel,
    ConfigDict,
    DirectoryPath,
    Field,
    FilePath,
    HttpUrl,
    NonNegativeFloat,
    PositiveInt,
    SecretStr,
)
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    PyprojectTomlConfigSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

ROAMING_DIR = user_config_dir("fabricatio", "", roaming=True)


class LLMConfig(BaseModel):
    """LLM configuration class.

    Attributes:
        api_endpoint (HttpUrl): OpenAI API Endpoint.
        api_key (SecretStr): OpenAI API key. Empty by default for security reasons, should be set before use.
        timeout (PositiveInt): The timeout of the LLM model in seconds. Default is 300 seconds as per request.
        max_retries (PositiveInt): The maximum number of retries. Default is 3 retries.
        model (str): The LLM model name. Set to 'gpt-3.5-turbo' as per request.
        temperature (NonNegativeFloat): The temperature of the LLM model. Controls randomness in generation. Set to 1.0 as per request.
        stop_sign (str): The stop sign of the LLM model. No default stop sign specified.
        top_p (NonNegativeFloat): The top p of the LLM model. Controls diversity via nucleus sampling. Set to 0.35 as per request.
        generation_count (PositiveInt): The number of generations to generate. Default is 1.
        stream (bool): Whether to stream the LLM model's response. Default is False.
        max_tokens (PositiveInt): The maximum number of tokens to generate. Set to 8192 as per request.
    """

    model_config = ConfigDict(use_attribute_docstrings=True)
    api_endpoint: HttpUrl = Field(default=HttpUrl("https://api.openai.com"))
    """OpenAI API Endpoint."""

    api_key: SecretStr = Field(default=SecretStr(""))
    """OpenAI API key. Empty by default for security reasons, should be set before use."""

    timeout: PositiveInt = Field(default=300)
    """The timeout of the LLM model in seconds. Default is 300 seconds as per request."""

    max_retries: PositiveInt = Field(default=3)
    """The maximum number of retries. Default is 3 retries."""

    model: str = Field(default="gpt-3.5-turbo")
    """The LLM model name. Set to 'gpt-3.5-turbo' as per request."""

    temperature: NonNegativeFloat = Field(default=1.0)
    """The temperature of the LLM model. Controls randomness in generation. Set to 1.0 as per request."""

    stop_sign: str | List[str] = Field(default=("\n\n\n", "User:"))
    """The stop sign of the LLM model. No default stop sign specified."""

    top_p: NonNegativeFloat = Field(default=0.35)
    """The top p of the LLM model. Controls diversity via nucleus sampling. Set to 0.35 as per request."""

    generation_count: PositiveInt = Field(default=1)
    """The number of generations to generate. Default is 1."""

    stream: bool = Field(default=False)
    """Whether to stream the LLM model's response. Default is False."""

    max_tokens: PositiveInt = Field(default=8192)
    """The maximum number of tokens to generate. Set to 8192 as per request."""


class PymitterConfig(BaseModel):
    """Pymitter configuration class.

    Attributes:
        delimiter (str): The delimiter used to separate the event name into segments.
        new_listener_event (bool): If set, a newListener event is emitted when a new listener is added.
        max_listeners (int): The maximum number of listeners per event.
    """

    model_config = ConfigDict(use_attribute_docstrings=True)
    delimiter: str = Field(default="::", frozen=True)
    """The delimiter used to separate the event name into segments."""

    new_listener_event: bool = Field(default=False, frozen=True)
    """If set, a newListener event is emitted when a new listener is added."""

    max_listeners: int = Field(default=-1, frozen=True)
    """The maximum number of listeners per event."""


class DebugConfig(BaseModel):
    """Debug configuration class.

    Attributes:
        log_level (Literal["DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]): The log level of the application.
        log_file (FilePath): The log file of the application.
    """

    model_config = ConfigDict(use_attribute_docstrings=True)

    log_level: Literal["DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")
    """The log level of the application."""

    log_file: FilePath = Field(default=rf"{ROAMING_DIR}\fabricatio.log")
    """The log file of the application."""

    rotation: int = Field(default=1)
    """The rotation of the log file. in weeks."""

    retention: int = Field(default=2)
    """The retention of the log file. in weeks."""

    streaming_visible: bool = Field(default=False)
    """Whether to print the llm output when streaming."""


class TemplateConfig(BaseModel):
    """Template configuration class."""

    model_config = ConfigDict(use_attribute_docstrings=True)
    template_dir: List[DirectoryPath] = Field(
        default_factory=lambda: [DirectoryPath(r".\templates"), DirectoryPath(rf"{ROAMING_DIR}\templates")]
    )
    """The directory containing the templates."""
    active_loading: bool = Field(default=False)
    """Whether to enable active loading of templates."""

    template_suffix: str = Field(default="hbs", frozen=True)
    """The suffix of the templates."""

    propose_task_template: str = Field(default="propose_task")
    """The name of the propose task template which will be used to propose a task."""

    draft_tool_usage_code_template: str = Field(default="draft_tool_usage_code")
    """The name of the draft tool usage code template which will be used to draft tool usage code."""

    make_choice_template: str = Field(default="make_choice")
    """The name of the make choice template which will be used to make a choice."""

    make_judgment_template: str = Field(default="make_judgment")
    """The name of the make judgment template which will be used to make a judgment."""

    dependencies_template: str = Field(default="dependencies")
    """The name of the dependencies template which will be used to manage dependencies."""

    task_briefing_template: str = Field(default="task_briefing")
    """The name of the task briefing template which will be used to brief a task."""


class MagikaConfig(BaseModel):
    """Magika configuration class."""

    model_config = ConfigDict(use_attribute_docstrings=True)
    model_dir: Optional[DirectoryPath] = Field(default=None)
    """The directory containing the models for magika."""


class GeneralConfig(BaseModel):
    """Global configuration class."""

    model_config = ConfigDict(use_attribute_docstrings=True)
    workspace: DirectoryPath = Field(default=DirectoryPath(r"."))
    """The workspace directory for the application."""

    confirm_on_ops: bool = Field(default=True)
    """Whether to confirm on operations."""


class ToolBoxConfig(BaseModel):
    """Toolbox configuration class."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    tool_module_name: str = Field(default="Toolbox")
    """The name of the module containing the toolbox."""

    data_module_name: str = Field(default="Data")
    """The name of the module containing the data."""


class Settings(BaseSettings):
    """Application settings class.

    Attributes:
        llm (LLMConfig): LLM Configuration
        debug (DebugConfig): Debug Configuration
        pymitter (PymitterConfig): Pymitter Configuration
        templates (TemplateConfig): Template Configuration
        magika (MagikaConfig): Magika Configuration
    """

    model_config = SettingsConfigDict(
        env_prefix="FABRIK_",
        env_nested_delimiter="__",
        pyproject_toml_depth=1,
        pyproject_toml_table_header=("tool", "fabricatio"),
        toml_file=["fabricatio.toml", rf"{ROAMING_DIR}\fabricatio.toml"],
        env_file=[".env", ".envrc"],
        use_attribute_docstrings=True,
    )

    llm: LLMConfig = Field(default_factory=LLMConfig)
    """LLM Configuration"""

    debug: DebugConfig = Field(default_factory=DebugConfig)
    """Debug Configuration"""

    pymitter: PymitterConfig = Field(default_factory=PymitterConfig)
    """Pymitter Configuration"""

    templates: TemplateConfig = Field(default_factory=TemplateConfig)
    """Template Configuration"""

    magika: MagikaConfig = Field(default_factory=MagikaConfig)
    """Magika Configuration"""

    general: GeneralConfig = Field(default_factory=GeneralConfig)
    """General Configuration"""

    toolbox: ToolBoxConfig = Field(default_factory=ToolBoxConfig)
    """Toolbox Configuration"""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customize settings sources.

        Args:
            settings_cls (type[BaseSettings]): The settings class.
            init_settings (PydanticBaseSettingsSource): Initial settings source.
            env_settings (PydanticBaseSettingsSource): Environment settings source.
            dotenv_settings (PydanticBaseSettingsSource): Dotenv settings source.
            file_secret_settings (PydanticBaseSettingsSource): File secret settings source.

        Returns:
            tuple[PydanticBaseSettingsSource, ...]: A tuple of settings sources.
        """
        return (
            DotEnvSettingsSource(settings_cls),
            EnvSettingsSource(settings_cls),
            TomlConfigSettingsSource(settings_cls),
            PyprojectTomlConfigSettingsSource(settings_cls),
        )


configs: Settings = Settings()
