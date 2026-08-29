"""Typed model of the bundled ComfyUI workflow graph, built in code.

The graph is fully internal — external callers never see or operate on a
workflow — and statically known, so it is *initialised in Python* (no
JSON asset to keep in sync) and only ever **serialized** to ComfyUI's
API format via :meth:`Graph.to_api` on submission.

One pydantic class per node type; fixed wire node IDs live solely as
serialization aliases, so Python code reads/writes named fields
(``graph.loader.inputs.ckpt_name``) while the wire emits
``{"loader": {"class_type": ..., "inputs": {...}, "_meta": ...}}`` —
the Python field name *is* the node ID.
``validate_assignment`` keeps the typed invariants true for the whole
object lifetime.
"""

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

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    title: str


class NodeInputs(BaseModel):
    """Base for node input blocks — exact keys only, no silent extras."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)


class CheckpointLoaderInputs(NodeInputs):
    """Inputs of ``CheckpointLoaderSimple``."""

    ckpt_name: str = "catTowerNoobaiXL_v15Vpred.safetensors"


class CheckpointLoaderNode(BaseModel):
    """``CheckpointLoaderSimple`` node."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["CheckpointLoaderSimple"] = "CheckpointLoaderSimple"
    inputs: CheckpointLoaderInputs = Field(default_factory=CheckpointLoaderInputs)
    meta: NodeMeta = Field(validation_alias="_meta")

    @classmethod
    def default(cls) -> Self:
        """Template loader node."""
        return cls(meta=NodeMeta(title="Load Checkpoint"))


class EmptyLatentInputs(NodeInputs):
    """Inputs of ``EmptyLatentImage``."""

    width: int = 768
    height: int = 512
    batch_size: int = 1


class EmptyLatentNode(BaseModel):
    """``EmptyLatentImage`` node."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["EmptyLatentImage"] = "EmptyLatentImage"
    inputs: EmptyLatentInputs = Field(default_factory=EmptyLatentInputs)
    meta: NodeMeta = Field(validation_alias="_meta")

    @classmethod
    def default(cls) -> Self:
        """Template latent node."""
        return cls(meta=NodeMeta(title="Empty Latent Image"))


class CLIPEncodeInputs(NodeInputs):
    """Inputs of ``CLIPTextEncode``."""

    text: str
    clip: NodeRef = Field(default_factory=lambda: NodeRef(node_id="loader", output_index=1))


class CLIPEncodeNode(BaseModel):
    """``CLIPTextEncode`` node — used for both prompt encodes."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["CLIPTextEncode"] = "CLIPTextEncode"
    inputs: CLIPEncodeInputs = Field(default_factory=CLIPEncodeInputs)
    meta: NodeMeta = Field(validation_alias="_meta")

    @classmethod
    def default(cls, *, text: str) -> Self:
        """Template prompt-encode node carrying *text*."""
        return cls(inputs=CLIPEncodeInputs(text=text), meta=NodeMeta(title="CLIP Text Encode (Prompt)"))


class VAEDecodeInputs(NodeInputs):
    """Inputs of ``VAEDecode``."""

    samples: NodeRef
    vae: NodeRef = Field(default_factory=lambda: NodeRef(node_id="loader", output_index=2))


class VAEDecodeNode(BaseModel):
    """``VAEDecode`` node — base pass and refine pass."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["VAEDecode"] = "VAEDecode"
    inputs: VAEDecodeInputs = Field(default_factory=VAEDecodeInputs)
    meta: NodeMeta = Field(validation_alias="_meta")

    @classmethod
    def default(cls, *, samples: NodeRef) -> Self:
        """Template decode node fed from the given sampler."""
        return cls(inputs=VAEDecodeInputs(samples=samples), meta=NodeMeta(title="VAE Decode"))


class VAEEncodeInputs(NodeInputs):
    """Inputs of ``VAEEncode``."""

    pixels: NodeRef = Field(default_factory=lambda: NodeRef(node_id="upscale", output_index=0))
    vae: NodeRef = Field(default_factory=lambda: NodeRef(node_id="loader", output_index=2))


class VAEEncodeNode(BaseModel):
    """``VAEEncode`` node."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["VAEEncode"] = "VAEEncode"
    inputs: VAEEncodeInputs = Field(default_factory=VAEEncodeInputs)
    meta: NodeMeta = Field(validation_alias="_meta")

    @classmethod
    def default(cls) -> Self:
        """Template re-encode node."""
        return cls(meta=NodeMeta(title="VAE Encode"))


class PreviewImageInputs(NodeInputs):
    """Inputs of ``PreviewImage``."""

    images: NodeRef = Field(default_factory=lambda: NodeRef(node_id="refine_decode", output_index=0))


class PreviewImageNode(BaseModel):
    """``PreviewImage`` node."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["PreviewImage"] = "PreviewImage"
    inputs: PreviewImageInputs = Field(default_factory=PreviewImageInputs)
    meta: NodeMeta = Field(validation_alias="_meta")

    @classmethod
    def default(cls) -> Self:
        """Template preview node."""
        return cls(meta=NodeMeta(title="Preview Image"))


class ImageScaleByInputs(NodeInputs):
    """Inputs of ``ImageScaleBy``."""

    upscale_method: str = "nearest-exact"
    scale_by: float = 2.3
    image: NodeRef = Field(default_factory=lambda: NodeRef(node_id="decode", output_index=0))


class ImageScaleByNode(BaseModel):
    """``ImageScaleBy`` node."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["ImageScaleBy"] = "ImageScaleBy"
    inputs: ImageScaleByInputs = Field(default_factory=ImageScaleByInputs)
    meta: NodeMeta = Field(validation_alias="_meta")

    @classmethod
    def default(cls) -> Self:
        """Template upscale node."""
        return cls(meta=NodeMeta(title="Upscale Image By"))


class SamplerInputs(NodeInputs):
    """Inputs of ``KSamplerAdvanced``."""

    add_noise: Literal["enable"] = "enable"
    noise_seed: int = 1072236688235494
    steps: int
    cfg: float
    sampler_name: str = "er_sde"
    scheduler: str = "beta"
    start_at_step: int
    end_at_step: int
    return_with_leftover_noise: Literal["disable"] = "disable"
    model: NodeRef = Field(default_factory=lambda: NodeRef(node_id="loader", output_index=0))
    positive: NodeRef = Field(default_factory=lambda: NodeRef(node_id="positive", output_index=0))
    negative: NodeRef = Field(default_factory=lambda: NodeRef(node_id="negative", output_index=0))
    latent_image: NodeRef


class KSamplerAdvancedNode(BaseModel):
    """``KSamplerAdvanced`` node — base pass and refine pass."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["KSamplerAdvanced"] = "KSamplerAdvanced"
    inputs: SamplerInputs = Field(default_factory=SamplerInputs)
    meta: NodeMeta = Field(validation_alias="_meta")

    @classmethod
    def default(
        cls,
        *,
        latent_image: NodeRef,
        steps: int,
        cfg: float,
        start_at_step: int,
        end_at_step: int,
    ) -> Self:
        """Template sampler node with per-pass schedule values."""
        return cls(
            inputs=SamplerInputs(
                latent_image=latent_image,
                steps=steps,
                cfg=cfg,
                start_at_step=start_at_step,
                end_at_step=end_at_step,
            ),
            meta=NodeMeta(title="KSampler (Advanced)"),
        )


_POSITIVE_PROMPT = (
    "best quality,masterpiece,4k,highres,1girl, selfie, holding phone, bedroom, "
    "morning sunlight, messy bed, pillows, white sheets, pajamas, pink hair, "
    "blunt bangs, waist-length twin tails, violet eyes,"
)
_NEGATIVE_PROMPT = (
    "worst,lowres,low quality,mulform,sketch,texts,censor,terrible quality,"
    "garbage,multiple arms,multiple legs,multiple fingers, low quality, "
    "jpeg artifacts, out of frame, watermark, signature,blurry,texts"
)


class Graph(BaseModel):
    """The bundled txt2img → upscale → refine graph, initialised in Python.

    ComfyUI node IDs are arbitrary unique strings, so the Python field
    names double as the wire node IDs — no numeric aliases anywhere.
    :meth:`to_api` produces the exact ComfyUI API-format payload for
    ``POST /prompt``.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    loader: CheckpointLoaderNode
    """Checkpoint loader node."""

    latent: EmptyLatentNode
    """Empty latent canvas node."""

    positive: CLIPEncodeNode
    """Positive prompt encode node."""

    negative: CLIPEncodeNode
    """Negative prompt encode node."""

    decode: VAEDecodeNode
    """Base-pass decode feeding the upscaler."""

    encode: VAEEncodeNode
    """Re-encode of the upscaled image for the refine pass."""

    refine_decode: VAEDecodeNode
    """Refine-pass decode node."""

    preview: PreviewImageNode
    """Preview image node."""

    upscale: ImageScaleByNode
    """Upscale step node."""

    sampler_base: KSamplerAdvancedNode
    """Base-pass sampler node."""

    sampler_refine: KSamplerAdvancedNode
    """Refine-pass sampler node."""

    @classmethod
    def default(cls) -> Self:
        """Assemble the bundled template from each node class's own default.

        Generation knobs (prompt, size, sampler, checkpoint) are
        overridden per request by the client via the ``with_*`` builders.
        """
        return cls(
            loader=CheckpointLoaderNode.default(),
            latent=EmptyLatentNode.default(),
            positive=CLIPEncodeNode.default(text=_POSITIVE_PROMPT),
            negative=CLIPEncodeNode.default(text=_NEGATIVE_PROMPT),
            decode=VAEDecodeNode.default(samples=NodeRef(node_id="sampler_base", output_index=0)),
            encode=VAEEncodeNode.default(),
            refine_decode=VAEDecodeNode.default(samples=NodeRef(node_id="sampler_refine", output_index=0)),
            preview=PreviewImageNode.default(),
            upscale=ImageScaleByNode.default(),
            sampler_base=KSamplerAdvancedNode.default(
                latent_image=NodeRef(node_id="latent", output_index=0),
                steps=21,
                cfg=7.9,
                start_at_step=0,
                end_at_step=990,
            ),
            sampler_refine=KSamplerAdvancedNode.default(
                latent_image=NodeRef(node_id="encode", output_index=0),
                steps=42,
                cfg=8.5,
                start_at_step=20,
                end_at_step=999,
            ),
        )

    def to_api(self) -> dict[str, object]:
        """Serialize to ComfyUI API format (``node_id -> {class_type, inputs, _meta}``).

        The field name doubles as the wire node ID, so serialization is a
        plain per-field projection; ``NodeRef`` fields serialize to
        ``[node_id, output_index]`` lists.
        """
        out: dict[str, object] = {}
        for name in type(self).model_fields:
            node = getattr(self, name)
            payload = node.model_dump(exclude={"meta"})
            payload["_meta"] = node.meta.model_dump()
            out[name] = payload
        return out

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
