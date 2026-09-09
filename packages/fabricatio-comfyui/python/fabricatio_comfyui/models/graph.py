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

from collections.abc import Sequence
from enum import StrEnum, auto
from typing import ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_serializer


class NodeRef(BaseModel):
    """A typed link to another node's output (``[node_id, output_index]`` in API format)."""

    model_config = ConfigDict(frozen=True)

    node_id: str
    """Source node identifier (e.g. ``"4"``)."""

    output_index: int = 0
    """Output index on the source node."""

    @model_serializer
    def _to_api_tuple(self) -> tuple[str, int]:
        """Serialize to ComfyUI's ``(node_id, output_index)`` pair form."""
        return self.node_id, self.output_index

    @classmethod
    def first(cls, node_id: str) -> Self:
        """Build a link to *node_id*'s first output (index 0)."""
        return cls(node_id=node_id)

    @classmethod
    def second(cls, node_id: str) -> Self:
        """Build a link to *node_id*'s second output (index 1)."""
        return cls(node_id=node_id, output_index=1)

    @classmethod
    def third(cls, node_id: str) -> Self:
        """Build a link to *node_id*'s third output (index 2)."""
        return cls(node_id=node_id, output_index=2)

    @classmethod
    def fourth(cls, node_id: str) -> Self:
        """Build a link to *node_id*'s fourth output (index 3)."""
        return cls(node_id=node_id, output_index=3)

    @classmethod
    def fifth(cls, node_id: str) -> Self:
        """Build a link to *node_id*'s fifth output (index 4)."""
        return cls(node_id=node_id, output_index=4)


class NodeMeta(BaseModel):
    """The ``_meta`` block of a node (display metadata, ignored by the server)."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    title: str


class RewireField(StrEnum):
    """Graph-template node fields that a LoRA chain can be wired into.

    Member value equals the member name, which is the graph model's
    field name and, by extension, the wire node ID.
    """

    sampler = auto()
    sampler_base = auto()
    sampler_refine = auto()
    positive = auto()
    negative = auto()


class InputLink(StrEnum):
    """Node input links a LoRA chain can repoint; the value is the inputs field name."""

    model = auto()
    clip = auto()


class WireNode(BaseModel):
    """Base for ComfyUI node models — wire projection always emits serialization aliases."""

    inputs: "NodeInputs"
    """Typed input block; subclasses narrow it to their concrete inputs model."""

    def dump(self) -> dict[str, object]:
        """Project the node to its ComfyUI API wire mapping."""
        return self.model_dump(by_alias=True)

    def with_input(self, field: InputLink, ref: NodeRef) -> Self:
        """Copy of the node with one ``inputs`` link repointed to *ref*."""
        clone = self.model_copy(deep=True)
        match field:
            case InputLink.model:
                clone.inputs.model = ref
            case InputLink.clip:
                clone.inputs.clip = ref
        return clone

    def with_model(self, ref: NodeRef) -> Self:
        """Copy of the node with its ``model`` input repointed to *ref*."""
        return self.with_input(InputLink.model, ref)

    def with_clip(self, ref: NodeRef) -> Self:
        """Copy of the node with its ``clip`` input repointed to *ref*."""
        return self.with_input(InputLink.clip, ref)


class LoraSpec(BaseModel):
    """A LoRA applied to the bundled workflow (server-side filename + strength).

    Both the model and CLIP branches pass through the LoRA; *strength*
    applies to each (ComfyUI ``LoraLoader``).
    """

    model_config = ConfigDict(frozen=True)

    lora_name: str
    """LoRA filename on the server."""

    strength: float = 1.0
    """LoRA strength applied to both the model and CLIP branches."""


class NodeInputs(BaseModel):
    """Base for node input blocks — exact keys only, no silent extras."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    model: NodeRef | None = Field(default=None, exclude=True)
    """Optional model source link; subclasses that carry one redeclare it as required."""

    clip: NodeRef | None = Field(default=None, exclude=True)
    """Optional CLIP source link; subclasses that carry one redeclare it as required."""


class LoraLoaderInputs(NodeInputs):
    """Inputs of ``LoraLoader``."""

    model: NodeRef
    """Incoming model source (the checkpoint loader or the previous LoRA's output 0)."""

    clip: NodeRef
    """Incoming CLIP source (the CLIP loader or the previous LoRA's output 1)."""

    lora_name: str
    """LoRA filename on the server."""

    strength_model: float
    """Strength applied to the model branch."""

    strength_clip: float
    """Strength applied to the CLIP branch."""


class LoraLoaderNode(WireNode):
    """``LoraLoader`` chain link, synthesized per LoRA at serialization time.

    Output 0 carries the weighted model, output 1 the weighted CLIP.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["LoraLoader"] = "LoraLoader"
    inputs: LoraLoaderInputs
    meta: NodeMeta = Field(validation_alias="_meta", serialization_alias="_meta")

    @classmethod
    def chain(
        cls,
        loras: Sequence[LoraSpec],
        nodes: dict[str, WireNode],
        model_source: NodeRef,
        clip_source: NodeRef,
    ) -> tuple[NodeRef, NodeRef]:
        """Insert a ``LoraLoader`` chain for *loras* into *nodes*, fed from *model_source*/*clip_source*.

        Each link takes its ID from its index (``lora_0``, ``lora_1``, …); output 0 carries
        the weighted model, output 1 the weighted CLIP.  Returns the tail refs to feed the
        downstream model/CLIP inputs.
        """
        model_ref, clip_ref = model_source, clip_source
        for i, spec in enumerate(loras):
            node_id = f"lora_{i}"
            nodes[node_id] = cls(
                inputs=LoraLoaderInputs(
                    model=model_ref,
                    clip=clip_ref,
                    lora_name=spec.lora_name,
                    strength_model=spec.strength,
                    strength_clip=spec.strength,
                ),
                meta=NodeMeta(title=f"LoRA {spec.lora_name}"),
            )
            model_ref, clip_ref = NodeRef.first(node_id), NodeRef.second(node_id)
        return model_ref, clip_ref


class BaseGraph(BaseModel):
    """Common shape of the bundled workflow templates.

    Node fields are declared per subclass; the base carries the LoRA
    chain and the wire projection contract — each concrete graph MUST
    declare where its model/CLIP come from and which inputs the LoRA
    chain rewires.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    model_source: ClassVar[NodeRef]
    """Wire ref to the node output carrying the base model."""

    clip_source: ClassVar[NodeRef]
    """Wire ref to the node output carrying the unweighted CLIP."""

    model_inputs: ClassVar[tuple[RewireField, ...]]
    """Model-carrying inputs the LoRA chain output 0 feeds."""

    clip_inputs: ClassVar[tuple[RewireField, ...]]
    """CLIP-carrying inputs the LoRA chain output 1 feeds."""

    _loras: list[LoraSpec] = PrivateAttr(default_factory=list)
    """LoRAs chained into the model/CLIP path before submission."""

    def to_api(self) -> dict[str, object]:
        """Serialize to ComfyUI API format, chaining any :attr:`loras` into the model/CLIP paths.

        The field name doubles as the wire node ID, so serialization is a
        plain per-field projection; ``NodeRef`` fields serialize to
        ``[node_id, output_index]`` lists.  When :attr:`loras` is given, a
        chain of ``LoraLoader`` nodes is inserted between :attr:`model_source`
        and :attr:`clip_source` and the inputs named by :attr:`model_inputs`
        / :attr:`clip_inputs` are rewired to the chain tail.
        """
        nodes: dict[str, WireNode] = dict(self)
        model_ref, clip_ref = LoraLoaderNode.chain(self._loras, nodes, self.model_source, self.clip_source)
        for name in self.model_inputs:
            nodes[name] = nodes[name].with_model(model_ref)
        for name in self.clip_inputs:
            nodes[name] = nodes[name].with_clip(clip_ref)
        return {name: node.dump() for name, node in nodes.items()}

    def with_lora(self, lora_name: str, *, strength: float = 1.0) -> Self:
        """Append a LoRA to the model/CLIP chain; return *self* for chaining."""
        self._loras.append(LoraSpec(lora_name=lora_name, strength=strength))
        return self


class CheckpointLoaderInputs(NodeInputs):
    """Inputs of ``CheckpointLoaderSimple``."""

    ckpt_name: str = "catTowerNoobaiXL_v15Vpred.safetensors"


class CheckpointLoaderNode(WireNode):
    """``CheckpointLoaderSimple`` node."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["CheckpointLoaderSimple"] = "CheckpointLoaderSimple"
    inputs: CheckpointLoaderInputs = Field(default_factory=CheckpointLoaderInputs)
    meta: NodeMeta = Field(validation_alias="_meta", serialization_alias="_meta")

    @classmethod
    def default(cls) -> Self:
        """Template loader node."""
        return cls(meta=NodeMeta(title="Load Checkpoint"))


class EmptyLatentInputs(NodeInputs):
    """Inputs of ``EmptyLatentImage``."""

    width: int = 768
    height: int = 512
    batch_size: int = 1


class EmptyLatentNode(WireNode):
    """``EmptyLatentImage`` node."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["EmptyLatentImage"] = "EmptyLatentImage"
    inputs: EmptyLatentInputs = Field(default_factory=EmptyLatentInputs)
    meta: NodeMeta = Field(validation_alias="_meta", serialization_alias="_meta")

    @classmethod
    def default(cls) -> Self:
        """Template latent node."""
        return cls(meta=NodeMeta(title="Empty Latent Image"))


class CLIPEncodeInputs(NodeInputs):
    """Inputs of ``CLIPTextEncode``."""

    text: str = ""
    clip: NodeRef = Field(default_factory=lambda: NodeRef.second("loader"))


class PositivePromptInputs(CLIPEncodeInputs):
    """Positive prompt of the bundled template."""

    text: str = (
        "best quality,masterpiece,4k,highres,1girl, selfie, holding phone, bedroom, "
        "morning sunlight, messy bed, pillows, white sheets, pajamas, pink hair, "
        "blunt bangs, waist-length twin tails, violet eyes,"
    )


class NegativePromptInputs(CLIPEncodeInputs):
    """Negative prompt of the bundled template."""

    text: str = (
        "worst,lowres,low quality,mulform,sketch,texts,censor,terrible quality,"
        "garbage,multiple arms,multiple legs,multiple fingers, low quality, "
        "jpeg artifacts, out of frame, watermark, signature,blurry,texts"
    )


class CLIPEncodeNode(WireNode):
    """``CLIPTextEncode`` node — used for both prompt encodes."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["CLIPTextEncode"] = "CLIPTextEncode"
    inputs: CLIPEncodeInputs = Field(default_factory=CLIPEncodeInputs)
    meta: NodeMeta = Field(validation_alias="_meta", serialization_alias="_meta")

    @classmethod
    def default(cls) -> Self:
        """Template prompt-encode node."""
        return cls(meta=NodeMeta(title="CLIP Text Encode (Prompt)"))


class PositivePromptNode(CLIPEncodeNode):
    """``positive`` node of the bundled template."""

    inputs: PositivePromptInputs = Field(default_factory=PositivePromptInputs)


class NegativePromptNode(CLIPEncodeNode):
    """``negative`` node of the bundled template."""

    inputs: NegativePromptInputs = Field(default_factory=NegativePromptInputs)


class VAEDecodeInputs(NodeInputs):
    """Inputs of ``VAEDecode``."""

    samples: NodeRef = Field(default_factory=lambda: NodeRef.first("sampler_base"))
    vae: NodeRef = Field(default_factory=lambda: NodeRef.third("loader"))


class VAEDecodeNode(WireNode):
    """``VAEDecode`` node — base pass and refine pass."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["VAEDecode"] = "VAEDecode"
    inputs: VAEDecodeInputs = Field(default_factory=VAEDecodeInputs)
    meta: NodeMeta = Field(validation_alias="_meta", serialization_alias="_meta")

    @classmethod
    def default(cls) -> Self:
        """Template decode node fed from the base sampler."""
        return cls(meta=NodeMeta(title="VAE Decode"))


class _RefineDecodeInputs(VAEDecodeInputs):
    """Refine-pass decode source of the bundled template."""

    samples: NodeRef = Field(default_factory=lambda: NodeRef.first("sampler_refine"))


class RefineDecodeNode(VAEDecodeNode):
    """``refine_decode`` node of the bundled template."""

    inputs: _RefineDecodeInputs = Field(default_factory=_RefineDecodeInputs)


class VAEEncodeInputs(NodeInputs):
    """Inputs of ``VAEEncode``."""

    pixels: NodeRef = Field(default_factory=lambda: NodeRef.first("upscale"))
    vae: NodeRef = Field(default_factory=lambda: NodeRef.third("loader"))


class VAEEncodeNode(WireNode):
    """``VAEEncode`` node."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["VAEEncode"] = "VAEEncode"
    inputs: VAEEncodeInputs = Field(default_factory=VAEEncodeInputs)
    meta: NodeMeta = Field(validation_alias="_meta", serialization_alias="_meta")

    @classmethod
    def default(cls) -> Self:
        """Template re-encode node."""
        return cls(meta=NodeMeta(title="VAE Encode"))


class PreviewImageInputs(NodeInputs):
    """Inputs of ``PreviewImage``."""

    images: NodeRef = Field(default_factory=lambda: NodeRef.first("refine_decode"))


class PreviewImageNode(WireNode):
    """``PreviewImage`` node."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["PreviewImage"] = "PreviewImage"
    inputs: PreviewImageInputs = Field(default_factory=PreviewImageInputs)
    meta: NodeMeta = Field(validation_alias="_meta", serialization_alias="_meta")

    @classmethod
    def default(cls) -> Self:
        """Template preview node."""
        return cls(meta=NodeMeta(title="Preview Image"))


class ImageScaleByInputs(NodeInputs):
    """Inputs of ``ImageScaleBy``."""

    upscale_method: str = "nearest-exact"
    scale_by: float = 2.3
    image: NodeRef = Field(default_factory=lambda: NodeRef.first("decode"))


class ImageScaleByNode(WireNode):
    """``ImageScaleBy`` node."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["ImageScaleBy"] = "ImageScaleBy"
    inputs: ImageScaleByInputs = Field(default_factory=ImageScaleByInputs)
    meta: NodeMeta = Field(validation_alias="_meta", serialization_alias="_meta")

    @classmethod
    def default(cls) -> Self:
        """Template upscale node."""
        return cls(meta=NodeMeta(title="Upscale Image By"))


class SamplerInputs(NodeInputs):
    """Inputs of ``KSamplerAdvanced``."""

    add_noise: Literal["enable"] = "enable"
    noise_seed: int = 1072236688235494
    steps: int = 21
    cfg: float = 7.0
    sampler_name: str = "er_sde"
    scheduler: str = "beta"
    start_at_step: int = 0
    end_at_step: int = 999
    return_with_leftover_noise: Literal["disable"] = "disable"
    model: NodeRef = Field(default_factory=lambda: NodeRef.first("loader"))
    positive: NodeRef = Field(default_factory=lambda: NodeRef.first("positive"))
    negative: NodeRef = Field(default_factory=lambda: NodeRef.first("negative"))
    latent_image: NodeRef = Field(default_factory=lambda: NodeRef.first("latent"))


class RefineSamplerInputs(SamplerInputs):
    """Refine-pass schedule of the bundled template."""

    cfg: float = 4.5
    sampler_name: str = "er_sde"
    scheduler: str = "karras"
    latent_image: NodeRef = Field(default_factory=lambda: NodeRef.first("encode"))


class KSamplerAdvancedNode(WireNode):
    """``KSamplerAdvanced`` node — the base pass."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["KSamplerAdvanced"] = "KSamplerAdvanced"
    inputs: SamplerInputs = Field(default_factory=SamplerInputs)
    meta: NodeMeta = Field(validation_alias="_meta", serialization_alias="_meta")

    @classmethod
    def default(cls) -> Self:
        """Template base-pass sampler node."""
        return cls(meta=NodeMeta(title="KSampler (Advanced)"))


class RefineSamplerNode(KSamplerAdvancedNode):
    """``sampler_refine`` node of the bundled template."""

    inputs: RefineSamplerInputs = Field(default_factory=RefineSamplerInputs)


class SimpleDecodeInputs(VAEDecodeInputs):
    """Decode source of the single-pass template."""

    samples: NodeRef = Field(default_factory=lambda: NodeRef.first("sampler_base"))


class SimpleDecodeNode(VAEDecodeNode):
    """``decode`` node of the single-pass template."""

    inputs: SimpleDecodeInputs = Field(default_factory=SimpleDecodeInputs)


class SimplePreviewInputs(PreviewImageInputs):
    """Preview source of the single-pass template."""

    images: NodeRef = Field(default_factory=lambda: NodeRef.first("decode"))


class SimplePreviewNode(PreviewImageNode):
    """``preview`` node of the single-pass template."""

    inputs: SimplePreviewInputs = Field(default_factory=SimplePreviewInputs)


class SimpleSamplerInputs(SamplerInputs):
    """Sole sampler schedule of the single-pass template."""

    end_at_step: int = 999


class SimpleSamplerNode(KSamplerAdvancedNode):
    """``sampler_base`` node of the single-pass template."""

    inputs: SimpleSamplerInputs = Field(default_factory=SimpleSamplerInputs)


class BaseTxt2ImgGraph(BaseGraph):
    """Shared node set and generation knobs of every bundled txt2img template.

    Node fields are typed here so a subclass can only narrow them, and
    every ``with_*`` knob lives here too, so a knob can never be applied to
    one template and silently missing from another.  A template states only
    what actually differs: :meth:`samplers`, :meth:`output_scale`, and the
    upscale/refine/loader nodes its shape adds.
    """

    loader: CheckpointLoaderNode
    """Checkpoint loader node."""

    latent: EmptyLatentNode
    """Empty latent canvas node."""

    positive: PositivePromptNode
    """Positive prompt encode node."""

    negative: NegativePromptNode
    """Negative prompt encode node."""

    def samplers(self) -> tuple[KSamplerAdvancedNode, ...]:
        """Return this template's sampler nodes in pass order.

        Abstract by convention: every concrete template declares its own
        sampler set, which is what makes :meth:`with_sampler` apply the
        same knobs to every pass of either shape.
        """
        raise NotImplementedError

    def output_scale(self) -> float:
        """Linear factor between this template's latent canvas and its finished image.

        ``1.0`` means the latent *is* the output; a template that upscales
        before its final pass overrides this so :func:`resolve_canvas` can
        size the base canvas for a megapixel budget of the *finished* image.
        """
        return 1.0

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
        """Update sampler parameters on every sampler of this template.

        Keeping the seeds/steps/cfg of a multi-pass template aligned is the
        sane semantic for a single generation.  Return *self* for chaining.
        """
        for sampler in self.samplers():
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


class GraphSimple(BaseTxt2ImgGraph):
    """The single-pass txt2img graph — no upscale, no refine.

    One sampler pass decodes straight to the preview, so the finished
    image is exactly the latent canvas: ``mp`` / ``prop`` size it without
    the ``scale**2`` division the high-res template needs.
    """

    model_source: ClassVar[NodeRef] = NodeRef.first("loader")
    clip_source: ClassVar[NodeRef] = NodeRef.second("loader")
    model_inputs: ClassVar[tuple[RewireField, ...]] = (RewireField.sampler_base,)
    clip_inputs: ClassVar[tuple[RewireField, ...]] = (RewireField.positive, RewireField.negative)

    decode: SimpleDecodeNode
    """Decode node feeding the preview directly."""

    preview: SimplePreviewNode
    """Preview image node."""

    sampler_base: SimpleSamplerNode
    """The sole sampler pass."""

    def samplers(self) -> tuple[KSamplerAdvancedNode, ...]:
        """Return the single sampler pass of the low-res template."""
        return (self.sampler_base,)

    @classmethod
    def default(cls) -> Self:
        """Assemble the single-pass template from each node class's own default.

        Generation knobs (prompt, size, sampler, checkpoint) are
        overridden per request by the client via the ``with_*`` builders.
        """
        return cls(
            loader=CheckpointLoaderNode.default(),
            latent=EmptyLatentNode.default(),
            positive=PositivePromptNode.default(),
            negative=NegativePromptNode.default(),
            decode=SimpleDecodeNode.default(),
            preview=SimplePreviewNode.default(),
            sampler_base=SimpleSamplerNode.default(),
        )


class Graph(BaseTxt2ImgGraph):
    """The bundled txt2img → upscale → refine graph, initialised in Python.

    ComfyUI node IDs are arbitrary unique strings, so the Python field
    names double as the wire node IDs — no numeric aliases anywhere.
    :meth:`to_api` produces the exact ComfyUI API-format payload for
    ``POST /prompt``.
    """

    model_source: ClassVar[NodeRef] = NodeRef.first("loader")
    clip_source: ClassVar[NodeRef] = NodeRef.second("loader")
    model_inputs: ClassVar[tuple[RewireField, ...]] = (RewireField.sampler_base, RewireField.sampler_refine)
    clip_inputs: ClassVar[tuple[RewireField, ...]] = (RewireField.positive, RewireField.negative)

    decode: VAEDecodeNode
    """Base-pass decode feeding the upscaler."""

    encode: VAEEncodeNode
    """Re-encode of the upscaled image for the refine pass."""

    refine_decode: RefineDecodeNode
    """Refine-pass decode node."""

    preview: PreviewImageNode
    """Preview image node."""

    upscale: ImageScaleByNode
    """Upscale step node."""

    sampler_base: KSamplerAdvancedNode
    """Base-pass sampler node."""

    sampler_refine: RefineSamplerNode
    """Refine-pass sampler node."""

    def samplers(self) -> tuple[KSamplerAdvancedNode, ...]:
        """Return both sampler passes of the high-res template."""
        return (self.sampler_base, self.sampler_refine)

    def output_scale(self) -> float:
        """Return the upscale factor this template applies before its refine pass."""
        return self.upscale.inputs.scale_by

    @classmethod
    def default(cls) -> Self:
        """Assemble the bundled template from each node class's own default.

        Generation knobs (prompt, size, sampler, checkpoint) are
        overridden per request by the client via the ``with_*`` builders.
        """
        return cls(
            loader=CheckpointLoaderNode.default(),
            latent=EmptyLatentNode.default(),
            positive=PositivePromptNode.default(),
            negative=NegativePromptNode.default(),
            decode=VAEDecodeNode.default(),
            encode=VAEEncodeNode.default(),
            refine_decode=RefineDecodeNode.default(),
            preview=PreviewImageNode.default(),
            upscale=ImageScaleByNode.default(),
            sampler_base=KSamplerAdvancedNode.default(),
            sampler_refine=RefineSamplerNode.default(),
        )
