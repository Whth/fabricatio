"""Command line interface for fabricatio-webui service."""

from fabricatio_core.utils import cfg

cfg(feats=["cli"])
import json
from asyncio import run
from pathlib import Path
from typing import Optional

from typer import Option, Typer

from fabricatio_webui.config import webui_config
from fabricatio_webui.registry import build_node_registry
from fabricatio_webui.rust import start_service

app = Typer()

CUR_DIR = Path(__file__).parent


def _default_www() -> Path:
    """Return the default frontend directory."""
    return CUR_DIR / "www"


@app.command()
def main(
    frontend_dir: Optional[Path] = Option(None, "--frontend-dir", "-d", help="front end directory"),
    data_dir: Path = Option(Path("./workflows"), "--data-dir", help="workflow persistence directory"),
    addr: Optional[str] = Option(None, "--addr", "-a", help="address to bind to"),
) -> None:
    """Start the webui service."""
    registry = build_node_registry()
    registry_json = json.dumps(registry.get("node_types", []))

    data_dir.mkdir(parents=True, exist_ok=True)

    # Resolve config — CLI flags win over config file defaults.
    resolved_addr = addr or webui_config.addr
    resolved_frontend = str(frontend_dir or webui_config.frontend_dir or _default_www())

    async def _wrapper() -> None:
        await start_service(
            resolved_frontend,
            str(data_dir),
            resolved_addr,
            registry_json,
            list(webui_config.allowed_origins),
        )

    run(_wrapper())
