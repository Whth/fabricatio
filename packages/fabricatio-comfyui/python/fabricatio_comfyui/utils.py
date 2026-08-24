"""Shared helpers for ComfyUI client modules."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fabricatio_comfyui.models.comfyui import ComfyuiExecutionResult, ComfyuiOutputImage, HistoryEntry
    from fabricatio_comfyui.models.workflow import Workflow

__all__ = ["build_result", "is_node_ref", "load_template"]


def is_node_ref(value: object) -> bool:
    """Return ``True`` if *value* looks like a ``[node_id, output_index]`` reference."""
    return isinstance(value, list) and len(value) == 2 and isinstance(value[0], str)


def load_template(template: str | None) -> "Workflow":
    """Load a bundled workflow template by name (``None`` = the bundled default).

    *template* is the stem of a ``.json`` file under
    :mod:`fabricatio_comfyui.workflows`.
    """
    from fabricatio_comfyui.models.workflow import Workflow  # breaks import cycle

    if template is None:
        return Workflow.default()
    return Workflow.from_template(template)


def build_result(prompt_id: str, entry: "HistoryEntry") -> "ComfyuiExecutionResult":
    """Build an execution result from a history entry."""
    from fabricatio_comfyui.models.comfyui import ComfyuiExecutionResult  # breaks import cycle

    outputs: dict[str, list[ComfyuiOutputImage]] = {}
    for node_id, node_output in entry.outputs.items():
        if node_output.images:
            outputs[node_id] = list(node_output.images)

    return ComfyuiExecutionResult(
        prompt_id=prompt_id,
        outputs=outputs,
        status=entry.status.status_str,
        error=entry.status.exception,
    )
