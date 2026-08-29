"""Typed deserializer of the bundled ComfyUI workflow graph.

The bundled ``graphs/default.json`` is fully internal — external callers
never see or operate on a workflow graph — so its shape is known at
compile time.  This module models it **exactly**: one pydantic class per
node type, fixed node IDs as field aliases, strict ``extra`` handling at
every level so any drift in the JSON fails loudly at load time.

Parameterisation is plain typed attribute access plus chainable ``with_*``
mutators (the repo's mutator convention: in-place, return ``self``).  No
generic graph container, no ``get``-by-type lookup, no ``Any``.
"""

from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator


class NodeRef(BaseModel):
    """A typed link to another node's output (``[node_id, output_index]`` in API format)."""

    model_config = ConfigDict(frozen=True)

    node_id: str
    """Source node identifier (e.g. ``"4"``)."""

    output_index: int = 0
    """Output index on the source node."""

    @model_validator(mode="before")
    @classmethod
    def _from_api_list(cls, data: object) -> object:
        """Accept ComfyUI's ``[node_id, output_index]`` list form."""
        if isinstance(data, list) and len(data) == 2 and isinstance(data[0], str) and isinstance(data[1], int):
            return {"node_id": data[0], "output_index": data[1]}
        return data

    @model_serializer
    def _to_api_list(self) -> list[str | int]:
        """Serialize back to ComfyUI's ``[node_id, output_index]`` list form."""
        return [self.node_id, self.output_index]


class NodeMeta(BaseModel):
    """The ``_meta`` block of a node (display metadata, ignored by the server)."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    title: str


class NodeInputs(BaseModel):
    """Base for node input blocks — exact keys only, no silent extras."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class CheckpointLoaderInputs(NodeInputs):
    """Inputs of ``CheckpointLoaderSimple``."""

    ckpt_name: str


class CheckpointLoaderNode(BaseModel):
    """``CheckpointLoaderSimple`` node (id ``"4"``)."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    class_type: Literal["CheckpointLoaderSimple"]
    inputs: CheckpointLoaderInputs
    meta: NodeMeta = Field(alias="_meta")


class EmptyLatentInputs(NodeInputs):
    """Inputs of ``EmptyLatentImage``."""

    width: int
    height: int
    batch_size: int


class EmptyLatentNode(BaseModel):
    """``EmptyLatentImage`` node (id ``"6"``)."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    class_type: Literal["EmptyLatentImage"]
    inputs: EmptyLatentInputs
    meta: NodeMeta = Field(alias="_meta")


class CLIPEncodeInputs(NodeInputs):
    """Inputs of ``CLIPTextEncode``."""

    text: str
    clip: NodeRef


class CLIPEncodeNode(BaseModel):
    """``CLIPTextEncode`` node (ids ``"7"`` positive / ``"8"`` negative)."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    class_type: Literal["CLIPTextEncode"]
    inputs: CLIPEncodeInputs
    meta: NodeMeta = Field(alias="_meta")


class VAEDecodeInputs(NodeInputs):
    """Inputs of ``VAEDecode``."""

    samples: NodeRef
    vae: NodeRef


class VAEDecodeNode(BaseModel):
    """``VAEDecode`` node (ids ``"9"`` / ``"15"``)."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    class_type: Literal["VAEDecode"]
    inputs: VAEDecodeInputs
    meta: NodeMeta = Field(alias="_meta")


class VAEEncodeInputs(NodeInputs):
    """Inputs of ``VAEEncode``."""

    pixels: NodeRef
    vae: NodeRef


class VAEEncodeNode(BaseModel):
    """``VAEEncode`` node (id ``"13"``)."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    class_type: Literal["VAEEncode"]
    inputs: VAEEncodeInputs
    meta: NodeMeta = Field(alias="_meta")


class PreviewImageInputs(NodeInputs):
    """Inputs of ``PreviewImage``."""

    images: NodeRef


class PreviewImageNode(BaseModel):
    """``PreviewImage`` node (id ``"16"``)."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    class_type: Literal["PreviewImage"]
    inputs: PreviewImageInputs
    meta: NodeMeta = Field(alias="_meta")


class ImageScaleByInputs(NodeInputs):
    """Inputs of ``ImageScaleBy``."""

    upscale_method: str
    scale_by: float
    image: NodeRef


class ImageScaleByNode(BaseModel):
    """``ImageScaleBy`` node (id ``"19"``)."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    class_type: Literal["ImageScaleBy"]
    inputs: ImageScaleByInputs
    meta: NodeMeta = Field(alias="_meta")


class SamplerInputs(NodeInputs):
    """Inputs of ``KSamplerAdvanced``."""

    add_noise: Literal["enable"]
    noise_seed: int
    steps: int
    cfg: float
    sampler_name: str
    scheduler: str
    start_at_step: int
    end_at_step: int
    return_with_leftover_noise: Literal["disable"]
    model: NodeRef
    positive: NodeRef
    negative: NodeRef
    latent_image: NodeRef


class KSamplerAdvancedNode(BaseModel):
    """``KSamplerAdvanced`` node (ids ``"25"`` base / ``"26"`` refine)."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    class_type: Literal["KSamplerAdvanced"]
    inputs: SamplerInputs
    meta: NodeMeta = Field(alias="_meta")


class Graph(BaseModel):
    """Exact model of ``graphs/default.json`` — fixed node IDs as field aliases.

    Loading validates the bundled JSON against this schema (every node,
    input key, and ``class_type`` literal), so template drift fails loudly
    instead of surfacing as a server-side 400.

    Serialization via :meth:`to_api` produces the exact ComfyUI API-format
    payload for ``POST /prompt``.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    loader: CheckpointLoaderNode = Field(alias="4")
    """Checkpoint loader (id ``"4"``)."""

    latent: EmptyLatentNode = Field(alias="6")
    """Empty latent canvas (id ``"6"``)."""

    positive: CLIPEncodeNode = Field(alias="7")
    """Positive prompt encode (id ``"7"``)."""

    negative: CLIPEncodeNode = Field(alias="8")
    """Negative prompt encode (id ``"8"``)."""

    decode: VAEDecodeNode = Field(alias="9")
    """Base-pass decode feeding the upscaler (id ``"9"``)."""

    encode: VAEEncodeNode = Field(alias="13")
    """Re-encode of the upscaled image for the refine pass (id ``"13"``)."""

    refine_decode: VAEDecodeNode = Field(alias="15")
    """Refine-pass decode (id ``"15"``)."""

    preview: PreviewImageNode = Field(alias="16")
    """Preview image (id ``"16"``)."""

    upscale: ImageScaleByNode = Field(alias="19")
    """Upscale step (id ``"19"``)."""

    sampler_base: KSamplerAdvancedNode = Field(alias="25")
    """Base-pass sampler (id ``"25"``)."""

    sampler_refine: KSamplerAdvancedNode = Field(alias="26")
    """Refine-pass sampler (id ``"26"``)."""

    @classmethod
    def bundled(cls) -> Self:
        """Load and validate the bundled ``graphs/default.json`` template."""
        path = Path(__file__).resolve().parent.parent / "graphs" / "default.json"
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    def to_api(self) -> dict[str, object]:
        """Serialize to ComfyUI API format (``node_id -> {class_type, inputs, _meta}``)."""
        return self.model_dump(by_alias=True)

    # ------------------------------------------------------------------
    # Chainable parameterisation — direct typed mutation, no lookups
    # ------------------------------------------------------------------

    def with_checkpoint(self, ckpt_name: str) -> Self:
        """Set the checkpoint on the loader node; return *self* for chaining."""
        self.loader.inputs.ckpt_name = ckpt_name
        return self

    def with_positive_prompt(self, text: str) -> Self:
        """Set the positive prompt text; return *self* for chaining."""
        self.positive.inputs.text = text
        return self

    def with_negative_prompt(self, text: str) -> Self:
        """Set the negative prompt text; return *self* for chaining."""
        self.negative.inputs.text = text
        return self

    def with_resolution(self, *, width: int | None = None, height: int | None = None) -> Self:
        """Set the latent canvas width/height; return *self* for chaining."""
        if width is not None:
            self.latent.inputs.width = width
        if height is not None:
            self.latent.inputs.height = height
        return self

    def with_sampler(
        self,
        *,
        seed: int | None = None,
        steps: int | None = None,
        cfg: float | None = None,
        sampler_name: str | None = None,
        scheduler: str | None = None,
    ) -> Self:
        """Update sampler parameters on **both** KSamplerAdvanced nodes (base + refine).

        The bundled template runs a base pass and a refine pass; keeping
        their seeds/steps/cfg aligned is the sane semantic for a single
        generation.  Return *self* for chaining.
        """
        for sampler in (self.sampler_base, self.sampler_refine):
            if seed is not None:
                sampler.inputs.noise_seed = seed
            if steps is not None:
                sampler.inputs.steps = steps
            if cfg is not None:
                sampler.inputs.cfg = cfg
            if sampler_name is not None:
                sampler.inputs.sampler_name = sampler_name
            if scheduler is not None:
                sampler.inputs.scheduler = scheduler
        return self
