"""Shared WebSocket event framing for the webui worker and executor.

Both the worker (``status``/``execution_*`` frames) and the instrumented
actions (``node_*`` frames) emit the same shape: ``{"type": event_type,
**payload}`` serialized with orjson and handed to the injected Rust
``rust_broadcast`` callable. This module owns that framing once.
"""

from collections.abc import Callable, Mapping

import orjson
from fabricatio_core.journal import logger

from fabricatio_webui.models.wire import JSONValue


def emit_event(
    broadcast: Callable[[str], None] | None,
    event_type: str,
    payload: Mapping[str, JSONValue],
    *,
    execution_id: str | None = None,
) -> None:
    """Frame *payload* as a WS message and hand it to *broadcast*.

    The frame is ``{"type": event_type, **payload}``; *execution_id* is appended
    when given (the executor's node events carry it there, while the worker's
    own payloads already include it). A missing broadcast is a no-op and a
    failing one is logged, never raised: a dead client must not abort an
    execution.
    """
    if broadcast is None:
        return
    frame: dict[str, JSONValue] = {"type": event_type, **payload}
    if execution_id is not None:
        frame["execution_id"] = execution_id
    try:
        broadcast(orjson.dumps(frame).decode())
    except Exception:  # noqa: BLE001
        logger.warn(f"Broadcast failed for {event_type}")
