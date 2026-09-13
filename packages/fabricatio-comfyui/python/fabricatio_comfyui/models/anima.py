"""Typed model of the bundled anima workflow graph, built in code.

Mirrors :mod:`fabricatio_comfyui.models.graph` conventions: one pydantic
class per node type, the Python field name doubles as the wire node ID,
and :meth:`AnimaGraph.to_api` produces the exact ComfyUI API-format
payload for ``POST /prompt``.

The anima template differs from the bundled default graph structurally:
the model is loaded as three separate pieces (checkpoint, CLIP, VAE),
sampled once with ``er_sde`` at 32 steps, and rendered at a fixed
1344x1024 canvas.  The three model filenames are **placeholders** in
this module — the client resolves them from config
(:data:`comfyui_config.anima_checkpoint` / ``anima_clip`` / ``anima_vae``)
before submission and fails loudly when a value is missing.
"""

from typing import ClassVar, Literal, Self

from pydantic import ConfigDict, Field

from fabricatio_comfyui.models.graph import (
    BaseTxt2ImgGraph,
    CLIPEncodeInputs,
    KSamplerAdvancedNode,
    NodeInputs,
    NodeMeta,
    NodeRef,
    RewireField,
    SamplerInputs,
    WireNode,
)


class AnimaCheckpointLoaderInputs(NodeInputs):
    """Inputs of ``CheckpointLoaderSimple`` in the anima template."""

    ckpt_name: str = "<anima_checkpoint>"


class AnimaCheckpointLoaderNode(WireNode):
    """``CheckpointLoaderSimple`` node of the anima template."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["CheckpointLoaderSimple"] = "CheckpointLoaderSimple"
    inputs: AnimaCheckpointLoaderInputs = Field(default_factory=AnimaCheckpointLoaderInputs)
    meta: NodeMeta = Field(validation_alias="_meta", serialization_alias="_meta")

    @classmethod
    def default(cls) -> Self:
        """Anima checkpoint loader node."""
        return cls(meta=NodeMeta(title="Load Checkpoint"))


class AnimaCLIPLoaderInputs(NodeInputs):
    """Inputs of ``CLIPLoader`` in the anima template."""

    clip_name: str = "<anima_clip>"
    type: Literal["stable_diffusion"] = "stable_diffusion"
    device: Literal["default"] = "default"


class AnimaCLIPLoaderNode(WireNode):
    """``CLIPLoader`` node of the anima template."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["CLIPLoader"] = "CLIPLoader"
    inputs: AnimaCLIPLoaderInputs = Field(default_factory=AnimaCLIPLoaderInputs)
    meta: NodeMeta = Field(validation_alias="_meta", serialization_alias="_meta")

    @classmethod
    def default(cls) -> Self:
        """Anima CLIP loader node."""
        return cls(meta=NodeMeta(title="Load CLIP"))


class AnimaVAELoaderInputs(NodeInputs):
    """Inputs of ``VAELoader`` in the anima template."""

    vae_name: str = "<anima_vae>"


class AnimaVAELoaderNode(WireNode):
    """``VAELoader`` node of the anima template."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["VAELoader"] = "VAELoader"
    inputs: AnimaVAELoaderInputs = Field(default_factory=AnimaVAELoaderInputs)
    meta: NodeMeta = Field(validation_alias="_meta", serialization_alias="_meta")

    @classmethod
    def default(cls) -> Self:
        """Anima VAE loader node."""
        return cls(meta=NodeMeta(title="Load VAE"))


class AnimaEmptyLatentInputs(NodeInputs):
    """Inputs of ``EmptyLatentImage`` in the anima template."""

    width: int = 1344
    height: int = 1024
    batch_size: int = 1


class AnimaEmptyLatentNode(WireNode):
    """``EmptyLatentImage`` node of the anima template."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["EmptyLatentImage"] = "EmptyLatentImage"
    inputs: AnimaEmptyLatentInputs = Field(default_factory=AnimaEmptyLatentInputs)
    meta: NodeMeta = Field(validation_alias="_meta", serialization_alias="_meta")

    @classmethod
    def default(cls) -> Self:
        """Anima empty latent node at the fixed 4:3 1.3MP canvas."""
        return cls(meta=NodeMeta(title="Empty Latent Image"))


class AnimaPositivePromptInputs(CLIPEncodeInputs):
    """Positive prompt of the anima template."""

    clip: NodeRef = Field(default_factory=lambda: NodeRef.first("clip"))
    text: str = (
        "best quality,masterpiece,4k,highres,1girl, selfie, holding phone, bedroom, "
        "morning sunlight, messy bed, pillows, white sheets, pajamas, pink hair, "
        "blunt bangs, waist-length twin tails, violet eyes,"
    )


class AnimaNegativePromptInputs(CLIPEncodeInputs):
    """Negative prompt of the anima template."""

    clip: NodeRef = Field(default_factory=lambda: NodeRef.first("clip"))
    text: str = (
        "worst,lowres,low quality,mulform,sketch,texts,censor,terrible quality,"
        "garbage,multiple arms,multiple legs,multiple fingers, low quality, "
        "jpeg artifacts, out of frame, watermark, signature,blurry,texts"
    )


class AnimaPositivePromptNode(WireNode):
    """``positive`` node of the anima template."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["CLIPTextEncode"] = "CLIPTextEncode"
    inputs: AnimaPositivePromptInputs = Field(default_factory=AnimaPositivePromptInputs)
    meta: NodeMeta = Field(validation_alias="_meta", serialization_alias="_meta")

    @classmethod
    def default(cls) -> Self:
        """Anima positive prompt node."""
        return cls(meta=NodeMeta(title="CLIP Text Encode (Prompt)"))


class AnimaNegativePromptNode(WireNode):
    """``negative`` node of the anima template."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["CLIPTextEncode"] = "CLIPTextEncode"
    inputs: AnimaNegativePromptInputs = Field(default_factory=AnimaNegativePromptInputs)
    meta: NodeMeta = Field(validation_alias="_meta", serialization_alias="_meta")

    @classmethod
    def default(cls) -> Self:
        """Anima negative prompt node."""
        return cls(meta=NodeMeta(title="CLIP Text Encode (Prompt)"))


class AnimaSamplerInputs(SamplerInputs):
    """Inputs of ``KSamplerAdvanced`` in the anima template."""

    steps: int = 32
    cfg: float = 7.0
    sampler_name: str = "er_sde"
    scheduler: str = "karras"
    end_at_step: int = 999


class AnimaSamplerNode(KSamplerAdvancedNode):
    """``KSamplerAdvanced`` node of the anima template."""

    inputs: AnimaSamplerInputs = Field(default_factory=AnimaSamplerInputs)


class AnimaVAEDecodeInputs(NodeInputs):
    """Inputs of ``VAEDecode`` in the anima template."""

    samples: NodeRef = Field(default_factory=lambda: NodeRef.first("sampler"))
    vae: NodeRef = Field(default_factory=lambda: NodeRef.first("vae"))


class AnimaVAEDecodeNode(WireNode):
    """``VAEDecode`` node of the anima template."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["VAEDecode"] = "VAEDecode"
    inputs: AnimaVAEDecodeInputs = Field(default_factory=AnimaVAEDecodeInputs)
    meta: NodeMeta = Field(validation_alias="_meta", serialization_alias="_meta")

    @classmethod
    def default(cls) -> Self:
        """Anima decode node."""
        return cls(meta=NodeMeta(title="VAE Decode"))


class AnimaPreviewInputs(NodeInputs):
    """Inputs of ``PreviewImage`` in the anima template."""

    images: NodeRef = Field(default_factory=lambda: NodeRef.first("decode"))


class AnimaPreviewNode(WireNode):
    """``PreviewImage`` node of the anima template."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["PreviewImage"] = "PreviewImage"
    inputs: AnimaPreviewInputs = Field(default_factory=AnimaPreviewInputs)
    meta: NodeMeta = Field(validation_alias="_meta", serialization_alias="_meta")

    @classmethod
    def default(cls) -> Self:
        """Anima preview node."""
        return cls(meta=NodeMeta(title="Preview Image"))


class AnimaGraph(BaseTxt2ImgGraph):
    """The bundled anima txt2img graph, initialised in Python.

    Single sampler pass (no refine); model pieces load from separate
    checkpoint / CLIP / VAE nodes.  The three model filenames default to
    placeholder tokens and MUST be resolved from config before
    submission — see :data:`comfyui_config.anima_checkpoint` and friends.
    """

    model_source: ClassVar[NodeRef] = NodeRef.first("loader")
    clip_source: ClassVar[NodeRef] = NodeRef.first("clip")
    clip_inputs: ClassVar[tuple[RewireField, ...]] = (RewireField.positive, RewireField.negative)

    loader: AnimaCheckpointLoaderNode
    """Checkpoint loader node."""

    clip: AnimaCLIPLoaderNode
    """CLIP loader node."""

    vae: AnimaVAELoaderNode
    """VAE loader node."""

    latent: AnimaEmptyLatentNode
    """Empty latent canvas node."""

    positive: AnimaPositivePromptNode
    """Positive prompt encode node."""

    negative: AnimaNegativePromptNode
    """Negative prompt encode node."""

    sampler: AnimaSamplerNode
    """Sampler node."""

    decode: AnimaVAEDecodeNode
    """Decode node."""

    preview: AnimaPreviewNode
    """Preview image node."""

    @classmethod
    def default(cls) -> Self:
        """Assemble the anima template from each node class's own default.

        Generation knobs (prompt, size, sampler, checkpoint) are
        overridden per request by the client via the ``with_*`` builders;
        the checkpoint / CLIP / VAE placeholders are resolved there too.
        """
        return cls(
            loader=AnimaCheckpointLoaderNode.default(),
            clip=AnimaCLIPLoaderNode.default(),
            vae=AnimaVAELoaderNode.default(),
            latent=AnimaEmptyLatentNode.default(),
            positive=AnimaPositivePromptNode.default(),
            negative=AnimaNegativePromptNode.default(),
            sampler=AnimaSamplerNode.default(),
            decode=AnimaVAEDecodeNode.default(),
            preview=AnimaPreviewNode.default(),
        )

    def sampler_fields(self) -> tuple[RewireField, ...]:
        """Return the single sampler pass of the anima template."""
        return (RewireField.sampler,)

    def with_checkpoint(self, ckpt_name: str) -> Self:
        """Set the checkpoint on the loader node; return *self* for chaining."""
        self.loader.inputs.ckpt_name = ckpt_name
        return self

    def with_clip(self, clip_name: str) -> Self:
        """Set the CLIP on the clip loader node; return *self* for chaining."""
        self.clip.inputs.clip_name = clip_name
        return self

    def with_vae(self, vae_name: str) -> Self:
        """Set the VAE on the vae loader node; return *self* for chaining."""
        self.vae.inputs.vae_name = vae_name
        return self
