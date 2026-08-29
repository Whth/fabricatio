"""Tests for the AssembleContext capability."""

from fabricatio_context.capabilities.context import AssembleContext
from fabricatio_context.models.context import ContextEntry, ContextLog


class Assembler(AssembleContext):
    """Assembler with a seeded head."""

    def context_head(self) -> ContextLog:
        """Seed two stable boilerplate entries."""
        return ContextLog(
            entries=(
                ContextEntry(kind="rules", title="Rules", body="static rules"),
                ContextEntry(kind="rules", title="More", body="more rules"),
            )
        )


class TestAssembleContext:
    """Head/branch behavior."""

    def test_default_head_is_empty(self) -> None:
        """The base head is an empty log."""
        assert AssembleContext().context_head().entries == ()

    def test_branch_context_forks_head(self) -> None:
        """Branches fork the head in O(1) and share its entries."""
        assembler = Assembler()
        branch = assembler.branch_context()
        assert branch.entries == assembler.context_head().entries
        assert branch.forked_at == 2

    def test_make_entry_builds_frozen_entry(self) -> None:
        """make_entry builds a frozen entry with the given fields."""
        entry = AssembleContext.make_entry("tool_results", "Results", "body")
        assert entry.kind == "tool_results"
        assert entry.title == "Results"
        assert entry.body == "body"

    def test_render_context_is_deterministic(self) -> None:
        """Rendering a log twice yields identical bytes."""
        assembler = Assembler()
        branch = assembler.branch_context().with_entry(
            AssembleContext.make_entry("request", "Req", "do the thing"),
        )
        assert assembler.render_context(branch) == assembler.render_context(branch)

    def test_branches_share_head_prefix(self) -> None:
        """Every branch render extends the head render byte-for-byte."""
        assembler = Assembler()
        head_render = assembler.render_context(assembler.context_head())
        left = assembler.branch_context().with_entry(
            AssembleContext.make_entry("request", "Req", "request A"),
        )
        right = assembler.branch_context().with_entry(
            AssembleContext.make_entry("request", "Req", "request B"),
        )
        assert assembler.render_context(left).startswith(head_render)
        assert assembler.render_context(right).startswith(head_render)
