"""Data models for the sandbox subpackage."""

from fabricatio_core.models.generic import Display

from fabricatio_sandbox.rust import SandboxSession


class SandboxResult(Display):
    """Result of a sandboxed operation.

    Attributes:
        session: The underlying sandbox session after the operation.
        diff: Per-file unified diffs for all mutations, or ``None`` if unchanged.
        applied: Whether ``session.apply()`` was called successfully.
    """

    session: SandboxSession
    diff: dict[str, str]
    applied: bool = False

    def display(self) -> str:
        """Return a human-readable summary of the sandbox result."""
        n = len(self.diff)
        status = "applied" if self.applied else "pending"
        return f"SandboxResult({n} file(s) changed, {status})"
