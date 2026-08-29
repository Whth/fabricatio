"""Tests for ContextLog and ContextEntry (generalized from fabricatio-novel's suite)."""

import pytest
from fabricatio_context.models.context import ContextEntry, ContextLog
from pydantic import ValidationError


def entry(body: str = "He left.", title: str = "S1", kind: str = "scene_content") -> ContextEntry:
    """Build a test entry."""
    return ContextEntry(kind=kind, title=title, body=body)


def test_entry_is_frozen() -> None:
    """Entries must reject mutation."""
    with pytest.raises(ValidationError):
        entry().body = "changed"  # type: ignore[union-attr]


class TestContextLogAppend:
    """Appending entries."""

    def test_with_entry_is_pure(self) -> None:
        """with_entry returns a new log and leaves the receiver unchanged."""
        log = ContextLog()
        appended = log.with_entry(entry())
        assert log.entries == ()
        assert len(appended.entries) == 1

    def test_with_entry_chains_in_order(self) -> None:
        """Chained appends preserve sequence order."""
        first, second = entry(title="S1"), entry(title="S2")
        log = ContextLog().with_entry(first).with_entry(second)
        assert log.entries == (first, second)

    def test_with_entries_appends_in_sequence_order(self) -> None:
        """Bulk appends preserve sequence order."""
        first, second, third = entry(title="S1"), entry(title="S2"), entry(title="S3")
        log = ContextLog(entries=(first,)).with_entries((second, third))
        assert log.entries == (first, second, third)

    def test_append_mutates_and_returns_self(self) -> None:
        """The mutating sugar rebinds entries and returns self."""
        log = ContextLog()
        assert log.append(entry()) is log
        assert len(log.entries) == 1

    def test_append_rebinding_does_not_disturb_other_holders(self) -> None:
        """Rebinding the tuple never disturbs holders of the old log."""
        shared = entry()
        log = ContextLog(entries=(shared,))
        observer = log.branch()
        log.append(entry(title="S2"))
        assert observer.entries == (shared,)


class TestContextLogBranch:
    """Branching."""

    def test_branch_shares_history_and_records_fork_point(self) -> None:
        """A fork carries the same entries and the fork length."""
        log = ContextLog(entries=(entry(), entry(title="S2")))
        fork = log.branch()
        assert fork.entries == log.entries
        assert fork.forked_at == 2

    def test_branch_appends_do_not_leak_to_parent(self) -> None:
        """Appending to the fork leaves the parent untouched."""
        log = ContextLog(entries=(entry(),))
        fork = log.branch().with_entry(entry(title="Alt"))
        assert len(fork.entries) == 2
        assert len(log.entries) == 1

    def test_parent_appends_do_not_leak_to_branch(self) -> None:
        """Appending to the parent leaves the fork untouched."""
        log = ContextLog(entries=(entry(),))
        fork = log.branch()
        grown = log.with_entry(entry(title="Next"))
        assert len(grown.entries) == 2
        assert len(fork.entries) == 1

    def test_clear_hands_out_empty_log(self) -> None:
        """Clear returns a fresh log while the original keeps its history."""
        log = ContextLog(entries=(entry(),))
        fresh = log.clear()
        assert fresh.entries == ()
        assert fresh.forked_at == 0
        assert len(log.entries) == 1


class TestContextLogRender:
    """Rendering."""

    def test_render_joins_bodies_with_blank_lines(self) -> None:
        """Bodies join with the double newline separator."""
        log = ContextLog(entries=(entry(body="A."), entry(body="B.")))
        assert log.render() == "A.\n\nB."

    def test_render_filters_empty_bodies(self) -> None:
        """Empty bodies drop out."""
        log = ContextLog(entries=(entry(body=""), entry(body="A."), entry(body="")))
        assert log.render() == "A."

    def test_render_empty_log_is_empty_string(self) -> None:
        """An empty log renders empty."""
        assert ContextLog().render() == ""

    def test_render_is_deterministic(self) -> None:
        """Identical logs render byte-identical text."""
        entries = (entry(body="A."), entry(body="B."))
        assert ContextLog(entries=entries).render() == ContextLog(entries=entries).render()


class TestContextLogSerialization:
    """Snapshot persistence."""

    def test_round_trip_preserves_entries_and_fork_point(self) -> None:
        """JSON round-trip restores an equal log."""
        log = ContextLog(entries=(entry(kind="chapter_header", title="Ch1", body="# Ch1"), entry())).branch()
        revived = ContextLog.model_validate_json(log.model_dump_json())
        assert revived == log
        assert revived.forked_at == log.forked_at

    def test_kind_is_free_form(self) -> None:
        """Kind accepts arbitrary vocabularies (packages narrow it via subclassing)."""
        assert entry(kind="anything_at_all").kind == "anything_at_all"


class TestPrefixProperty:
    """The head/branch prompt-cache contract."""

    def test_branch_render_extends_head_render(self) -> None:
        """A branch's render must extend the head's render byte-for-byte."""
        head = ContextLog(entries=(entry(body="static rules"), entry(body="more rules")))
        left = head.branch().with_entry(entry(body="request A"))
        right = head.branch().with_entry(entry(body="request B"))
        assert left.render().startswith(head.render())
        assert right.render().startswith(head.render())
        assert left.render()[: len(head.render())] == right.render()[: len(head.render())]
