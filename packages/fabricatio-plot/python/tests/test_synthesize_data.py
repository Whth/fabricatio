"""Tests for the synthesize_data module."""

from typing import List, Optional

import pytest
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_code_string, return_json_obj_string, return_string
from fabricatio_mock.utils import install_router
from fabricatio_plot.capabilities.synthesize_data import SynthesizeData
from fabricatio_plot.config import plot_config
from litellm import Router


class SynthesizeDataRole(LLMTestRole, SynthesizeData):
    """Test role that combines LLMTestRole with SynthesizeData for testing."""


@pytest.fixture
def mock_csv_router(ret_values: List[str]) -> Router:
    """Returns a Router instance with a mocked return_code_string function."""
    return return_code_string(*ret_values, lang=plot_config.csv_codeblock_lang)


@pytest.fixture
def mock_router(ret_values: List[str]) -> Router:
    """Returns a Router instance with a mocked return_json_obj_string function."""
    return return_json_obj_string(*ret_values)


@pytest.fixture
def role() -> SynthesizeDataRole:
    """Create a SynthesizeDataRole instance for testing.

    Returns:
        SynthesizeDataRole: Test role instance
    """
    return SynthesizeDataRole()


@pytest.mark.parametrize(
    ("requirement", "ret_values"),
    [
        ("user data", [["name", "email", "age"]]),
        ("sales data", [["product", "price", "quantity", "date"]]),
        ("weather data", [["temperature", "humidity", "pressure"]]),
    ],
)
@pytest.mark.asyncio
async def test_generate_header_single_requirement(
    role: SynthesizeDataRole, requirement: str, ret_values: List[List[str]]
) -> None:
    """Test generate_header with single requirement string.

    Args:
        role: SynthesizeDataRole fixture
        requirement: Single requirement string
        ret_values: Expected return values from mock
    """
    mock_router_instance = return_json_obj_string(*ret_values)
    with install_router(mock_router_instance):
        result = await role.generate_header(requirement)
        assert result == ret_values[0]


@pytest.mark.parametrize(
    ("requirements", "ret_values"),
    [
        (["user data", "sales data"], [["name", "email", "age"], ["product", "price", "quantity"]]),
        (["weather data"], [["temperature", "humidity", "pressure"]]),
    ],
)
@pytest.mark.asyncio
async def test_generate_header_multiple_requirements(
    role: SynthesizeDataRole, requirements: List[str], ret_values: List[List[str]]
) -> None:
    """Test generate_header with multiple requirement strings.

    Args:
        role: SynthesizeDataRole fixture
        requirements: List of requirement strings to test
        ret_values: Expected header values for the given requirements
    """
    mock_router_instance = return_json_obj_string(*ret_values)
    with install_router(mock_router_instance):
        result = await role.generate_header(requirements)
        assert result == ret_values


@pytest.mark.parametrize(
    ("requirements", "ret_values"),
    [
        ("user data", [["product", "price", "quantity"]]),
        (["user data"], [["product", "price", "quantity"]]),
    ],
)
@pytest.mark.asyncio
async def test_generate_header_returns_none(
    role: SynthesizeDataRole, requirements: str | List[str], ret_values: List[List[str]]
) -> None:
    """Test generate_header when LLM returns None.

    Args:
        role: SynthesizeDataRole fixture
        requirements: List of requirement strings to test
        ret_values: Expected header values for the given requirements
    """
    with install_router(return_string("invalid response")):
        result = await role.generate_header(requirements)
        if isinstance(requirements, str):
            assert result is None
        else:
            assert all(r is None for r in result)


@pytest.mark.parametrize(
    ("requirements", "header", "ret_values"),
    [
        ("user data", ["name", "age", "email"], ["name,age,email\nJohn,25,john@example.com\nJane,30,jane@example.com"]),
        ("user data", ["name", "age"], ["name,age\nJohn,25\nJane,30"]),
    ],
)
@pytest.mark.asyncio
async def test_generate_csv_data_with_header(
    role: SynthesizeDataRole, requirements: str, header: List[str], ret_values: List[str]
) -> None:
    """Test generate_csv_data with provided header.

    Args:
        role: SynthesizeDataRole fixture
        requirements: Data requirements
        header: Expected header columns
        ret_values: Mock CSV data return values
    """
    mock_csv_router_instance = return_code_string(*ret_values, lang=plot_config.csv_codeblock_lang)
    with install_router(mock_csv_router_instance):
        result = await role.generate_csv_data(requirements, header, rows=2)
        assert result is not None
        assert result.shape[0] == 2
        assert list(result.columns) == header


@pytest.mark.parametrize(
    ("expected_header", "ret_values"),
    [
        (["name", "age", "email"], ["username,years,contact\nJohn,25,john@example.com"]),
    ],
)
@pytest.mark.asyncio
async def test_generate_csv_data_header_mismatch(
    role: SynthesizeDataRole,
    expected_header: List[str],
    ret_values: List[str],
) -> None:
    """Test generate_csv_data when CSV header doesn't match expected header.

    Args:
        role: SynthesizeDataRole fixture
        expected_header: Expected header for the CSV
        ret_values: Mock CSV data return values
    """
    mock_csv_router_instance = return_code_string(*ret_values, lang=plot_config.csv_codeblock_lang)
    with install_router(mock_csv_router_instance):
        result = await role.generate_csv_data("user data", expected_header, rows=1)
        assert result is None


@pytest.mark.parametrize(
    ("requirements", "header", "ret_values"),
    [
        (
            "user data",
            ["name", "age", "email"],
            ["namea,age,email\nJohn,25,john@example.com\nJane,30,jane@example.com"],
        ),
        (
            "user data",
            ["name", "age"],
            ["namesc,age\nJohn,25\nJane,30"],
        ),
    ],
)
@pytest.mark.asyncio
async def test_generate_csv_data_parse_error(
    role: SynthesizeDataRole,
    requirements: str,
    header: List[str],
    ret_values: List[str],
) -> None:
    """Test generate_csv_data with malformed CSV content.

    Args:
        role: SynthesizeDataRole fixture
        requirements: Description of the data to be synthesized
        header: Expected header for the CSV
        ret_values: Malformed CSV content to trigger parsing error
    """
    mock_csv_router_instance = return_code_string(*ret_values, lang=plot_config.csv_codeblock_lang)
    with install_router(mock_csv_router_instance):
        result = await role.generate_csv_data(requirements, header, rows=2)
        assert result is None


@pytest.mark.parametrize(
    ("requirement", "header", "rows", "batch_size", "expected_shape", "ret_values"),
    [
        (
            "user data",
            ["name", "age"],
            4,
            2,
            (4, 2),
            ["name,age\nJohn,25\nJane,30", "name,age\nBob,40\nAlice,28"],
        ),
    ],
)
@pytest.mark.asyncio
async def test_synthesize_data_success(
    role: SynthesizeDataRole,
    requirement: str,
    header: List[str],
    rows: int,
    batch_size: int,
    expected_shape: tuple,
    ret_values: List[str],
) -> None:
    """Test successful synthesize_data operation.

    Args:
        role: SynthesizeDataRole fixture
        requirement: Description of the data requirements
        header: List of column names
        rows: Number of rows to generate
        batch_size: Size of each batch
        expected_shape: Expected shape of the resulting DataFrame
        ret_values: Mocked CSV data response from LLM
    """
    mock_csv_router_instance = return_code_string(*ret_values, lang=plot_config.csv_codeblock_lang)
    with install_router(mock_csv_router_instance):
        result = await role.synthesize_data(requirement, header=header, rows=rows, batch_size=batch_size)
        assert result is not None
        assert result.shape == expected_shape
        assert list(result.columns) == ["name", "age"]


@pytest.mark.parametrize(
    ("requirement", "rows", "batch_size", "expected_shape", "header", "ret_values"),
    [
        (
            "sales data",
            2,
            2,
            (2, 2),
            ["product", "price"],
            ["product,price\nWidget,9.99\nGadget,19.99"],
        ),
    ],
)
@pytest.mark.asyncio
async def test_synthesize_data_with_explicit_header(
    role: SynthesizeDataRole,
    requirement: str,
    rows: int,
    batch_size: int,
    expected_shape: tuple,
    header: List[str],
    ret_values: List[str],
) -> None:
    """Test synthesize_data with explicitly provided header.

    Args:
        role: SynthesizeDataRole fixture
        requirement: Description of the data requirements
        rows: Number of rows to generate
        batch_size: Size of each batch
        expected_shape: Expected shape of the resulting DataFrame
        header: Explicit column headers to use
        ret_values: Mocked CSV data response from LLM
    """
    mock_csv_router_instance = return_code_string(*ret_values, lang=plot_config.csv_codeblock_lang)
    with install_router(mock_csv_router_instance):
        result = await role.synthesize_data(requirement, rows=rows, batch_size=batch_size, header=header)
        assert result is not None
        assert result.shape == expected_shape
        assert list(result.columns) == header


@pytest.mark.parametrize(
    ("requirement", "batch_size", "ret_values", "expected_rows", "header"),
    [
        (
            "user data",
            2,
            ["name,age\nJohn,25\nJane,30", "name,age\nBob,40\nAlice,35"],
            4,
            ["name", "age"],
        ),
    ],
)
@pytest.mark.asyncio
async def test_synthesize_data_partial_batch_failure(
    role: SynthesizeDataRole,
    requirement: str,
    batch_size: int,
    ret_values: List[str],
    expected_rows: int,
    header: List[str],
) -> None:
    """Test synthesize_data when some batches fail.

    Args:
        role: SynthesizeDataRole fixture
        requirement: Description of the data requirements
        batch_size: Size of each batch
        ret_values: Responses including malformed CSV
        expected_rows: Number of rows expected to succeed
        header: Explicit column headers to use
    """
    mock_csv_router_instance = return_code_string(*ret_values, lang=plot_config.csv_codeblock_lang)
    with install_router(mock_csv_router_instance):
        result = await role.synthesize_data(requirement, rows=expected_rows, batch_size=batch_size, header=header)
        assert result is not None
        assert result.shape[0] == expected_rows


@pytest.mark.parametrize(
    ("requirement", "rows", "batch_size", "ret_values", "header"),
    [
        (
            "user data",
            4,
            2,
            ["", "ascasc"],
            ["name", "age"],
        ),
    ],
)
@pytest.mark.asyncio
async def test_synthesize_data_all_batches_fail(
    role: SynthesizeDataRole,
    requirement: str,
    rows: int,
    batch_size: int,
    ret_values: List[str],
    header: List[str],
) -> None:
    """Test synthesize_data when all batches fail.

    Args:
        role: SynthesizeDataRole fixture
        requirement: Description of the data requirements
        rows: Total number of rows to generate
        batch_size: Size of each batch
        ret_values: Response simulating malformed CSV that will fail parsing
        header: Explicit column headers to use
    """
    mock_csv_router_instance = return_code_string(*ret_values, lang=plot_config.csv_codeblock_lang)
    with install_router(mock_csv_router_instance):
        result = await role.synthesize_data(requirement, rows=rows, batch_size=batch_size, header=header)
        assert result is None


@pytest.mark.parametrize(
    ("requirement", "row_count", "expected_result", "ret_values", "header"),
    [
        ("user data", 0, None, ["name,age\nJohn,25"], ["name", "age"]),
        ("user data", -1, None, ["name,age\nJohn,25"], ["name", "age"]),
    ],
)
@pytest.mark.asyncio
async def test_synthesize_data_invalid_row_count(
    role: SynthesizeDataRole,
    requirement: str,
    row_count: int,
    expected_result: Optional[int],
    ret_values: List[str],
    header: List[str],
) -> None:
    """Test synthesize_data with invalid row counts.

    Args:
        role: SynthesizeDataRole fixture
        requirement: Description of the data requirements
        row_count: Invalid number of rows to request
        expected_result: Expected result (None for invalid requests)
        ret_values: Mock CSV data return values
        header: Explicit column headers to use
    """
    mock_csv_router_instance = return_code_string(*ret_values, lang=plot_config.csv_codeblock_lang)
    with install_router(mock_csv_router_instance):
        assert await role.synthesize_data(requirement, rows=row_count, header=header) is expected_result
