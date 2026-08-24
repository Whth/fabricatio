"""Tests for the RatingImage capability."""

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from fabricatio_capabilities.capabilities.rating_image import RatingImage
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_json_router_usage
from fabricatio_mock.utils import install_router_usage

if TYPE_CHECKING:
    import pytest_mock

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 32  # minimal PNG-signature payload


class RatingImageTestRole(LLMTestRole, RatingImage):
    """Test role mixing the dummy LLM into the RatingImage capability."""


@pytest.fixture
def role() -> RatingImageTestRole:
    """Instantiate the test role for each test."""
    return RatingImageTestRole(name="rate-image")


@pytest.fixture(name="image_path")
def image_path_fixture(tmp_path: Path) -> Path:
    """Write a tiny fake PNG and return its path."""
    p = tmp_path / "subject.png"
    p.write_bytes(PNG_BYTES)
    return p


@pytest.fixture(name="responses")
def responses_fixture() -> list[str]:
    """Valid rating JSON wrapped for the dummy router."""
    return return_json_router_usage('{"clarity": 0.80, "depth": 0.60}')


@pytest.mark.asyncio
async def test_rate_image_returns_ratings(responses: list[str], role: RatingImageTestRole, image_path: Path) -> None:
    """A valid model response yields the per-criterion score dict."""
    with install_router_usage(*responses):
        ratings = await role.rate_image(
            image_path,
            "art quality",
            {"clarity", "depth"},
            manual={"clarity": "sharpness", "depth": "composition depth"},
        )
    assert ratings == {"clarity": 0.80, "depth": 0.60}


@pytest.mark.asyncio
async def test_rate_image_attaches_bytes(
    responses: list[str],
    role: RatingImageTestRole,
    image_path: Path,
    mocker: "pytest_mock.MockerFixture",
) -> None:
    """The image file's bytes ride the request as the images kwarg."""
    spy = mocker.patch.object(RatingImage, "propose", autospec=True)
    spy.return_value = SimpleNamespace(model_dump=lambda: {"clarity": 1.0})

    with install_router_usage(*responses):
        await role.rate_image(image_path, "t", {"clarity"}, manual={"clarity": "c"})

    kwargs = spy.call_args.kwargs
    assert kwargs["images"] == [PNG_BYTES]


@pytest.mark.asyncio
async def test_rate_image_invalid_response_returns_none(role: RatingImageTestRole, image_path: Path) -> None:
    """Exhausted validation attempts surface as None instead of raising."""
    bad = install_router_usage(*return_json_router_usage('{"clarity": "not-a-number"}'))
    with bad:
        ratings = await role.rate_image(
            image_path,
            "t",
            {"clarity"},
            manual={"clarity": "c"},
            max_validations=1,
        )
    assert ratings is None


@pytest.mark.asyncio
async def test_rate_image_batch(
    responses: list[str], role: RatingImageTestRole, image_path: Path, tmp_path: Path
) -> None:
    """A list of paths rates each image independently, preserving order."""
    second = tmp_path / "second.png"
    second.write_bytes(PNG_BYTES)

    with install_router_usage(*responses):
        ratings = await role.rate_image(
            [image_path, second],
            "art quality",
            {"clarity", "depth"},
            manual={"clarity": "sharpness", "depth": "composition depth"},
        )
    assert ratings == [{"clarity": 0.80, "depth": 0.60}, {"clarity": 0.80, "depth": 0.60}]
