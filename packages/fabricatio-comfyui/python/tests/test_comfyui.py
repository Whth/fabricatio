"""Tests for the fabricatio-comfyui subpackage."""

import asyncio
import threading
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest
from fabricatio_comfyui.capabilities.comfyui import UseComfyUI
from fabricatio_comfyui.config import comfyui_config
from fabricatio_comfyui.http_client import ComfyUIHttpClient, get_comfyui_client
from fabricatio_comfyui.models.comfyui import (
    ExecutionResult,
    HistoryEntry,
    OutputImage,
    PromptResponse,
    QueueInfo,
    UploadResponse,
)
from fabricatio_comfyui.models.graph import Graph, NodeRef
from pydantic import ValidationError


def _node_payload(raw: dict[str, object], node_id: str) -> dict[str, object]:
    """Narrow the raw API-format graph to one node's mutable payload."""
    return cast("dict[str, object]", raw[node_id])


class TestFactories:
    """Cached-factory and bundled-template construction paths."""

    @pytest.mark.asyncio
    async def test_comfyui_client_is_shared(self) -> None:
        """The mixin holds no client; the cached factory hands out one shared instance."""
        role_a, role_b = UseComfyUI(), UseComfyUI()
        assert role_a.comfyui_client is role_b.comfyui_client

    @pytest.mark.asyncio
    async def test_client_factory_caches_per_url(self) -> None:
        """get_comfyui_client returns the same client per (loop, URL) pair, distinct per URL."""
        other = "http://127.0.0.1:9999"

        url = comfyui_config.base_url
        assert get_comfyui_client(url) is get_comfyui_client(url)
        assert get_comfyui_client(other) is not get_comfyui_client(url)

    @pytest.mark.asyncio
    async def test_client_factory_scoped_to_event_loop(self) -> None:
        """Identity holds within one loop; another loop gets a distinct pool instance."""
        url = comfyui_config.base_url
        first = get_comfyui_client(url)
        assert get_comfyui_client(url) is first  # cached within this loop

        # A different event loop must not inherit this loop's client: run the
        # factory on its own loop in a side thread.
        seen: list[object] = []

        def side_loop() -> None:
            async def grab() -> None:
                seen.append(get_comfyui_client(url))

            asyncio.run(grab())

        worker = threading.Thread(target=side_loop)
        worker.start()
        worker.join()
        assert seen[0] is not first

    def test_default_builds_full_graph(self) -> None:
        """default() builds all eleven nodes in Python, no JSON asset."""
        assert len(Graph.default().to_api()) == 11


# ======================================================================
# Graph tests — the Python-initialised typed graph and its wire format
# ======================================================================


class TestGraph:
    """Graph is initialised in Python and serializes to exact wire format."""

    def test_wire_round_trip(self) -> None:
        """to_api() emits the ComfyUI wire format and revalidates to an equal graph."""
        graph = Graph.default()
        assert Graph.model_validate(graph.to_api()) == graph

    def test_typed_node_access(self) -> None:
        """Nodes are reachable through typed fields, not lookups."""
        graph = Graph.default()
        assert graph.loader.class_type == "CheckpointLoaderSimple"
        assert graph.loader.inputs.ckpt_name == "catTowerNoobaiXL_v15Vpred.safetensors"
        assert graph.latent.inputs.width == 768
        assert graph.latent.inputs.height == 512
        assert graph.latent.inputs.batch_size == 1
        assert graph.positive.class_type == "CLIPTextEncode"
        assert graph.negative.class_type == "CLIPTextEncode"
        assert graph.preview.inputs.images.node_id == "15"
        assert graph.sampler_base.class_type == "KSamplerAdvanced"
        assert graph.sampler_refine.class_type == "KSamplerAdvanced"

    def test_node_ref_round_trip(self) -> None:
        """NodeRef parses the API list form and serializes back to it."""
        ref = NodeRef.model_validate(["4", 1])
        assert ref.node_id == "4"
        assert ref.output_index == 1
        assert ref.model_dump() == ["4", 1]

    def test_node_ref_rejects_short_list(self) -> None:
        """A node reference without an output index is invalid."""
        with pytest.raises(ValidationError):
            NodeRef.model_validate(["5"])

    def test_with_checkpoint(self) -> None:
        """with_checkpoint updates the loader's ckpt_name."""
        graph = Graph.default().with_checkpoint("model_v2.safetensors")
        assert graph.loader.inputs.ckpt_name == "model_v2.safetensors"

    def test_with_prompts(self) -> None:
        """with_positive_prompt / with_negative_prompt set the typed nodes."""
        graph = Graph.default().with_positive_prompt("a landscape").with_negative_prompt("blurry")
        assert graph.positive.inputs.text == "a landscape"
        assert graph.negative.inputs.text == "blurry"

    def test_with_resolution(self) -> None:
        """with_resolution updates the latent canvas dimensions."""
        graph = Graph.default().with_resolution(width=1024, height=768)
        assert graph.latent.inputs.width == 1024
        assert graph.latent.inputs.height == 768

    def test_with_resolution_partial(self) -> None:
        """with_resolution only updates the provided dimension."""
        graph = Graph.default().with_resolution(height=640)
        assert graph.latent.inputs.width == 768  # unchanged
        assert graph.latent.inputs.height == 640

    def test_with_sampler_updates_both_stages(self) -> None:
        """with_sampler aligns the base and refine samplers."""
        graph = Graph.default().with_sampler(seed=999, steps=30, cfg=7.5)
        for sampler in (graph.sampler_base, graph.sampler_refine):
            assert sampler.inputs.noise_seed == 999
            assert sampler.inputs.steps == 30
            assert sampler.inputs.cfg == 7.5

    def test_with_sampler_partial(self) -> None:
        """with_sampler only updates the provided parameters."""
        graph = Graph.default()
        original_steps = graph.sampler_base.inputs.steps
        graph.with_sampler(cfg=12.0)
        assert graph.sampler_base.inputs.cfg == 12.0
        assert graph.sampler_base.inputs.steps == original_steps

    def test_mutators_chain(self) -> None:
        """with_* builders return self, so calls chain."""
        graph = Graph.default()
        result = graph.with_checkpoint("x.safetensors").with_positive_prompt("chained")
        assert result is graph

    def test_mutators_validate_assignment(self) -> None:
        """The typed contract holds for the whole lifetime, not just at load."""
        graph = Graph.default()
        with pytest.raises(ValidationError):
            graph.with_resolution(width=cast("int", "abc"))
        with pytest.raises(ValidationError):
            graph.with_sampler(steps=cast("int", "twenty"))
        with pytest.raises(ValidationError):
            graph.with_checkpoint(cast("str", 123))
        with pytest.raises(ValidationError):
            graph.positive.inputs.text = cast("str", None)

    def test_mutators_accept_typed_knobs(self) -> None:
        """Legitimate typed values pass assignment validation."""
        graph = Graph.default()
        graph.with_checkpoint("x.safetensors").with_resolution(width=1024, height=768)
        graph.with_sampler(seed=42, steps=20, cfg=7.0)
        assert graph.loader.inputs.ckpt_name == "x.safetensors"
        assert graph.latent.inputs.width == 1024
        assert graph.sampler_base.inputs.noise_seed == 42

    def test_unknown_input_key_rejected(self) -> None:
        """A node input outside the known shape fails loudly at load."""
        raw = Graph.default().to_api()
        _node_payload(raw, "4").setdefault("inputs", {})["bogus_knob"] = 1
        with pytest.raises(ValidationError):
            Graph.model_validate(raw)

    def test_wrong_class_type_rejected(self) -> None:
        """A class_type outside the literal union fails loudly at load."""
        raw = Graph.default().to_api()
        _node_payload(raw, "4")["class_type"] = "KSampler"
        with pytest.raises(ValidationError):
            Graph.model_validate(raw)

    def test_missing_node_rejected(self) -> None:
        """A missing node id fails loudly at load."""
        raw = Graph.default().to_api()
        del raw["26"]
        with pytest.raises(ValidationError):
            Graph.model_validate(raw)

    def test_unknown_node_id_rejected(self) -> None:
        """An unexpected extra node id fails loudly at load."""
        raw = Graph.default().to_api()
        raw["999"] = {"class_type": "PreviewImage", "inputs": {"images": ["15", 0]}, "_meta": {"title": "x"}}
        with pytest.raises(ValidationError):
            Graph.model_validate(raw)


# ======================================================================
# Model tests
# ======================================================================


class TestModels:
    """Model unit tests."""

    def test_output_image_url_path(self) -> None:
        """Output image URL path encodes all fields."""
        img = OutputImage(filename="test.png", subfolder="sub", type="output")
        assert "filename=test.png" in img.url_path
        assert "subfolder=sub" in img.url_path
        assert "type=output" in img.url_path

    def test_execution_result_all_images(self) -> None:
        """Flatten images from multiple output nodes."""
        result = ExecutionResult(
            prompt_id="abc",
            outputs={
                "9": [OutputImage(filename="img1.png"), OutputImage(filename="img2.png")],
                "12": [OutputImage(filename="img3.png")],
            },
            status="completed",
        )
        assert len(result.all_images) == 3
        assert result.succeeded is True

    def test_execution_result_succeeded_with_success_status(self) -> None:
        """ComfyUI returns status_str='success' (not 'completed') — succeeded must accept it."""
        result = ExecutionResult(
            prompt_id="abc",
            outputs={"9": [OutputImage(filename="img.png")]},
            status="success",
        )
        assert result.succeeded is True

    def test_execution_result_failed(self) -> None:
        """Failed result exposes error message."""
        result = ExecutionResult(prompt_id="abc", status="error", error="CUDA out of memory")
        assert result.succeeded is False
        assert result.error == "CUDA out of memory"

    def test_execution_result_empty(self) -> None:
        """Empty result yields no images and not succeeded."""
        result = ExecutionResult(prompt_id="abc")
        assert result.all_images == []
        assert result.succeeded is False

    def test_execution_result_from_history(self) -> None:
        """from_history builds a result from a history entry."""
        entry = HistoryEntry.from_raw(
            {
                "status": {"status_str": "completed", "completed": True},
                "outputs": {"9": {"images": [{"filename": "img.png", "subfolder": "", "type": "output"}]}},
            },
        )
        result = ExecutionResult.from_history("pid-1", entry)
        assert result.prompt_id == "pid-1"
        assert result.status == "completed"
        assert result.error is None
        assert [img.filename for img in result.all_images] == ["img.png"]

    def test_execution_result_from_history_failed(self) -> None:
        """from_history carries the exception message on failure."""
        entry = HistoryEntry.from_raw(
            {"status": {"status_str": "error", "completed": True, "exception": "CUDA OOM"}, "outputs": {}},
        )
        result = ExecutionResult.from_history("pid-1", entry)
        assert result.succeeded is False
        assert result.error == "CUDA OOM"

    def test_history_entry_from_raw(self) -> None:
        """Parse history entry from raw API response."""
        raw = {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {"9": {"images": [{"filename": "img.png", "subfolder": "", "type": "output"}]}},
        }
        entry = HistoryEntry.from_raw(raw)
        assert entry.status.status_str == "completed"
        assert entry.status.completed is True
        assert "9" in entry.outputs
        assert entry.outputs["9"].images[0].filename == "img.png"

    def test_history_entry_from_raw_empty(self) -> None:
        """Empty raw dict defaults to unknown status with no outputs."""
        entry = HistoryEntry.from_raw({})
        assert entry.status.status_str == "unknown"
        assert entry.status.completed is False
        assert entry.outputs == {}

    def test_history_entry_from_raw_failed(self) -> None:
        """Failed history entry carries exception string."""
        raw = {"status": {"status_str": "error", "completed": True, "exception": "CUDA OOM"}, "outputs": {}}
        entry = HistoryEntry.from_raw(raw)
        assert entry.status.status_str == "error"
        assert entry.status.exception == "CUDA OOM"

    def test_history_entry_filters_empty_outputs(self) -> None:
        """History entries without filenames are stripped from outputs."""
        raw = {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {
                "9": {"images": [{"filename": "img.png"}]},
                "12": {"images": [{"filename": ""}]},
            },
        }
        entry = HistoryEntry.from_raw(raw)
        assert list(entry.outputs.keys()) == ["9"]

    def test_queue_info_from_raw(self) -> None:
        """Parse queue info with running and pending entries."""
        raw = {
            "queue_running": [[1, "pid-1", {}, {}, []]],
            "queue_pending": [[2, "pid-2", {}, {}, ["node1"]]],
        }
        info = QueueInfo.from_raw(raw)
        assert len(info.queue_running) == 1
        assert info.queue_running[0].prompt_id == "pid-1"
        assert len(info.queue_pending) == 1
        assert info.queue_pending[0].outputs_to_execute == ["node1"]

    def test_queue_info_from_raw_empty(self) -> None:
        """Empty raw dict yields empty queue lists."""
        info = QueueInfo.from_raw({})
        assert info.queue_running == []
        assert info.queue_pending == []

    def test_upload_response_from_raw(self) -> None:
        """Parse upload response fields from raw dict."""
        resp = UploadResponse.from_raw({"name": "test.png", "subfolder": "input", "type": "input"})
        assert resp.name == "test.png"
        assert resp.subfolder == "input"

    def test_prompt_response_fields(self) -> None:
        """PromptResponse carries id, number, and default empty errors."""
        resp = PromptResponse(prompt_id="uuid-123", number=5)
        assert resp.prompt_id == "uuid-123"
        assert resp.number == 5
        assert resp.node_errors == {}


# ======================================================================
# Client tests
# ======================================================================


@pytest.mark.asyncio
async def test_generate_flow(tmp_path: Path) -> None:
    """End-to-end flow via the high-level capability: generate -> poll -> download."""
    client = UseComfyUI().comfyui_client

    mock_history: dict[str, object] = {
        "mock-uuid-123": {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {"9": {"images": [{"filename": "ComfyUI_00001_.png", "subfolder": "", "type": "output"}]}},
        },
    }

    with (
        patch.object(client, "_post") as mock_post,
        patch.object(client, "_get") as mock_get,
        patch.object(client, "get_image") as mock_img,
    ):
        mock_post.return_value = {"prompt_id": "mock-uuid-123", "number": 1}

        async def get_side_effect(path: str, **kwargs: object) -> object:
            if path.startswith("/history/"):
                return mock_history
            return {}

        mock_get.side_effect = get_side_effect
        mock_img.return_value = b"fake-image-bytes"

        role = UseComfyUI()
        result = await role.generate_image(
            prompt="a mountain landscape",
            download_dir=tmp_path,
            seed=42,
            steps=20,
        )

        assert result.prompt_id == "mock-uuid-123"
        assert result.succeeded is True
        assert len(result.all_images) == 1
        assert result.all_images[0].filename == "ComfyUI_00001_.png"
        mock_img.assert_called_once()


@pytest.mark.asyncio
async def test_generate_applies_knobs_to_bundled_graph() -> None:
    """Generate builds the internal graph and applies every knob."""
    client = ComfyUIHttpClient.create(None)

    captured: dict[str, object] = {}

    async def post_side_effect(path: str, **kwargs: object) -> dict[str, object]:
        captured["path"] = path
        captured.update(cast("dict[str, object]", kwargs.get("json_data") or {}))
        return {"prompt_id": "pid-1", "number": 1}

    completed: dict[str, object] = {
        "pid-1": {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {},
        },
    }

    with (
        patch.object(client, "_post", side_effect=post_side_effect),
        patch.object(client, "_get", return_value=completed),
    ):
        await client.generate(
            prompt="a cat",
            negative_prompt="ugly",
            width=640,
            height=640,
            seed=42,
            steps=20,
            cfg=7.0,
            checkpoint="custom.safetensors",
            front=True,
        )

    assert captured["path"] == "/prompt"
    prompt = cast("dict[str, object]", captured["prompt"])
    assert cast("dict[str, object]", prompt["4"])["inputs"]["ckpt_name"] == "custom.safetensors"
    assert cast("dict[str, object]", prompt["7"])["inputs"]["text"] == "a cat"
    assert cast("dict[str, object]", prompt["8"])["inputs"]["text"] == "ugly"
    assert cast("dict[str, object]", prompt["6"])["inputs"]["width"] == 640
    assert cast("dict[str, object]", prompt["6"])["inputs"]["height"] == 640
    assert cast("dict[str, object]", prompt["25"])["inputs"]["noise_seed"] == 42
    assert cast("dict[str, object]", prompt["25"])["inputs"]["steps"] == 20
    assert cast("dict[str, object]", prompt["25"])["inputs"]["cfg"] == 7.0
    assert captured["front"] is True
    assert captured["client_id"] == client.client_id


@pytest.mark.asyncio
async def test_generate_returns_typed_result() -> None:
    """Generate returns an ExecutionResult, not a raw dict."""
    client = ComfyUIHttpClient.create(None)
    mock_history: dict[str, object] = {
        "pid-1": {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {"9": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}},
        },
    }
    with (
        patch.object(client, "_post", return_value={"prompt_id": "pid-1", "number": 1}),
        patch.object(client, "_get", return_value=mock_history),
    ):
        result = await client.generate("hi")
        assert isinstance(result, ExecutionResult)
        assert result.prompt_id == "pid-1"
        assert result.succeeded is True


@pytest.mark.asyncio
async def test_generate_timeout() -> None:
    """Verify timeout raises when polling fails to complete."""
    role = UseComfyUI()
    client = role.comfyui_client
    with (
        patch.object(client, "_post", return_value={"prompt_id": "timeout-uuid"}),
        patch.object(client, "_get", return_value={}),
        pytest.raises(TimeoutError),
    ):
        await role.generate_image(prompt="anything", timeout=0.2)


@pytest.mark.asyncio
async def test_upload_image(tmp_path: Path) -> None:
    """Upload a local image file and verify the typed response."""
    client = ComfyUIHttpClient.create(None)

    with patch.object(client, "_upload") as mock_upload:
        mock_upload.return_value = {"name": "test.png", "subfolder": "input"}

        fake_img = tmp_path / "test.png"
        fake_img.write_bytes(b"fake-png-content")

        result = await client.upload_image(fake_img)
        assert result.name == "test.png"
        assert isinstance(result, UploadResponse)
        mock_upload.assert_called_once()


@pytest.mark.asyncio
async def test_get_history_returns_typed() -> None:
    """get_history returns a HistoryEntry for a known prompt id."""
    client = ComfyUIHttpClient.create(None)

    raw = {
        "pid-1": {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {"9": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}},
        },
    }
    with patch.object(client, "_get", return_value=raw):
        entry = await client.get_history("pid-1")
        assert isinstance(entry, HistoryEntry)
        assert entry.status.status_str == "completed"


@pytest.mark.asyncio
async def test_get_history_missing() -> None:
    """get_history returns None for a nonexistent prompt id."""
    client = ComfyUIHttpClient.create(None)

    with patch.object(client, "_get", return_value={}):
        entry = await client.get_history("nonexistent")
        assert entry is None


@pytest.mark.asyncio
async def test_queue_info_typed() -> None:
    """get_queue_info returns a typed QueueInfo object."""
    client = ComfyUIHttpClient.create(None)

    raw = {"queue_running": [], "queue_pending": [[1, "pid", {}, {}, []]]}
    with patch.object(client, "_get", return_value=raw):
        info = await client.get_queue_info()
        assert isinstance(info, QueueInfo)
        assert len(info.queue_pending) == 1


@pytest.mark.asyncio
async def test_client_id_uses_base_url() -> None:
    """client_id is derived from the configured base_url."""
    c1 = ComfyUIHttpClient.create(None)
    c2 = ComfyUIHttpClient.create(None)
    assert c1.client_id == c2.client_id
    assert c1.client_id == comfyui_config.base_url.rstrip("/").lower()


@pytest.mark.asyncio
async def test_wait_for_completion_polling() -> None:
    """wait_for_completion uses HTTP polling."""
    client = ComfyUIHttpClient.create(None)

    raw = {
        "pid-1": {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {},
        },
    }
    with patch.object(client, "_get", return_value=raw):
        result = await client.wait_for_completion("pid-1", poll_interval=0.01, timeout=5.0)
        assert result.prompt_id == "pid-1"
        assert result.status == "completed"


# ======================================================================
# Integration tests (require live ComfyUI server at 127.0.0.1:8188)
# ======================================================================


def _comfyui_available() -> bool:
    """Check if ComfyUI server is reachable."""
    import httpx

    try:
        r = httpx.get("http://127.0.0.1:8188/system_stats", timeout=3.0)
        return r.status_code == 200
    except httpx.RequestError:
        return False


def _first_checkpoint() -> str | None:
    """Return the first available checkpoint filename on the live server, or None."""
    import httpx

    try:
        r = httpx.get("http://127.0.0.1:8188/models/checkpoints", timeout=3.0)
        if r.status_code != 200:
            return None
        models = r.json()
        return models[0] if models else None
    except httpx.RequestError:
        return None


_requires_comfyui = pytest.mark.skipif(not _comfyui_available(), reason="ComfyUI server not running")
_requires_checkpoint = pytest.mark.skipif(
    _first_checkpoint() is None,
    reason="No checkpoints installed on ComfyUI server",
)


@pytest.mark.asyncio
@_requires_comfyui
@_requires_checkpoint
async def test_integration_generate(tmp_path: Path) -> None:
    """Integration: generate via the bundled workflow against a real server."""
    client = get_comfyui_client(comfyui_config.base_url)
    result = await client.generate(
        prompt="a cute cat",
        checkpoint=_first_checkpoint(),
        timeout=180.0,
    )
    assert result.succeeded is True
    assert len(result.all_images) >= 1


@pytest.mark.asyncio
@_requires_comfyui
@_requires_checkpoint
async def test_integration_generate_with_download(tmp_path: Path) -> None:
    """Integration: end-to-end generate with download against a real server."""
    role = UseComfyUI()
    result = await role.generate_image(
        prompt="a cute cat",
        checkpoint=_first_checkpoint(),
        download_dir=tmp_path,
        timeout=180.0,
    )

    assert result.succeeded is True

    # Verify image was downloaded to disk
    downloaded = list(tmp_path.glob("*.png"))
    assert len(downloaded) >= 1
    assert downloaded[0].stat().st_size > 0
