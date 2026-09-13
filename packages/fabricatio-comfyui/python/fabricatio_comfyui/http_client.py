"""Concrete ComfyUI HTTP client.

:class:`ComfyUIHttpClient` is the sole implementation of
:class:`ComfyUIClientBase`.  It owns the ``httpx.AsyncClient`` lifecycle
and all REST endpoints.

Clients are process-wide singletons per base URL via the cached
:func:`get_comfyui_client` factory (the ``fabricatio-milvus`` pattern):
the mixin fetches the shared client when needed and the connection pool
is reused across every instance instead of being bound (and leaked) per
instance.  Direct construction / ``async with`` stays available for
tests and alternate backends that want a private pool::

    async with ComfyUIHttpClient.create() as client:
        results = await client.generate("a mountain landscape")
        await client.download_images(results[0], "./outputs")
"""

import asyncio
import io
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import IO, Self, Unpack, final

import httpx
from fabricatio_core.journal import logger
from fabricatio_core.utils import first_available
from PIL import Image

from fabricatio_comfyui.client_base import ComfyUIClientBase
from fabricatio_comfyui.config import comfyui_config
from fabricatio_comfyui.models.anima import AnimaGraph
from fabricatio_comfyui.models.comfyui import (
    ExecutionResult,
    HistoryEntry,
    OutputImage,
    PromptRequest,
    PromptResponse,
    QueueInfo,
    UploadResponse,
    ViewImageParams,
)
from fabricatio_comfyui.models.graph import (
    BaseGraph,
    BasePromptedGraph,
    BaseTxt2ImgGraph,
    Graph,
    GraphImg2Img,
    GraphSimple,
    LoraSpec,
)
from fabricatio_comfyui.models.kwargs_types import (
    Img2ImgKwargs,
    PollKwargs,
    TemplateKwargs,
    UploadKwargs,
    ViewImageKwargs,
)
from fabricatio_comfyui.models.resolution import resolve_canvas

__all__ = ["ComfyUIHttpClient", "get_comfyui_client"]


@cache
def _cached_client_for_loop(loop: asyncio.AbstractEventLoop, base_url: str) -> "ComfyUIHttpClient":
    """Build the shared client for *base_url* bound to *loop*'s lifetime."""
    return ComfyUIHttpClient.create(base_url)


def get_comfyui_client(base_url: str) -> "ComfyUIHttpClient":
    """Return the shared client for *base_url* on the current event loop.

    One client (and therefore one ``httpx`` connection pool) per distinct
    (event loop, base URL) pair — the ``fabricatio-milvus`` pattern, with
    one extra key: ``httpx.AsyncClient`` pools are event-loop-bound, so a
    plain per-URL ``@cache`` would hand a pool from a closed loop to the
    next one (``RuntimeError: Event loop is closed``).  Within a single
    loop the pool is created once and reused by every holder; a fresh
    loop gets a fresh pool, keeping pytest-asyncio and multi-loop apps
    safe.  Never ``aclose`` the returned client — other holders on the
    same loop may still be using it.
    """
    return _cached_client_for_loop(asyncio.get_running_loop(), base_url)


@final
@dataclass
class ComfyUIHttpClient(ComfyUIClientBase):
    """Async HTTP client for the ComfyUI REST API.

    Manages an ``httpx.AsyncClient`` connection pool.  Prefer the shared
    :func:`get_comfyui_client` factory for normal use; construct directly
    (or via :meth:`create` with ``async with``) only when a private pool
    is wanted.
    """

    source: httpx.AsyncClient

    @classmethod
    def create(cls, base_url: str | None = None) -> Self:
        """Build a client from the global :data:`comfyui_config`.

        The returned client owns its own ``httpx.AsyncClient`` — close it
        via ``await client.aclose()`` or, preferably, ``async with``.
        """
        return cls(
            source=httpx.AsyncClient(
                base_url=first_available((base_url, comfyui_config.base_url)).rstrip("/"),
                timeout=httpx.Timeout(comfyui_config.timeout),
            ),
        )

    def client_id(self) -> str:
        """Return the client ID derived from the configured server URL."""
        return comfyui_config.base_url.rstrip("/").lower()

    # ------------------------------------------------------------------
    # Lifecycle — explicit close; the context-manager pair is inherited
    # from :class:`ComfyUIClientBase` and delegates here
    # ------------------------------------------------------------------

    async def aclose(self) -> None:
        """Close the underlying ``httpx.AsyncClient`` connection pool."""
        await self.source.aclose()

    # ------------------------------------------------------------------
    # Low-level HTTP
    # ------------------------------------------------------------------

    async def _post(
        self,
        path: str,
        *,
        json_data: dict[str, object] | None = None,
        body: bytes | None = None,
        files: dict[str, tuple[str, IO[bytes], str]] | None = None,
        timeout: float | None = None,
    ) -> dict[str, object]:
        """Send a POST request and return the JSON response.

        *json_data*, *body*, and *files* are mutually exclusive content
        shapes; the caller picks exactly one.  ``body`` is forwarded via
        httpx's ``content=`` parameter (raw request body).
        """
        resp = await self.source.post(
            path,
            json=json_data,
            content=body,
            files=files,
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()

    async def _get(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> dict[str, object] | bytes:
        """Send a GET request; return bytes for binary content, JSON otherwise."""
        resp = await self.source.get(path, params=params, timeout=timeout)
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "")
        if ct.startswith("image/") or ct.startswith("application/octet"):
            return resp.content
        return resp.json()

    async def _upload(
        self,
        path: str,
        *,
        files: dict[str, tuple[str, IO[bytes], str]],
        data: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> dict[str, object]:
        """Upload files via multipart POST and return the JSON response."""
        resp = await self.source.post(path, data=data, files=files, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # REST endpoints (ComfyUIClientBase implementation)
    # ------------------------------------------------------------------

    def _apply_common[T: BasePromptedGraph](
        self,
        template: T,
        *,
        checkpoint: str | None,
        loras: list[LoraSpec] | None,
    ) -> T:
        """Apply the checkpoint and the LoRA chain shared by every entry point.

        *checkpoint* is the caller-resolved name (each template builder
        resolves it against :data:`comfyui_config` with its own rung
        order) and is applied when given; ``None`` keeps the template's
        own checkpoint.
        """
        if checkpoint is not None:
            template.with_checkpoint(checkpoint)
        for spec in loras or ():
            template.with_lora(spec.lora_name, strength=spec.strength)
        return template

    def _default_template(self, *, checkpoint: str | None, loras: list[LoraSpec] | None = None) -> Graph:
        """Build the bundled two-pass template with the shared checkpoint/LoRA chain."""
        return self._apply_common(
            Graph.default(),
            checkpoint=checkpoint or comfyui_config.checkpoint,
            loras=loras,
        )

    def _simple_template(self, *, checkpoint: str | None, loras: list[LoraSpec] | None = None) -> GraphSimple:
        """Build the bundled single-pass template with the shared checkpoint/LoRA chain."""
        return self._apply_common(
            GraphSimple.default(),
            checkpoint=checkpoint or comfyui_config.checkpoint,
            loras=loras,
        )

    def _anima_template(
        self,
        *,
        checkpoint: str | None = None,
        clip: str | None = None,
        vae: str | None = None,
        loras: list[LoraSpec] | None = None,
    ) -> AnimaGraph:
        """Build the bundled anima template, resolving its model filenames.

        Each filename falls back to :data:`comfyui_config` (``checkpoint``
        additionally to the generic :attr:`checkpoint` rung); unset names
        fail loudly.
        """
        checkpoint_name = checkpoint or comfyui_config.checkpoint or comfyui_config.anima_checkpoint
        if checkpoint_name is None:
            raise ValueError(
                "generate_anima needs a checkpoint: pass checkpoint= or set [ext.comfyui] checkpoint or anima_checkpoint"
            )
        clip_name = clip or comfyui_config.anima_clip
        if clip_name is None:
            raise ValueError("generate_anima needs a CLIP: pass clip= or set [ext.comfyui] anima_clip")
        vae_name = vae or comfyui_config.anima_vae
        if vae_name is None:
            raise ValueError("generate_anima needs a VAE: pass vae= or set [ext.comfyui] anima_vae")
        template = AnimaGraph.default().with_checkpoint(checkpoint_name).with_clip(clip_name).with_vae(vae_name)
        return self._apply_common(template, checkpoint=checkpoint_name, loras=loras)

    def _render_graph(
        self,
        prompt: str,
        *,
        template: BaseTxt2ImgGraph | AnimaGraph,
        **kwargs: Unpack[TemplateKwargs],
    ) -> BaseTxt2ImgGraph | AnimaGraph:
        """Copy *template* and apply the overrides for one prompt.

        Only provided (non-``None``) knobs change the graph; canvas and
        checkpoint knobs fall back to :data:`comfyui_config` before the
        template's own values, and computed sizes snap to the 64px grid.
        """
        graph = template.model_copy(deep=True)
        if prompt:
            graph.with_positive_prompt(prompt)
        if (negative_prompt := kwargs.get("negative_prompt")) is not None:
            graph.with_negative_prompt(negative_prompt)
        size_mp = first_available((kwargs.get("mp"), comfyui_config.mp), raise_exception=False)
        size_prop = first_available((kwargs.get("prop"), comfyui_config.prop), raise_exception=False)
        if size_mp is not None or size_prop is not None:
            # mp budgets the FINAL image; a template that upscales after the base
            # pass (ImageScaleBy) therefore carries mp / scale**2 on its latent,
            # and templates without an upscale step report scale 1.0 (latent = output).
            width, height = resolve_canvas(
                mp=size_mp,
                prop=size_prop,
                base=(graph.latent.inputs.width, graph.latent.inputs.height),
                scale=template.output_scale(),
            )
            graph.with_resolution(width=width, height=height)
        seed = kwargs.get("seed")
        steps = kwargs.get("steps")
        cfg = kwargs.get("cfg")
        if seed is not None or steps is not None or cfg is not None:
            graph.with_sampler(seed=seed, steps=steps, cfg=cfg)
        return graph

    async def _queue_and_wait(
        self,
        graphs: Iterable[BaseGraph],
        *,
        front: bool = False,
        timeout: float | None = None,
    ) -> list[ExecutionResult]:
        """Queue each graph and poll it to completion, in order.

        Prompts run sequentially; the return holds one execution result per
        graph, in input order, without downloading images.  When the
        awaiting task is cancelled (e.g. Ctrl+C), the running job is
        interrupted server-side before the cancellation propagates.
        """
        results: list[ExecutionResult] = []
        for graph in graphs:
            req = PromptRequest(prompt=graph.to_api(), client_id=self.client_id(), front=front)
            data = await self._post("/prompt", json_data=req.model_dump(exclude_unset=True))
            resp = PromptResponse.from_raw(data)
            try:
                results.append(await self.wait_for_completion(resp.prompt_id, timeout=timeout))
            except asyncio.CancelledError:
                logger.info("ComfyUI generation cancelled — interrupting the server-side job")
                try:
                    await self.interrupt()
                except httpx.HTTPError:
                    logger.warn("Failed to interrupt ComfyUI after cancellation")
                raise
        return results

    async def _submit_txt2img(
        self,
        prompt: str | list[str],
        template: BaseTxt2ImgGraph | AnimaGraph,
        *,
        front: bool,
        timeout: float | None,
        **kwargs: Unpack[TemplateKwargs],
    ) -> list[ExecutionResult]:
        """Render *template* once per prompt and queue the renders in order.

        Only the provided (non-``None``) template knobs
        (:class:`~fabricatio_comfyui.models.kwargs_types.TemplateKwargs`)
        override the template; unset knobs keep the template's value, with
        canvas and checkpoint falling back to :data:`comfyui_config` first.
        """
        prompts = [prompt] if isinstance(prompt, str) else list(prompt)
        graphs = (self._render_graph(one, template=template, **kwargs) for one in prompts)
        return await self._queue_and_wait(graphs, front=front, timeout=timeout)

    async def generate(
        self,
        prompt: str | list[str],
        *,
        front: bool = False,
        timeout: float | None = None,
        **kwargs: Unpack[TemplateKwargs],
    ) -> list[ExecutionResult]:
        """Queue one or more prompts on the bundled two-pass template and poll each to completion.

        The workflow graph is built internally — callers never see or
        construct one.  The two-pass template samples a base canvas,
        upscales it, and refines it on a second pass, so *mp* sizes the
        base canvas such that the upscaled output lands at the budget.
        *front* enqueues at the head of the queue and *timeout* bounds
        each poll — both are queueing knobs consumed here and never reach
        the template.
        """
        return await self._submit_txt2img(
            prompt,
            self._default_template(checkpoint=kwargs.get("checkpoint"), loras=kwargs.get("loras")),
            front=front,
            timeout=timeout,
            **kwargs,
        )

    async def generate_simple(
        self,
        prompt: str | list[str],
        *,
        front: bool = False,
        timeout: float | None = None,
        **kwargs: Unpack[TemplateKwargs],
    ) -> list[ExecutionResult]:
        """Queue one or more prompts on the bundled single-pass template and poll each to completion.

        The single-pass template skips the upscale/refine branch — the
        finished image is exactly the latent canvas, so *mp* / *prop*
        size it directly.
        """
        return await self._submit_txt2img(
            prompt,
            self._simple_template(checkpoint=kwargs.get("checkpoint"), loras=kwargs.get("loras")),
            front=front,
            timeout=timeout,
            **kwargs,
        )

    async def generate_anima(
        self,
        prompt: str | list[str],
        *,
        clip: str | None = None,
        vae: str | None = None,
        front: bool = False,
        timeout: float | None = None,
        **kwargs: Unpack[TemplateKwargs],
    ) -> list[ExecutionResult]:
        """Queue one or more prompts on the bundled anima template and poll each to completion.

        The anima template loads checkpoint / CLIP / VAE from separate
        nodes and samples once at a fixed 4:3 canvas (*mp* / *prop*
        overridable).  *clip* / *vae* fall back to ``[ext.comfyui]
        anima_clip`` / ``anima_vae`` and *checkpoint* (via
        :class:`~fabricatio_comfyui.models.kwargs_types.TemplateKwargs`)
        to ``checkpoint`` / ``anima_checkpoint`` — unset filenames fail
        loudly.
        """
        return await self._submit_txt2img(
            prompt,
            self._anima_template(checkpoint=kwargs.get("checkpoint"), clip=clip, vae=vae, loras=kwargs.get("loras")),
            front=front,
            timeout=timeout,
            **kwargs,
        )

    @staticmethod
    def _input_image_name(uploaded: UploadResponse) -> str:
        """Return the ``LoadImage`` value for an uploaded file (``subfolder/name``)."""
        return f"{uploaded.subfolder}/{uploaded.name}" if uploaded.subfolder else uploaded.name

    async def _image_dimensions(self, image: str | Path) -> tuple[int, int]:
        """Return the ``(width, height)`` of a local image file or a server-side input image."""
        if isinstance(image, Path):
            with Image.open(image) as img:
                return img.size
        subfolder, _, filename = image.rpartition("/")
        raw = await self.get_image(filename=filename, subfolder=subfolder, image_type="input")
        with Image.open(io.BytesIO(raw)) as img:
            return img.size

    async def generate_img2img(
        self,
        prompt: str | list[str],
        image: str | Path,
        *,
        denoise: float | None = None,
        front: bool = False,
        timeout: float | None = None,
        **kwargs: Unpack[Img2ImgKwargs],
    ) -> list[ExecutionResult]:
        """Queue one or more img2img prompts against *image* and poll each to completion.

        The bundled img2img template scales the image toward the megapixel
        budget, encodes it, and resamples it at partial denoise on the
        highres template's refine schedule.  *image* is either a local
        file — passed as a :class:`pathlib.Path` and uploaded via
        ``POST /upload/image`` first — or the exact name of an image
        already in the server's input directory.  A ``str`` that names an
        existing local file is rejected as ambiguous rather than silently
        resolved one way.  The remaining knobs mirror :meth:`generate`: a
        *mp* budget is applied as the upscale factor derived from the
        image's own dimensions, and *denoise* maps to the sampler's start
        step.  There is no *prop*: the aspect ratio belongs to the input
        image.
        """
        prompts = [prompt] if isinstance(prompt, str) else list(prompt)
        if isinstance(image, str) and Path(image).is_file():
            raise ValueError(
                f"{image!r} names an existing local file — pass it as Path(...) to upload it, "
                "or pass the exact name of an image already in the server's input directory"
            )
        template = self._apply_common(
            GraphImg2Img.default(),
            checkpoint=kwargs.get("checkpoint") or comfyui_config.checkpoint,
            loras=kwargs.get("loras"),
        )
        size_mp = first_available((kwargs.get("mp"), comfyui_config.mp), raise_exception=False)
        if size_mp is not None:
            template.with_target_mp(size_mp, image_size=await self._image_dimensions(image))
        if isinstance(image, Path):
            uploaded = await self.upload_image(image)
            template.with_image(self._input_image_name(uploaded))
        else:
            template.with_image(image)
        if (negative_prompt := kwargs.get("negative_prompt")) is not None:
            template.with_negative_prompt(negative_prompt)
        seed = kwargs.get("seed")
        steps = kwargs.get("steps")
        cfg = kwargs.get("cfg")
        template.with_sampler(seed=seed, steps=steps, cfg=cfg)
        if denoise is not None:
            template.with_denoise(denoise)

        def _graphs() -> Iterable[BaseGraph]:
            for one in prompts:
                graph = template.model_copy(deep=True)
                if one:
                    graph.with_positive_prompt(one)
                yield graph

        return await self._queue_and_wait(_graphs(), front=front, timeout=timeout)

    async def get_queue_info(self) -> QueueInfo:
        """Get current queue status via ``GET /queue``."""
        raw = await self._get("/queue")
        if isinstance(raw, bytes):
            raise RuntimeError(f"Unexpected binary response from /queue: {len(raw)} bytes")
        return QueueInfo.from_raw(raw)

    async def get_history(self, prompt_id: str) -> HistoryEntry | None:
        """Get execution history via ``GET /history/{prompt_id}``."""
        raw = await self._get(f"/history/{prompt_id}")
        if isinstance(raw, bytes):
            raise RuntimeError(f"Unexpected binary response from /history: {len(raw)} bytes")
        return HistoryEntry.from_history_response(raw, prompt_id)

    async def interrupt(self) -> None:
        """Interrupt the currently running workflow via ``POST /interrupt``."""
        await self._post("/interrupt")

    async def get_image(
        self,
        filename: str,
        **kwargs: Unpack[ViewImageKwargs],
    ) -> bytes:
        """Download a generated image via ``GET /view``."""
        subfolder = kwargs.get("subfolder", "")
        image_type = kwargs.get("image_type", "output")
        params = ViewImageParams(filename=filename, subfolder=subfolder, type=image_type)
        result = await self._get("/view", params=params.to_params())
        if isinstance(result, dict):
            raise RuntimeError(f"Failed to retrieve image {filename}: {result}")
        return result

    async def upload_image(
        self,
        image_path: str | Path,
        **kwargs: Unpack[UploadKwargs],
    ) -> UploadResponse:
        """Upload an image via ``POST /upload/image``."""
        image_type = kwargs.get("image_type", "input")
        overwrite = kwargs.get("overwrite", True)
        p = Path(image_path)
        with p.open("rb") as f:
            files: dict[str, tuple[str, IO[bytes], str]] = {"image": (p.name, f, "image/png")}
            data = {"type": image_type, "overwrite": str(overwrite).lower()}
            raw = await self._upload("/upload/image", files=files, data=data)
        return UploadResponse.from_raw(raw)

    async def wait_for_completion(
        self,
        prompt_id: str,
        **kwargs: Unpack[PollKwargs],
    ) -> ExecutionResult:
        """Poll ``GET /history/{prompt_id}`` until completion."""
        poll_interval = kwargs.get("poll_interval", 1.0)
        timeout = kwargs.get("timeout")
        effective_timeout = timeout or comfyui_config.timeout
        loop = asyncio.get_running_loop()
        deadline = loop.time() + effective_timeout

        while True:
            if loop.time() > deadline:
                raise TimeoutError(f"ComfyUI prompt {prompt_id} timed out after {effective_timeout}s")

            entry = await self.get_history(prompt_id)
            if entry is not None:
                return ExecutionResult.from_history(prompt_id, entry)

            await asyncio.sleep(poll_interval)

    async def download_images(self, result: ExecutionResult, download_dir: str | Path) -> list[Path]:
        """Download all output images to *download_dir* concurrently; returns their local paths."""
        dst = Path(download_dir)
        dst.mkdir(parents=True, exist_ok=True)

        async def _fetch(img: OutputImage) -> Path:
            data = await self.get_image(filename=img.filename, subfolder=img.subfolder, image_type=img.type)
            path = dst / img.filename
            path.write_bytes(data)
            return path

        return await asyncio.gather(*(_fetch(img) for img in result.all_images()))

    async def download_first_image(self, result: ExecutionResult, download_dir: str | Path) -> Path | None:
        """Download the first output image and return its local path (``None`` when empty)."""
        paths = await self.download_images(result, download_dir)
        return paths[0] if paths else None
