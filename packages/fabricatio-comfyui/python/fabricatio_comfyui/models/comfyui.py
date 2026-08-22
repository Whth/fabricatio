"""Typed Pydantic models for the ComfyUI HTTP API.

Every response from the ComfyUI server is deserialized into one of these
models, eliminating raw ``dict[str, object]`` propagation through call sites.
"""

from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from fabricatio_comfyui.models.workflow import WorkflowDict

__all__ = [
    "ComfyuiExecutionResult",
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
# Prompt submission
# ------------------------------------------------------------------
class PromptRequest(BaseModel):
    """Request body for ``POST /prompt``."""

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    prompt: WorkflowDict
    """The ComfyUI workflow graph (node_id -> class_type + inputs)."""

    client_id: str | None = None
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

    def to_params(self) -> dict[str, str]:
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

    node_errors: dict[str, Any] = Field(default_factory=dict)
    """Per-node validation errors (empty when valid).

    ``Any`` here is server-supplied diagnostic data — ComfyUI does not publish
    a stable schema for per-node error payloads.
    """

    @classmethod
    def from_raw(cls, data: dict[str, Any]) -> Self:
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

    prompt: WorkflowDict = Field(default_factory=dict)
    """The workflow graph submitted."""

    extra_data: dict[str, Any] = Field(default_factory=dict)
    """Extra metadata submitted with the prompt.

    ``Any`` is server-supplied opaque metadata; no client-side schema is
    published for ``extra_data`` payloads.
    """

    outputs_to_execute: list[str] = Field(default_factory=list)
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

    queue_running: list[QueueEntry] = Field(default_factory=list)
    """Currently executing prompts."""

    queue_pending: list[QueueEntry] = Field(default_factory=list)
    """Prompts waiting to execute."""

    @classmethod
    def from_raw(cls, data: dict[str, Any]) -> Self:
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

    exception: str | None = None
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

    images: list[ComfyuiOutputImage] = Field(default_factory=list)
    """Images produced by this node."""


class HistoryEntry(BaseModel):
    """A single entry from ``GET /history/{prompt_id}``."""

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    status: HistoryStatus = Field(default_factory=HistoryStatus)
    """Execution status."""

    outputs: dict[str, HistoryNodeOutput] = Field(default_factory=dict)
    """Per-node outputs keyed by node ID."""

    @model_validator(mode="before")
    @classmethod
    def _filter_empty_outputs(cls, data: Any) -> Any:
        """Strip images without filenames and drop empty output nodes."""
        if not isinstance(data, dict):
            return data
        outputs = data.get("outputs", {})
        cleaned: dict[str, Any] = {}
        for node_id, node_data in outputs.items():
            images = [img for img in node_data.get("images", []) if img.get("filename")]
            if images:
                cleaned[node_id] = {**node_data, "images": images}
        return {**data, "outputs": cleaned}

    @classmethod
    def from_raw(cls, data: dict[str, Any]) -> Self:
        """Deserialize from a single history entry dict."""
        return cls.model_validate(data)

    @classmethod
    def from_history_response(cls, response: dict[str, Any], prompt_id: str) -> Self | None:
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

    outputs: dict[str, list[ComfyuiOutputImage]] = Field(default_factory=dict)
    """Output images keyed by node ID."""

    status: str | None = None
    """Execution status string."""

    error: str | None = None
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
    def from_raw(cls, data: dict[str, Any]) -> Self:
        """Deserialize from the raw API response."""
        return cls.model_validate(data)


# ------------------------------------------------------------------
# System
# ------------------------------------------------------------------


class SystemStats(BaseModel):
    """Response from ``GET /system_stats``."""

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    system: dict[str, Any] = Field(default_factory=dict)
    """System info: OS, RAM, Python/PyTorch versions, etc.

    ``Any`` is intentional — the ComfyUI ``/system_stats`` payload is
    unstructured and varies by server build.
    """

    devices: list[dict[str, Any]] = Field(default_factory=list)
    """GPU/device information. ``Any`` per-device keys; no published schema."""
