"""Configuration for fabricatio-webui."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class WebuiConfig:
    """Configuration for fabricatio-webui.

    Override via ``<data_dir>/webui.toml`` or ``~/.config/fabricatio/webui.toml``.
    """

    addr: str = "127.0.0.1:9846"
    frontend_dir: str = ""  # empty = use bundled www
    allowed_origins: tuple[str, ...] = ("http://localhost:*", "http://127.0.0.1:*")
    queue_max: int = 64
    history_max: int = 256
    persist_workflows: bool = True


webui_config = CONFIG.load("webui", WebuiConfig)

__all__ = ["webui_config"]
