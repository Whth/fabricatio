"""Tests for the fabricatio-comfyui subpackage."""

import asyncio
import threading
from dataclasses import replace
from pathlib import Path
from typing import cast
from unittest.mock import patch

import httpx
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
        """The cached factory hands out one shared instance per base URL."""
        assert get_comfyui_client(comfyui_config.base_url) is get_comfyui_client(comfyui_config.base_url)

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
        assert graph.preview.inputs.images.node_id == "refine_decode"
        assert graph.sampler_base.class_type == "KSamplerAdvanced"
        assert graph.sampler_refine.class_type == "KSamplerAdvanced"

    def test_node_ref_round_trip(self) -> None:
        """NodeRef parses the API list form and serializes back to it."""
        ref = NodeRef.model_validate(["sampler_base", 1])
        assert ref.node_id == "sampler_base"
        assert ref.output_index == 1
        assert ref.model_dump() == ["sampler_base", 1]

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
        _node_payload(raw, "loader").setdefault("inputs", {})["bogus_knob"] = 1
        with pytest.raises(ValidationError):
            Graph.model_validate(raw)

    def test_wrong_class_type_rejected(self) -> None:
        """A class_type outside the literal union fails loudly at load."""
        raw = Graph.default().to_api()
        _node_payload(raw, "loader")["class_type"] = "KSampler"
        with pytest.raises(ValidationError):
            Graph.model_validate(raw)

    def test_missing_node_rejected(self) -> None:
        """A missing node id fails loudly at load."""
        raw = Graph.default().to_api()
        del raw["sampler_refine"]
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
        assert "filename=test.png" in img.url_path()
        assert "subfolder=sub" in img.url_path()
        assert "type=output" in img.url_path()

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
        assert len(result.all_images()) == 3
        assert result.succeeded() is True

    def test_execution_result_succeeded_with_success_status(self) -> None:
        """ComfyUI returns status_str='success' (not 'completed') — succeeded must accept it."""
        result = ExecutionResult(
            prompt_id="abc",
            outputs={"9": [OutputImage(filename="img.png")]},
            status="success",
        )
        assert result.succeeded() is True

    def test_execution_result_failed(self) -> None:
        """Failed result exposes error message."""
        result = ExecutionResult(prompt_id="abc", status="error", error="CUDA out of memory")
        assert result.succeeded() is False
        assert result.error == "CUDA out of memory"

    def test_execution_result_empty(self) -> None:
        """Empty result yields no images and not succeeded."""
        result = ExecutionResult(prompt_id="abc")
        assert result.all_images() == []
        assert result.succeeded() is False

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
        assert [img.filename for img in result.all_images()] == ["img.png"]

    def test_execution_result_from_history_failed(self) -> None:
        """from_history carries the exception message on failure."""
        entry = HistoryEntry.from_raw(
            {"status": {"status_str": "error", "completed": True, "exception": "CUDA OOM"}, "outputs": {}},
        )
        result = ExecutionResult.from_history("pid-1", entry)
        assert result.succeeded() is False
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
    client = get_comfyui_client(comfyui_config.base_url)

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

        path = await UseComfyUI().generate_image(
            prompt="a mountain landscape",
            download_dir=tmp_path,
            seed=42,
            steps=20,
        )

        assert path is not None
        assert path == tmp_path / "ComfyUI_00001_.png"
        assert path.read_bytes() == b"fake-image-bytes"
        mock_img.assert_called_once()


@pytest.mark.asyncio
async def test_generate_image_config_download_dir(tmp_path: Path) -> None:
    """download_dir falls back to comfyui_config.download_dir when not passed."""
    client = get_comfyui_client(comfyui_config.base_url)
    mock_history: dict[str, object] = {
        "mock-uuid-123": {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {"9": {"images": [{"filename": "ComfyUI_00001_.png", "subfolder": "", "type": "output"}]}},
        },
    }

    with (
        patch(
            "fabricatio_comfyui.capabilities.comfyui.comfyui_config",
            replace(comfyui_config, download_dir=str(tmp_path)),
        ),
        patch.object(client, "_post", return_value={"prompt_id": "mock-uuid-123", "number": 1}),
        patch.object(client, "_get", return_value=mock_history),
        patch.object(client, "get_image", return_value=b"fake-image-bytes"),
    ):
        path = await UseComfyUI().generate_image(prompt="a mountain landscape", seed=42)

    assert path is not None
    assert path == tmp_path / "ComfyUI_00001_.png"
    assert path.read_bytes() == b"fake-image-bytes"


@pytest.mark.asyncio
async def test_generate_image_class_download_dir(tmp_path: Path) -> None:
    """A class-level download_dir on the capability beats the global config."""
    client = get_comfyui_client(comfyui_config.base_url)
    mock_history: dict[str, object] = {
        "mock-uuid-123": {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {"9": {"images": [{"filename": "ComfyUI_00001_.png", "subfolder": "", "type": "output"}]}},
        },
    }

    class ScopedRole(UseComfyUI):
        download_dir: str = str(tmp_path)

    with (
        patch(
            "fabricatio_comfyui.capabilities.comfyui.comfyui_config",
            replace(comfyui_config, download_dir=str(tmp_path / "global")),
        ),
        patch.object(client, "_post", return_value={"prompt_id": "mock-uuid-123", "number": 1}),
        patch.object(client, "_get", return_value=mock_history),
        patch.object(client, "get_image", return_value=b"fake-image-bytes"),
    ):
        path = await ScopedRole().generate_image(prompt="a mountain landscape", seed=42)

    assert path is not None
    assert path == tmp_path / "ComfyUI_00001_.png"
    assert not (tmp_path / "global").exists()


@pytest.mark.asyncio
async def test_generate_image_instance_download_dir(tmp_path: Path) -> None:
    """A per-instance scoped download_dir on the capability beats the global config."""
    client = get_comfyui_client(comfyui_config.base_url)
    mock_history: dict[str, object] = {
        "mock-uuid-123": {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {"9": {"images": [{"filename": "ComfyUI_00001_.png", "subfolder": "", "type": "output"}]}},
        },
    }
    role = UseComfyUI(download_dir=str(tmp_path))

    with (
        patch(
            "fabricatio_comfyui.capabilities.comfyui.comfyui_config",
            replace(comfyui_config, download_dir=str(tmp_path / "global")),
        ),
        patch.object(client, "_post", return_value={"prompt_id": "mock-uuid-123", "number": 1}),
        patch.object(client, "_get", return_value=mock_history),
        patch.object(client, "get_image", return_value=b"fake-image-bytes"),
    ):
        path = await role.generate_image(prompt="a mountain landscape", seed=42)

    assert path is not None
    assert path == tmp_path / "ComfyUI_00001_.png"
    assert not (tmp_path / "global").exists()


@pytest.mark.asyncio
async def test_generate_image_requires_download_dir() -> None:
    """Missing download dir (param and config) is a loud misuse error, not a silent None."""
    with (
        patch(
            "fabricatio_comfyui.capabilities.comfyui.comfyui_config",
            replace(comfyui_config, download_dir=None),
        ),
        pytest.raises(ValueError, match="download directory"),
    ):
        await UseComfyUI().generate_image(prompt="a cat")


@pytest.mark.asyncio
async def test_generate_image_list_prompts(tmp_path: Path) -> None:
    """A list of prompts yields one downloaded path per prompt, in order."""
    client = get_comfyui_client(comfyui_config.base_url)
    histories = [
        {
            "pid-1": {
                "status": {"status_str": "completed", "completed": True},
                "outputs": {"9": {"images": [{"filename": "ComfyUI_00001_.png", "subfolder": "", "type": "output"}]}},
            },
        },
        {
            "pid-2": {
                "status": {"status_str": "completed", "completed": True},
                "outputs": {"9": {"images": [{"filename": "ComfyUI_00002_.png", "subfolder": "", "type": "output"}]}},
            },
        },
    ]
    with (
        patch.object(
            client, "_post", side_effect=[{"prompt_id": "pid-1", "number": 1}, {"prompt_id": "pid-2", "number": 1}]
        ),
        patch.object(client, "_get", side_effect=histories),
        patch.object(client, "get_image", return_value=b"fake-image-bytes"),
    ):
        paths = await UseComfyUI().generate_image(["a mountain", "a river"], download_dir=tmp_path)
        assert await UseComfyUI().generate_image([], download_dir=tmp_path) == []

    assert paths == [tmp_path / "ComfyUI_00001_.png", tmp_path / "ComfyUI_00002_.png"]
    assert paths[0] is not None
    assert paths[1] is not None
    assert paths[0].read_bytes() == paths[1].read_bytes() == b"fake-image-bytes"


@pytest.mark.asyncio
async def test_generate_image_list_mixed_failure(tmp_path: Path) -> None:
    """A failed generation in a list yields None at its index, keeping correspondence."""
    client = get_comfyui_client(comfyui_config.base_url)
    histories = [
        {
            "pid-1": {
                "status": {"status_str": "completed", "completed": True},
                "outputs": {"9": {"images": [{"filename": "ok.png", "subfolder": "", "type": "output"}]}},
            },
        },
        {
            "pid-2": {
                "status": {"status_str": "error", "completed": True, "exception": "CUDA out of memory"},
                "outputs": {},
            },
        },
    ]
    with (
        patch.object(
            client, "_post", side_effect=[{"prompt_id": "pid-1", "number": 1}, {"prompt_id": "pid-2", "number": 1}]
        ),
        patch.object(client, "_get", side_effect=histories),
        patch.object(client, "get_image", return_value=b"fake-image-bytes"),
    ):
        paths = await UseComfyUI().generate_image(["a mountain", "a river"], download_dir=tmp_path)

    assert paths == [tmp_path / "ok.png", None]
    assert paths[0] is not None
    assert paths[0].read_bytes() == b"fake-image-bytes"


@pytest.mark.asyncio
async def test_generate_image_returns_none_on_failure(tmp_path: Path) -> None:
    """Failed generation yields None from the seal, without downloading anything."""
    client = get_comfyui_client(comfyui_config.base_url)
    failed_history: dict[str, object] = {
        "fail-uuid": {
            "status": {"status_str": "error", "completed": True, "exception": "CUDA out of memory"},
            "outputs": {},
        },
    }

    with (
        patch.object(client, "_post", return_value={"prompt_id": "fail-uuid", "number": 1}),
        patch.object(client, "_get", return_value=failed_history),
        patch.object(client, "get_image") as mock_img,
    ):
        path = await UseComfyUI().generate_image(prompt="a cat", download_dir=tmp_path)

    assert path is None
    mock_img.assert_not_called()


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
    assert cast("dict[str, object]", prompt["loader"])["inputs"]["ckpt_name"] == "custom.safetensors"
    assert cast("dict[str, object]", prompt["positive"])["inputs"]["text"] == "a cat"
    assert cast("dict[str, object]", prompt["negative"])["inputs"]["text"] == "ugly"
    assert cast("dict[str, object]", prompt["latent"])["inputs"]["width"] == 640
    assert cast("dict[str, object]", prompt["latent"])["inputs"]["height"] == 640
    assert cast("dict[str, object]", prompt["sampler_base"])["inputs"]["noise_seed"] == 42
    assert cast("dict[str, object]", prompt["sampler_base"])["inputs"]["steps"] == 20
    assert cast("dict[str, object]", prompt["sampler_base"])["inputs"]["cfg"] == 7.0
    assert captured["front"] is True
    assert captured["client_id"] == client.client_id()


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
        results = await client.generate("hi")
        assert len(results) == 1
        result = results[0]
        assert isinstance(result, ExecutionResult)
        assert result.prompt_id == "pid-1"
        assert result.succeeded() is True


@pytest.mark.asyncio
async def test_generate_batch_prompts() -> None:
    """Generate accepts a prompt list and returns one result per prompt, in order."""
    client = ComfyUIHttpClient.create(None)
    mock_history: dict[str, object] = {
        "pid-1": {
            "status": {"status_str": "completed", "completed": True},
            "outputs": {"9": {"images": [{"filename": "a.png", "subfolder": "", "type": "output"}]}},
        },
        "pid-2": {
            "status": {"status_str": "error", "completed": True, "exception": "boom"},
            "outputs": {},
        },
    }
    with (
        patch.object(
            client,
            "_post",
            side_effect=[{"prompt_id": "pid-1", "number": 1}, {"prompt_id": "pid-2", "number": 1}],
        ),
        patch.object(client, "_get", return_value=mock_history),
    ):
        results = await client.generate(["first", "second"])

    assert [r.prompt_id for r in results] == ["pid-1", "pid-2"]
    assert results[0].succeeded() is True
    assert results[1].succeeded() is False


@pytest.mark.asyncio
async def test_generate_timeout(tmp_path: Path) -> None:
    """Verify timeout raises when polling fails to complete."""
    client = get_comfyui_client(comfyui_config.base_url)
    with (
        patch.object(client, "_post", return_value={"prompt_id": "timeout-uuid"}),
        patch.object(client, "_get", return_value={}),
        pytest.raises(TimeoutError),
    ):
        await UseComfyUI().generate_image(prompt="anything", download_dir=tmp_path, timeout=0.2)


@pytest.mark.asyncio
async def test_generate_interrupts_on_cancellation() -> None:
    """Cancelling generate interrupts the server-side job before propagating."""
    client = ComfyUIHttpClient.create(None)
    calls: list[str] = []

    async def post_side_effect(path: str, **kwargs: object) -> dict[str, object]:
        calls.append(path)
        return {"prompt_id": "pid-1", "number": 1}

    with (
        patch.object(client, "_post", side_effect=post_side_effect),
        patch.object(client, "_get", side_effect=asyncio.CancelledError),
        pytest.raises(asyncio.CancelledError),
    ):
        await client.generate("a cat")

    assert calls == ["/prompt", "/interrupt"]


@pytest.mark.asyncio
async def test_generate_cancel_cleanup_failure_keeps_cancellation() -> None:
    """A failed interrupt must not mask the cancellation."""
    client = ComfyUIHttpClient.create(None)

    async def post_side_effect(path: str, **kwargs: object) -> dict[str, object]:
        if path == "/prompt":
            return {"prompt_id": "pid-1", "number": 1}
        raise httpx.ConnectError("server down")

    with (
        patch.object(client, "_post", side_effect=post_side_effect),
        patch.object(client, "_get", side_effect=asyncio.CancelledError),
        pytest.raises(asyncio.CancelledError),
    ):
        await client.generate("a cat")


@pytest.mark.asyncio
async def test_download_images_returns_paths(tmp_path: Path) -> None:
    """download_images returns the local path of every downloaded image."""
    client = ComfyUIHttpClient.create(None)
    result = ExecutionResult(
        prompt_id="pid",
        outputs={"9": [OutputImage(filename="a.png"), OutputImage(filename="b.png")]},
    )
    with patch.object(client, "get_image", return_value=b"png-bytes"):
        paths = await client.download_images(result, tmp_path)
    assert paths == [tmp_path / "a.png", tmp_path / "b.png"]
    assert all(p.read_bytes() == b"png-bytes" for p in paths)


@pytest.mark.asyncio
async def test_download_first_image(tmp_path: Path) -> None:
    """download_first_image downloads the first image and returns its local path."""
    client = ComfyUIHttpClient.create(None)
    result = ExecutionResult(prompt_id="pid", outputs={"9": [OutputImage(filename="out.png")]})
    with patch.object(client, "get_image", return_value=b"png-bytes"):
        path = await client.download_first_image(result, tmp_path)
    assert path is not None
    assert path == tmp_path / "out.png"
    assert path.read_bytes() == b"png-bytes"


@pytest.mark.asyncio
async def test_download_first_image_empty(tmp_path: Path) -> None:
    """download_first_image returns None when the result holds no images."""
    client = ComfyUIHttpClient.create(None)
    with patch.object(client, "get_image") as mock_img:
        path = await client.download_first_image(ExecutionResult(prompt_id="pid"), tmp_path)
    assert path is None
    mock_img.assert_not_called()


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
    assert c1.client_id() == c2.client_id()
    assert c1.client_id() == comfyui_config.base_url.rstrip("/").lower()


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
    results = await client.generate(
        prompt="a cute cat",
        checkpoint=_first_checkpoint(),
        timeout=180.0,
    )
    assert len(results) == 1
    assert results[0].succeeded() is True
    assert len(results[0].all_images()) >= 1


@pytest.mark.asyncio
@_requires_comfyui
@_requires_checkpoint
async def test_integration_generate_with_download(tmp_path: Path) -> None:
    """Integration: end-to-end generate with download against a real server."""
    path = await UseComfyUI().generate_image(
        prompt="a cute cat",
        checkpoint=_first_checkpoint(),
        download_dir=tmp_path,
        timeout=180.0,
    )

    assert path is not None
    assert path.stat().st_size > 0
