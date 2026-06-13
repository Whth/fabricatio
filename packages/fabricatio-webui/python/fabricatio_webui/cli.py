"""Command line interface for fabricatio-webui service."""

from fabricatio_core.utils import cfg

cfg(feats=["cli"])
import json
from asyncio import run
from pathlib import Path
from typing import Optional


from typer import Option, Typer

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
    addr: str = Option("127.0.0.1:9846", "--addr", "-a", help="address to bind to"),
) -> None:
    """Start the webui service."""
    registry = build_node_registry()
    registry_json = json.dumps(registry.get("node_types", []))

    async def _wrapper() -> None:
        await start_service(str(frontend_dir or _default_www()), addr, registry_json)

    run(_wrapper())
