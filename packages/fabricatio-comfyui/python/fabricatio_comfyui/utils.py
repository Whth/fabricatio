"""Shared helpers for ComfyUI client modules."""

from typing import Dict

from fabricatio_comfyui.models.comfyui import ComfyuiExecutionResult, ComfyuiOutputImage, HistoryEntry

__all__ = ["build_result"]


def build_result(prompt_id: str, entry: HistoryEntry) -> ComfyuiExecutionResult:
    """Build an execution result from a history entry."""
    outputs: Dict[str, list[ComfyuiOutputImage]] = {}
    for node_id, node_output in entry.outputs.items():
        if node_output.images:
            outputs[node_id] = list(node_output.images)

    return ComfyuiExecutionResult(
        prompt_id=prompt_id,
        outputs=outputs,
        status=entry.status.status_str,
        error=entry.status.exception,
    )
