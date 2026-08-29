"""Typed model of the bundled ComfyUI workflow graph, built in code.

The graph is fully internal — external callers never see or operate on a
workflow — and statically known, so it is *initialised in Python* (no
JSON asset to keep in sync) and only ever **serialized** to ComfyUI's
API format via :meth:`Graph.to_api` on submission.

One pydantic class per node type; fixed wire node IDs live solely as
serialization aliases, so Python code reads/writes named fields
(``graph.loader.inputs.ckpt_name``) while the wire emits
``{"4": {"class_type": ..., "inputs": {...}, "_meta": ...}}`` exactly.
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

    ckpt_name: str


class CheckpointLoaderNode(BaseModel):
    """``CheckpointLoaderSimple`` node (id ``"4"``)."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

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

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["EmptyLatentImage"]
    inputs: EmptyLatentInputs
    meta: NodeMeta = Field(alias="_meta")


class CLIPEncodeInputs(NodeInputs):
    """Inputs of ``CLIPTextEncode``."""

    text: str
    clip: NodeRef


class CLIPEncodeNode(BaseModel):
    """``CLIPTextEncode`` node (ids ``"7"`` positive / ``"8"`` negative)."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["CLIPTextEncode"]
    inputs: CLIPEncodeInputs
    meta: NodeMeta = Field(alias="_meta")


class VAEDecodeInputs(NodeInputs):
    """Inputs of ``VAEDecode``."""

    samples: NodeRef
    vae: NodeRef


class VAEDecodeNode(BaseModel):
    """``VAEDecode`` node (ids ``"9"`` / ``"15"``)."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["VAEDecode"]
    inputs: VAEDecodeInputs
    meta: NodeMeta = Field(alias="_meta")


class VAEEncodeInputs(NodeInputs):
    """Inputs of ``VAEEncode``."""

    pixels: NodeRef
    vae: NodeRef


class VAEEncodeNode(BaseModel):
    """``VAEEncode`` node (id ``"13"``)."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["VAEEncode"]
    inputs: VAEEncodeInputs
    meta: NodeMeta = Field(alias="_meta")


class PreviewImageInputs(NodeInputs):
    """Inputs of ``PreviewImage``."""

    images: NodeRef


class PreviewImageNode(BaseModel):
    """``PreviewImage`` node (id ``"16"``)."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

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

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

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

    model_config = ConfigDict(populate_by_name=True, extra="forbid", validate_assignment=True)

    class_type: Literal["KSamplerAdvanced"]
    inputs: SamplerInputs
    meta: NodeMeta = Field(alias="_meta")


class Graph(BaseModel):
    """The bundled txt2img → upscale → refine graph, initialised in Python.

    Fixed wire node IDs exist only as serialization aliases; all Python
    access goes through named typed fields.  :meth:`to_api` produces the
    exact ComfyUI API-format payload for ``POST /prompt``.
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
    def default(cls) -> Self:
        """Build the bundled graph entirely in Python code.

        Values mirror the original ComfyUI UI export; generation knobs
        (prompt, size, sampler, checkpoint) are overridden per request by
        the client via the ``with_*`` builders.
        """
        clip_prompt = NodeMeta(title="CLIP Text Encode (Prompt)")
        sampler_meta = NodeMeta(title="KSampler (Advanced)")
        return cls(
            loader=CheckpointLoaderNode(
                class_type="CheckpointLoaderSimple",
                inputs=CheckpointLoaderInputs(ckpt_name="catTowerNoobaiXL_v15Vpred.safetensors"),
                meta=NodeMeta(title="Load Checkpoint"),
            ),
            latent=EmptyLatentNode(
                class_type="EmptyLatentImage",
                inputs=EmptyLatentInputs(width=768, height=512, batch_size=1),
                meta=NodeMeta(title="Empty Latent Image"),
            ),
            positive=CLIPEncodeNode(
                class_type="CLIPTextEncode",
                inputs=CLIPEncodeInputs(
                    text=(
                        "best quality,masterpiece,4k,highres,1girl, selfie, holding phone, bedroom, "
                        "morning sunlight, messy bed, pillows, white sheets, pajamas, pink hair, "
                        "blunt bangs, waist-length twin tails, violet eyes,"
                    ),
                    clip=NodeRef(node_id="4", output_index=1),
                ),
                meta=clip_prompt,
            ),
            negative=CLIPEncodeNode(
                class_type="CLIPTextEncode",
                inputs=CLIPEncodeInputs(
                    text=(
                        "worst,lowres,low quality,mulform,sketch,texts,censor,terrible quality,"
                        "garbage,multiple arms,multiple legs,multiple fingers, low quality, "
                        "jpeg artifacts, out of frame, watermark, signature,blurry,texts"
                    ),
                    clip=NodeRef(node_id="4", output_index=1),
                ),
                meta=clip_prompt,
            ),
            decode=VAEDecodeNode(
                class_type="VAEDecode",
                inputs=VAEDecodeInputs(samples=NodeRef(node_id="25", output_index=0), vae=NodeRef(node_id="4", output_index=2)),
                meta=NodeMeta(title="VAE Decode"),
            ),
            encode=VAEEncodeNode(
                class_type="VAEEncode",
                inputs=VAEEncodeInputs(pixels=NodeRef(node_id="19", output_index=0), vae=NodeRef(node_id="4", output_index=2)),
                meta=NodeMeta(title="VAE Encode"),
            ),
            refine_decode=VAEDecodeNode(
                class_type="VAEDecode",
                inputs=VAEDecodeInputs(samples=NodeRef(node_id="26", output_index=0), vae=NodeRef(node_id="4", output_index=2)),
                meta=NodeMeta(title="VAE Decode"),
            ),
            preview=PreviewImageNode(
                class_type="PreviewImage",
                inputs=PreviewImageInputs(images=NodeRef(node_id="15", output_index=0)),
                meta=NodeMeta(title="Preview Image"),
            ),
            upscale=ImageScaleByNode(
                class_type="ImageScaleBy",
                inputs=ImageScaleByInputs(upscale_method="nearest-exact", scale_by=2.3, image=NodeRef(node_id="9", output_index=0)),
                meta=NodeMeta(title="Upscale Image By"),
            ),
            sampler_base=KSamplerAdvancedNode(
                class_type="KSamplerAdvanced",
                inputs=SamplerInputs(
                    add_noise="enable",
                    noise_seed=1072236688235494,
                    steps=21,
                    cfg=7.9,
                    sampler_name="er_sde",
                    scheduler="beta",
                    start_at_step=0,
                    end_at_step=990,
                    return_with_leftover_noise="disable",
                    model=NodeRef(node_id="4", output_index=0),
                    positive=NodeRef(node_id="7", output_index=0),
                    negative=NodeRef(node_id="8", output_index=0),
                    latent_image=NodeRef(node_id="6", output_index=0),
                ),
                meta=sampler_meta,
            ),
            sampler_refine=KSamplerAdvancedNode(
                class_type="KSamplerAdvanced",
                inputs=SamplerInputs(
                    add_noise="enable",
                    noise_seed=1072236688235494,
                    steps=42,
                    cfg=8.5,
                    sampler_name="er_sde",
                    scheduler="beta",
                    start_at_step=20,
                    end_at_step=999,
                    return_with_leftover_noise="disable",
                    model=NodeRef(node_id="4", output_index=0),
                    positive=NodeRef(node_id="7", output_index=0),
                    negative=NodeRef(node_id="8", output_index=0),
                    latent_image=NodeRef(node_id="13", output_index=0),
                ),
                meta=sampler_meta,
            ),
        )

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
