"""Capability mixin for prefix-stable prompt assembly.

Composes onto a Role to manage a stable *head* of boilerplate entries plus
per-request *branches*: the head renders byte-identically across every request
(provider prefix caches hit), while each request appends to its own fork.
"""

from fabricatio_context.models.context import ContextEntry, ContextLog


class AssembleContext:
    """Manage a stable context head and per-request branches."""

    def context_head(self) -> ContextLog:
        """Return the stable head entries shared by every request; override to seed."""
        return ContextLog()

    def branch_context(self) -> ContextLog:
        """Fork the head into a fresh per-request branch in O(1)."""
        return self.context_head().branch()

    @staticmethod
    def make_entry(kind: str, title: str, body: str) -> ContextEntry:
        """Build a frozen context entry."""
        return ContextEntry(kind=kind, title=title, body=body)

    @staticmethod
    def render_context(context: ContextLog) -> str:
        """Render a log deterministically; identical logs yield identical bytes."""
        return context.render()


__all__ = ["AssembleContext"]
