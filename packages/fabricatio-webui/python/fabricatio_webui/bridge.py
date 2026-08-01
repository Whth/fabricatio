"""Deprecated async bridge callable from Rust via PyO3.

Deprecated: execution now lives in :mod:`fabricatio_webui.worker`
(``WorkflowWorker``), driven by the PyO3 callables passed into
``start_service``. Kept for reference; ``execute_workflow`` is no longer
used by the service.
"""

from typing import Any, Callable, Coroutine, Dict

import orjson


async def execute_workflow(
    workflow_json: str,
    event_callback: Callable[[str, str], Coroutine[Any, Any, None]],
) -> str:
    """Execute a workflow and return the final context as a JSON string.

    Parameters:
        workflow_json: serialised workflow descriptor.
        event_callback: ``async def(event_type: str, payload_json: str)``
            called with each lifecycle event.

    Returns:
        JSON-encoded result context dictionary.
    """
    from fabricatio_webui.executor import WorkflowExecutor

    wf = orjson.loads(workflow_json)

    async def _cb(event_type: str, payload: Dict[str, Any]) -> None:
        await event_callback(event_type, orjson.dumps(payload).decode())

    executor = WorkflowExecutor.new(wf, _cb)
    result = await executor.execute()
    return orjson.dumps(result).decode()
