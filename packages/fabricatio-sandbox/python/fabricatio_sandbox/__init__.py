"""An extension of fabricatio providing VFS-based sandboxed file operations for LLM agents."""

from fabricatio_sandbox.rust import SandboxSession, VirtualFS

__all__ = [
    "SandboxSession",
    "VirtualFS",
]
