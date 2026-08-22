"""Programmatic ComfyUI workflow graph builder.

:class:`Workflow` is a thin composition of :class:`WorkflowCore` (graph
container + CRUD + serialization) and the ``*Ops`` ABCs
(:class:`LoaderOps`, :class:`PromptOps`, :class:`SamplerOps`,
:class:`ResolutionOps`) that add typed node-family setters.  Each concern
lives in its own module; this file just wires them together through nominal
multiple inheritance.

Load from a bundled template or build from scratch::

    wf = Workflow.from_template("default")
    wf.set_positive_prompt("masterpiece, best quality")
    wf.set_resolution(width=1024, height=1024)

    data = wf.to_api()
"""

from pathlib import Path

from fabricatio_comfyui.models.workflow_core import (
    RESOLUTION_SELECTOR_ASPECT_RATIOS,
    FrameAspect,
    Node,
    NodeApi,
    NodeInputs,
    NodeRef,
    WorkflowCore,
    WorkflowDict,
)
from fabricatio_comfyui.models.workflow_ops import (
    LoaderOps,
    PromptOps,
    ResolutionOps,
    SamplerOps,
)

__all__ = [
    "RESOLUTION_SELECTOR_ASPECT_RATIOS",
    "FrameAspect",
    "Node",
    "NodeApi",
    "NodeInputs",
    "NodeRef",
    "Workflow",
    "WorkflowDict",
]


class Workflow(WorkflowCore, LoaderOps, PromptOps, SamplerOps, ResolutionOps):
    """ComfyUI workflow graph: core container + typed node-family setters."""

    @classmethod
    def from_template(cls, name: str) -> "Workflow":
        """Load a bundled workflow by *name* (the stem of a ``.json`` file under :mod:`fabricatio_comfyui.workflows`).

        Raises:
            FileNotFoundError: when no matching bundled template exists.
        """
        # Walk up from this file: workflow.py lives at <pkg>/models/, so
        # parent.parent is the package root, where `workflows/<name>.json`
        # lives next to the bundled default.

        pkg_root = Path(__file__).resolve().parent.parent
        path = pkg_root / "workflows" / f"{name}.json"
        return cls.from_file(path)
