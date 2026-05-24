"""Data models for ComfyUI API integration."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

__all__ = [
    "ComfyuiExecutionResult",
    "ComfyuiNodeRef",
    "ComfyuiOutputImage",
]


@dataclass(frozen=True)
class ComfyuiNodeRef:
    """Reference to another node's output in a workflow graph.

    Used as a value in node inputs to wire nodes together.
    """

    node_id: str
    """The source node ID."""

    output_index: int = 0
    """The output index on the source node (default 0)."""

    def to_list(self) -> list[str | int]:
        """Serialize to the ComfyUI API list format ``[node_id, output_index]``."""
        return [self.node_id, self.output_index]


@dataclass
class ComfyuiOutputImage:
    """Metadata for a generated image output."""

    filename: str
    """Image filename."""

    subfolder: str = ""
    """Subfolder within the output directory."""

    type: str = "output"
    """Directory type: ``output``, ``input``, or ``temp``."""

    @property
    def url_path(self) -> str:
        """Query string for the ``/view`` endpoint."""
        from urllib.parse import urlencode

        return urlencode({
            "filename": self.filename,
            "subfolder": self.subfolder,
            "type": self.type,
        })


@dataclass
class ComfyuiExecutionResult:
    """Result of a ComfyUI workflow execution."""

    prompt_id: str
    """UUID of the executed prompt."""

    outputs: Dict[str, List[ComfyuiOutputImage]] = field(default_factory=dict)
    """Outputs keyed by node ID, each containing a list of image metadata."""

    status: Optional[str] = None
    """Execution status string (``completed``, ``failed``, etc.)."""

    error: Optional[str] = None
    """Error message if execution failed."""

    @property
    def all_images(self) -> list[ComfyuiOutputImage]:
        """Flatten all output images across all nodes."""
        return [img for imgs in self.outputs.values() for img in imgs]

    @property
    def succeeded(self) -> bool:
        """Whether the execution completed without error."""
        return self.status == "completed" and self.error is None
