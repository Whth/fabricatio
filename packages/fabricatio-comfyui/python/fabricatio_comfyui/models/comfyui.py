"""Typed Pydantic models for the ComfyUI HTTP API.

Every response from the ComfyUI server is deserialized into one of these
models, eliminating raw ``Dict[str, Any]`` propagation.
"""

from typing import Any, Dict, List, Optional, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "ComfyuiExecutionResult",
    "ComfyuiNodeRef",
    "ComfyuiOutputImage",
    "HistoryEntry",
    "HistoryNodeOutput",
    "HistoryStatus",
    "PromptRequest",
    "PromptResponse",
    "QueueEntry",
    "QueueInfo",
    "SystemStats",
    "UploadResponse",
    "ViewImageParams",
]


# ------------------------------------------------------------------
# Workflow graph primitives
# ------------------------------------------------------------------


class ComfyuiNodeRef(BaseModel):
    """Reference to another node's output in a workflow graph.

    Used as a value in node inputs to wire nodes together.
    Serialized to the ComfyUI API list format ``[node_id, output_index]``.
    """

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    node_id: str
    """The source node ID."""

    output_index: int = 0
    """The output index on the source node (default 0)."""

    def to_list(self) -> list[str | int]:
        """Serialize to ``[node_id, output_index]``."""
        return [self.node_id, self.output_index]


# ------------------------------------------------------------------
# Prompt submission
# ------------------------------------------------------------------
class PromptRequest(BaseModel):
    """Request body for ``POST /prompt``."""

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    prompt: Dict[str, Any]
    """The ComfyUI workflow graph (node_id -> class_type + inputs)."""

    client_id: Optional[str] = None
    """WebSocket client ID for progress tracking."""

    front: bool = False
    """If True, enqueue at the front of the queue."""


class ViewImageParams(BaseModel):
    """Query parameters for ``GET /view``."""

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    filename: str
    """Image filename on the server."""

    subfolder: str = ""
    """Subfolder within the output directory."""

    type: str = "output"
    """Directory type: ``output``, ``input``, or ``temp``."""

    def to_params(self) -> Dict[str, str]:
        """Serialize to query parameter dict."""
        return {
            "filename": self.filename,
            "subfolder": self.subfolder,
            "type": self.type,
        }


class PromptResponse(BaseModel):
    """Response from ``POST /prompt``."""

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    prompt_id: str
    """UUID assigned to the queued prompt."""

    number: int = 0
    """Queue position number."""

    node_errors: Dict[str, Any] = Field(default_factory=dict)
    """Per-node validation errors (empty when valid)."""

    @classmethod
    def from_raw(cls, data: Dict[str, Any]) -> Self:
        """Deserialize from the raw ``POST /prompt`` response."""
        return cls.model_validate(data)


# ------------------------------------------------------------------
# Queue
# ------------------------------------------------------------------


class QueueEntry(BaseModel):
    """A single item in the execution queue.

    ComfyUI returns queue entries as tuples:
    ``[number, prompt_id, prompt, extra_data, outputs_to_execute]``.
    This model deserializes that tuple via a ``@model_validator``.
    """

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    number: int = 0
    """Queue position."""

    prompt_id: str = ""
    """Prompt UUID."""

    prompt: Dict[str, Any] = Field(default_factory=dict)
    """The workflow graph submitted."""

    extra_data: Dict[str, Any] = Field(default_factory=dict)
    """Extra metadata submitted with the prompt."""

    outputs_to_execute: List[str] = Field(default_factory=list)
    """Node IDs that will be executed."""

    @model_validator(mode="before")
    @classmethod
    def _from_tuple(cls, data: Any) -> Any:
        """Accept ComfyUI's ``[number, prompt_id, …]`` tuple format."""
        if isinstance(data, (list, tuple)):
            return {
                "number": data[0] if len(data) > 0 else 0,
                "prompt_id": data[1] if len(data) > 1 else "",
                "prompt": data[2] if len(data) > 2 else {},
                "extra_data": data[3] if len(data) > 3 else {},
                "outputs_to_execute": data[4] if len(data) > 4 else [],
            }
        return data


class QueueInfo(BaseModel):
    """Response from ``GET /queue``."""

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    queue_running: List[QueueEntry] = Field(default_factory=list)
    """Currently executing prompts."""

    queue_pending: List[QueueEntry] = Field(default_factory=list)
    """Prompts waiting to execute."""

    @classmethod
    def from_raw(cls, data: Dict[str, Any]) -> Self:
        """Deserialize from the raw API response."""
        return cls.model_validate(data)


# ------------------------------------------------------------------
# History / execution results
# ------------------------------------------------------------------


class HistoryStatus(BaseModel):
    """Execution status within a history entry."""

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    status_str: str = "unknown"
    """Human-readable status: ``completed``, ``failed``, ``error``, etc."""

    completed: bool = False
    """Whether execution finished (success or failure)."""

    exception: Optional[str] = None
    """Exception message if execution failed."""


class ComfyuiOutputImage(BaseModel):
    """Metadata for a single generated output image."""

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    filename: str
    """Image filename on the server."""

    subfolder: str = ""
    """Subfolder within the output directory."""

    type: str = "output"
    """Directory type: ``output``, ``input``, or ``temp``."""

    @property
    def url_path(self) -> str:
        """Query string for the ``/view`` endpoint."""
        from urllib.parse import urlencode

        return urlencode(
            {
                "filename": self.filename,
                "subfolder": self.subfolder,
                "type": self.type,
            }
        )


class HistoryNodeOutput(BaseModel):
    """Output from a single node in the execution history."""

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    images: List[ComfyuiOutputImage] = Field(default_factory=list)
    """Images produced by this node."""


class HistoryEntry(BaseModel):
    """A single entry from ``GET /history/{prompt_id}``."""

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    status: HistoryStatus = Field(default_factory=HistoryStatus)
    """Execution status."""

    outputs: Dict[str, HistoryNodeOutput] = Field(default_factory=dict)
    """Per-node outputs keyed by node ID."""

    @model_validator(mode="before")
    @classmethod
    def _filter_empty_outputs(cls, data: Any) -> Any:
        """Strip images without filenames and drop empty output nodes."""
        if not isinstance(data, dict):
            return data
        outputs = data.get("outputs", {})
        cleaned: Dict[str, Any] = {}
        for node_id, node_data in outputs.items():
            images = [img for img in node_data.get("images", []) if img.get("filename")]
            if images:
                cleaned[node_id] = {**node_data, "images": images}
        return {**data, "outputs": cleaned}

    @classmethod
    def from_raw(cls, data: Dict[str, Any]) -> Self:
        """Deserialize from a single history entry dict."""
        return cls.model_validate(data)

    @classmethod
    def from_history_response(cls, response: Dict[str, Any], prompt_id: str) -> Optional[Self]:
        """Look up a prompt_id in a ``GET /history/{prompt_id}`` response.

        Returns:
            A :class:`HistoryEntry` if found, ``None`` otherwise.
        """
        if not response or prompt_id not in response:
            return None
        return cls.from_raw(response[prompt_id])


class ComfyuiExecutionResult(BaseModel):
    """Final result of a workflow execution."""

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    prompt_id: str
    """UUID of the executed prompt."""

    outputs: Dict[str, List[ComfyuiOutputImage]] = Field(default_factory=dict)
    """Output images keyed by node ID."""

    status: Optional[str] = None
    """Execution status string."""

    error: Optional[str] = None
    """Error message if execution failed."""

    @property
    def all_images(self) -> list[ComfyuiOutputImage]:
        """Flatten all output images across all nodes."""
        return [img for imgs in self.outputs.values() for img in imgs]

    @property
    def succeeded(self) -> bool:
        """Whether the execution completed without error."""
        return self.status in ("completed", "success") and self.error is None


# ------------------------------------------------------------------
# Upload
# ------------------------------------------------------------------


class UploadResponse(BaseModel):
    """Response from ``POST /upload/image``."""

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    name: str
    """Uploaded filename."""

    subfolder: str = ""
    """Subfolder where the file was stored."""

    type: str = "input"
    """Directory type."""

    @classmethod
    def from_raw(cls, data: Dict[str, Any]) -> Self:
        """Deserialize from the raw API response."""
        return cls.model_validate(data)


# ------------------------------------------------------------------
# System
# ------------------------------------------------------------------


class SystemStats(BaseModel):
    """Response from ``GET /system_stats``."""

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    system: Dict[str, Any] = Field(default_factory=dict)
    """System info: OS, RAM, Python/PyTorch versions, etc."""

    devices: List[Dict[str, Any]] = Field(default_factory=list)
    """GPU/device information."""
