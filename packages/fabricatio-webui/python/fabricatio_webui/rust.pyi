"""Rust bindings for the Rust API of fabricatio-webui."""

from pathlib import Path

async def start_service(frontend_dir: str | Path, addr: str) -> None:
    """Start the WebUI service."""
