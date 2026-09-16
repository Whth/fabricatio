"""Data models for the sandbox subpackage."""

from fabricatio_core.models.generic import Display

from fabricatio_sandbox.rust import SandboxSession


class SandboxResult(Display):
    """Result of a sandboxed operation."""

    session: SandboxSession
    """The underlying sandbox session after the operation."""

    diff: dict[str, str]
    """Per-file unified diffs for all mutations, or ``None`` if unchanged."""

    applied: bool = False
    """Whether ``session.apply()`` was called successfully."""

    def display(self) -> str:
        """Return a human-readable summary of the sandbox result."""
        n = len(self.diff)
        status = "applied" if self.applied else "pending"
        return f"SandboxResult({n} file(s) changed, {status})"
