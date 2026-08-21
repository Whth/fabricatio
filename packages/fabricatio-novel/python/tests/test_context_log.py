"""Test module for the append-only context log."""

from typing import Literal

import pytest
from fabricatio_novel.models.context.log import ContextEntry, ContextLog
from pydantic import ValidationError


def entry(
    kind: Literal["chapter_header", "scene_content"] = "scene_content", title: str = "S1", body: str = "He left."
) -> ContextEntry:
    """Build a default context entry for tests."""
    return ContextEntry(kind=kind, title=title, body=body)


class TestContextEntry:
    """Test suite for ContextEntry immutability."""

    def test_entry_is_frozen(self) -> None:
        """Assert mutating an entry raises instead of corrupting shared history."""
        e = entry()
        with pytest.raises(ValidationError):
            e.body = "changed"

    def test_entry_kinds_are_restricted(self) -> None:
        """Assert unknown kinds are rejected."""
        with pytest.raises(ValidationError):
            ContextEntry(kind="prose", title="S1", body="text")


class TestContextLogAppend:
    """Test suite for appending entries."""

    def test_with_entry_is_pure(self) -> None:
        """Assert with_entry returns a new log and leaves the receiver unchanged."""
        log = ContextLog()
        e = entry()
        appended = log.with_entry(e)
        assert log.entries == ()
        assert appended.entries == (e,)
        assert appended is not log

    def test_with_entry_preserves_order(self) -> None:
        """Assert entries accumulate in append order."""
        first, second = entry(title="S1"), entry(title="S2")
        log = ContextLog().with_entry(first).with_entry(second)
        assert log.entries == (first, second)

    def test_with_entries_appends_in_sequence_order(self) -> None:
        """Assert bulk append preserves the given sequence order."""
        first, second, third = entry(title="S1"), entry(title="S2"), entry(title="S3")
        log = ContextLog(entries=(first,)).with_entries((second, third))
        assert log.entries == (first, second, third)

    def test_append_mutates_and_returns_self(self) -> None:
        """Assert the mutating sugar rebinds entries and returns self."""
        log = ContextLog()
        assert log.append(entry()) is log
        assert len(log.entries) == 1

    def test_append_keeps_other_logs_sharing_history_unchanged(self) -> None:
        """Assert rebinding entries never mutates the shared tuple."""
        shared = entry()
        log = ContextLog(entries=(shared,))
        observer = log.branch()
        log.append(entry(title="S2"))
        assert observer.entries == (shared,)


class TestContextLogBranch:
    """Test suite for branching."""

    def test_branch_shares_history_and_records_fork_point(self) -> None:
        """Assert a fork carries the same entries and the fork length."""
        log = ContextLog(entries=(entry(), entry(title="S2")))
        fork = log.branch()
        assert fork.entries == log.entries
        assert fork.forked_at == 2

    def test_branch_appends_are_isolated_from_parent(self) -> None:
        """Assert appending to the fork leaves the parent untouched."""
        log = ContextLog(entries=(entry(),))
        fork = log.branch().with_entry(entry(title="Alt"))
        assert len(fork.entries) == 2
        assert len(log.entries) == 1

    def test_parent_appends_are_isolated_from_branch(self) -> None:
        """Assert appending to the parent leaves the fork untouched."""
        log = ContextLog(entries=(entry(),))
        fork = log.branch()
        grown = log.with_entry(entry(title="Next"))
        assert len(grown.entries) == 2
        assert len(fork.entries) == 1

    def test_clear_returns_fresh_log_and_keeps_original(self) -> None:
        """Assert clear hands out an empty log while the original keeps its history."""
        log = ContextLog(entries=(entry(),))
        fresh = log.clear()
        assert fresh.entries == ()
        assert fresh.forked_at == 0
        assert len(log.entries) == 1


class TestContextLogRender:
    """Test suite for rendering."""

    def test_render_joins_bodies_with_blank_lines(self) -> None:
        """Assert bodies join with the legacy double newline separator."""
        log = ContextLog(entries=(entry(body="A."), entry(body="B.")))
        assert log.render() == "A.\n\nB."

    def test_render_filters_empty_bodies(self) -> None:
        """Assert empty bodies drop out exactly like the legacy conditional join."""
        log = ContextLog(entries=(entry(body=""), entry(body="A."), entry(body="")))
        assert log.render() == "A."

    def test_render_empty_log_is_empty_string(self) -> None:
        """Assert an empty log renders empty."""
        assert ContextLog().render() == ""

    def test_render_matches_legacy_join_semantics(self) -> None:
        r"""Assert render equals the legacy '\n\n'.join over truthy parts."""
        bodies = ["# Ch1", "", "He left.", "A stranger appeared."]
        log = ContextLog(
            entries=(
                entry(kind="chapter_header", title="Ch1", body=bodies[0]),
                entry(body=bodies[1]),
                entry(title="S1", body=bodies[2]),
                entry(title="S2", body=bodies[3]),
            )
        )
        assert log.render() == "\n\n".join(p for p in bodies if p)


class TestContextLogSerialization:
    """Test suite for snapshot persistence."""

    def test_round_trip_preserves_entries_and_fork_point(self) -> None:
        """Assert JSON round-trip restores an equal log."""
        log = ContextLog(entries=(entry(kind="chapter_header", title="Ch1", body="# Ch1"), entry())).branch()
        revived = ContextLog.model_validate_json(log.model_dump_json())
        assert revived == log
        assert revived.forked_at == log.forked_at
