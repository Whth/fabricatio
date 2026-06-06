"""Sandbox capability — provides VFS-based isolated file operations for LLM agents."""

from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.capabilities.usages import UseLLM

from fabricatio_sandbox.config import sandbox_config
from fabricatio_sandbox.rust import SandboxSession

if TYPE_CHECKING:
    from typing import Unpack

    from fabricatio_core.models.kwargs_types import ValidateKwargs

    from fabricatio_sandbox.models.sandbox import SandboxResult


class Sandbox(UseLLM, ABC):
    """Capability mixin that gives a Role sandboxed file operations.

    Typical usage::

        class MyRole(Role, Sandbox):
            async def do_work(self):
                session = self.create_session(mounts={"/src": "/real/src"})
                # ... use session.read_text / write_text etc.
                diff = session.diff()
                session.apply()  # or discard by not calling apply
    """

    def create_session(self, mounts: dict[str, str] | None = None) -> SandboxSession:
        """Create a new sandbox session, optionally with real-dir mounts.

        Args:
            mounts: ``{"/virtual": "/real/path", ...}`` mapping.
                    Falls back to ``sandbox_config.mounts`` when *None*.

        Returns:
            A fresh :class:`SandboxSession`.
        """
        effective = mounts if mounts is not None else sandbox_config.mounts
        return SandboxSession(mounts=effective or None)

    async def sandbox(
        self,
        source: str,
        requirement: str,
        mounts: dict[str, str] | None = None,
        **kwargs: Unpack[ValidateKwargs[SandboxResult]],
    ) -> SandboxResult:
        """Run a sandboxed edit operation driven by the LLM.

        Creates a session, writes *source* into the VFS, asks the LLM to
        modify it according to *requirement*, and returns the result
        including diffs.

        Args:
            source: Initial file content to place in the sandbox.
            requirement: Natural-language description of the desired change.
            mounts: Optional real-dir mounts for context.
            **kwargs: Forwarded to ``aask_validate``.

        Returns:
            A :class:`SandboxResult` with the session, diffs, and applied flag.
        """
        from fabricatio_sandbox.models.sandbox import SandboxResult

        session = self.create_session(mounts)
        session.write_text("source", source)

        def _validator(resp: str) -> SandboxResult | None:
            """Extract modified content from the LLM response and build a result."""
            content = resp.strip()
            if not content:
                return None
            session.write_text("source", content)
            return SandboxResult(session=session, diff=session.diff())

        result = await self.aask_validate(
            TEMPLATE_MANAGER.render_template(
                sandbox_config.sandbox_template,
                {"source": source, "requirement": requirement},
            ),
            _validator,
            **kwargs,
        )

        if result is None:
            logger.warning("Sandbox operation produced no valid result.")
        return result
