"""Command line interface for fabricatio-webui service."""

from fabricatio_core.utils import cfg

cfg(feats=["cli"])
from asyncio import run
from pathlib import Path

from typer import Option, Typer

from fabricatio_webui.rust import start_service

app = Typer()

CUR_DIR = Path(__file__).parent


@app.command()
def main(
    frontend_dir: Path = Option(CUR_DIR.joinpath("www"), "--frontend-dir", "-d", help="front end directory"),
    addr: str = Option("127.0.0.1:9846", "--addr", "-a", help="address to bind to"),
) -> None:
    """Start the webui service."""

    async def _wrapper() -> None:
        await start_service(frontend_dir, addr)

    run(_wrapper())
