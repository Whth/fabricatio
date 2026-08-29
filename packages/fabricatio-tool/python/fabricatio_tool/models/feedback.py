"""Pure, deterministic feedback summarization for tool executions.

This module turns a :class:`ResultCollector` snapshot into a stable, LLM-readable
feedback string so that failed (or partially successful) executions can be fed
back into the next drafting round.

Design constraints:
- **Functional**: :func:`summarize_collector` and :func:`render_feedback` are pure
  functions over immutable snapshots; neither mutates the collector.
- **Prefix-cache friendly**: output depends only on the collector content, never on
  wall-clock time, random values, or insertion order (keys are sorted), so identical
  execution state always renders byte-identical text.
- **Context-composable**: the block is assembled as a
  :class:`~fabricatio_context.models.context.ContextLog`; callers accumulate every
  failed try via :func:`failure_entries` and :func:`feedback_log` so the LLM sees
  the whole failure history, not just the last error.
"""

import json
from dataclasses import dataclass

from fabricatio_context.models.context import ContextEntry, ContextLog

from fabricatio_tool.config import tool_config
from fabricatio_tool.models.collector import ResultCollector


@dataclass
class FeedbackPayload:
    """Immutable snapshot of a tool execution, ready for LLM feedback rendering."""

    results: dict[str, str]
    """Deterministically stringified successful results, sorted by key."""

    error: str | None
    """Rendered :class:`ApplicationError`, if the execution failed."""

    source: str | None
    """The source code that raised the error, truncated."""


def _truncate(text: str, limit: int) -> str:
    """Truncate text to `limit` characters, keeping head and tail with a marker.

    Args:
        text: The text to truncate.
        limit: Maximum kept characters; non-positive limits return the text unchanged.

    Returns:
        The possibly truncated text with a deterministic marker in the middle.
    """
    if limit <= 0 or len(text) <= limit:
        return text
    marker = f"\n...[truncated {len(text) - limit} chars]...\n"
    head_keep = max((limit - len(marker)) // 2, 1)
    tail_keep = max(limit - len(marker) - head_keep, 0)
    return text[:head_keep] + marker + text[-tail_keep:]


def _stringify[T](val: T, *, limit: int) -> str:
    """Deterministically stringify a collected value for LLM consumption.

    JSON-serializable values render via compact JSON with sorted keys; anything
    else falls back to `repr`. The result is truncated to `limit` characters.

    Args:
        val: A value taken from a :class:`ResultCollector` container.
        limit: Per-item character cap applied after serialization.

    Returns:
        A deterministic string representation of the value.
    """
    try:
        text = json.dumps(val, sort_keys=True, ensure_ascii=False, default=repr)
    except (TypeError, ValueError):
        text = repr(val)
    return _truncate(text, limit)


def summarize_collector(collector: ResultCollector, *, max_chars: int | None = None) -> FeedbackPayload:
    """Snapshot a collector into a feedback payload without mutating it.

    The error entry stored under `tool_config.error_key` is excluded from
    `results` and surfaced through `error`/`source` instead.

    Args:
        collector: The collector to snapshot (read-only access).
        max_chars: Per-item character cap; defaults to `tool_config.feedback_max_chars`.

    Returns:
        The deterministic payload describing results, error, and failed source.
    """
    limit = tool_config.feedback_max_chars if max_chars is None else max_chars
    err = collector.error()
    results = {
        key: _stringify(val, limit=limit)
        for key, val in sorted(collector.container.items())
        if key != tool_config.error_key
    }
    return FeedbackPayload(
        results=results,
        error=str(err) if err is not None else None,
        source=_truncate(err.source, limit) if err is not None else None,
    )


def failure_entries(payload: FeedbackPayload) -> tuple[ContextEntry, ...]:
    """Extract only the failure entries (error and source) from a payload.

    These are the entries worth accumulating across retry rounds: results are
    snapshot-fresh each round, while every failed try's error and source must
    stay visible so the LLM never repeats a fixed mistake.

    Args:
        payload: The snapshot to extract from.

    Returns:
        The frozen error and source entries, in that order.
    """
    entries: list[ContextEntry] = []
    if payload.error is not None:
        entries.append(
            ContextEntry(
                kind="tool_error",
                title="Error",
                body=f"**Error raised during execution:**\n{payload.error}",
            )
        )
    if payload.source is not None:
        entries.append(
            ContextEntry(
                kind="tool_source",
                title="Source",
                body=f"**Source that raised the error:**\n```python\n{payload.source}\n```",
            )
        )
    return tuple(entries)


def feedback_log(payload: FeedbackPayload, *, history: ContextLog | None = None) -> ContextLog:
    """Assemble a payload into a branchable context log.

    Each section becomes a frozen entry. Without `history`, the log carries the
    payload's own failure entries; with `history`, those are replaced by the
    accumulated failure history so every previously failed try stays visible
    while the results section stays a single fresh snapshot.

    Args:
        payload: The snapshot to assemble.
        history: Accumulated failure entries from previous failed tries.

    Returns:
        The context log holding the results section plus the failure history.
    """
    entries: list[ContextEntry] = []
    if payload.results:
        rendered = "\n".join(f'- "{key}":\n{val}' for key, val in payload.results.items())
        entries.append(
            ContextEntry(
                kind="tool_results",
                title="Results",
                body=f"**Results collected during the failed execution:**\n{rendered}",
            )
        )
    entries.extend(history.entries if history is not None else failure_entries(payload))
    return ContextLog(entries=tuple(entries))


def render_feedback(payload: FeedbackPayload) -> str:
    """Render a payload into the markdown feedback block injected into the draft prompt.

    The rendering is deterministic: identical payloads produce identical bytes,
    which keeps provider prefix caches warm across retry rounds.

    Args:
        payload: The snapshot to render.

    Returns:
        The markdown feedback text; empty when the payload carries no information.
    """
    return feedback_log(payload).render()


__all__ = ["FeedbackPayload", "failure_entries", "feedback_log", "render_feedback", "summarize_collector"]
