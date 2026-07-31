"""Programmatic ComfyUI workflow graph builder.

:class:`Workflow` is a thin composition of :class:`WorkflowCore` (graph
container + CRUD + serialization) and the ``*Ops`` ABCs
(:class:`LoaderOps`, :class:`PromptOps`, :class:`SamplerOps`,
:class:`ResolutionOps`) that add typed node-family setters.  Each concern
lives in its own module; this file just wires them together through nominal
multiple inheritance.

Load from exported API-format JSON or build from scratch::

    wf = Workflow.from_file("demo.json")
    wf.set_positive_prompt("masterpiece, best quality")
    wf.set_checkpoint("v1-5-pruned-emaonly.safetensors")

    # Serialize for client.queue_prompt()
    data = wf.to_api()

    # Build from scratch
    wf = Workflow.new()
    ckpt = wf.add("CheckpointLoaderSimple", inputs={"ckpt_name": "model.safetensors"})
    empty = wf.add("EmptyLatentImage", inputs={"width": 512, "height": 512, "batch_size": 1})
    pos = wf.add("CLIPTextEncode", inputs={"text": "a cat"})
    pos.connect("clip", ckpt, 1)
"""

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
    """ComfyUI workflow graph: core container + typed node-family setters.

    Composed through nominal multiple inheritance — no plugin registry, no
    ``hasattr``, no runtime dispatch.  ``WorkflowCore`` provides the concrete
    implementations of :class:`WorkflowAccess`'s abstract helpers, so the
    ``*Ops`` mixins resolve ``_resolve`` / ``_require_node`` / ``by_type``
    through the MRO.
    """
