"""Test suite for DataIoToolBox in fabricatio_plot package.

This test suite covers functionality related to file-based data input/output operations:
- Loading data from CSV files
- Loading data from Excel files (with optional dependency)
- Saving data to various formats
- Error handling for unsupported formats and missing files

Each test ensures correct behavior of the corresponding I/O function,
including proper error handling for invalid inputs and edge cases.
"""

from pathlib import Path

import pandas as pd
import pytest
from fabricatio_core.rust import is_installed
from fabricatio_plot.toolboxes import dataframe_io as dt


# =====================
# Test Data Setup
# =====================
@pytest.fixture
def sample_dataframe() -> pd.DataFrame:
    """Create a sample DataFrame for I/O testing."""
    return pd.DataFrame(
        {
            "id": [1, 2, 3],
            "name": ["Alice", "Bob", "Charlie"],
            "score": [95.5, 87.0, 92.3],
            "active": [True, False, True],
        }
    )


@pytest.fixture
def temp_csv(tmp_path: Path) -> Path:
    """Create a temporary CSV file for testing."""
    file_path = tmp_path / "test.csv"
    df = pd.DataFrame({"col1": [1, 2], "col2": ["a", "b"]})
    df.to_csv(file_path, index=False)
    return file_path


@pytest.fixture
def temp_excel(tmp_path: Path) -> Path:
    """Create a temporary Excel file for testing."""
    pytest.skip("openpyxl library is not installed") if not is_installed("openpyxl") else None

    file_path = tmp_path / "test.xlsx"
    df = pd.DataFrame({"col1": [1, 2], "col2": ["a", "b"]})
    df.to_excel(file_path, index=False, sheet_name="Sheet1")
    return file_path


@pytest.fixture
def temp_parquet(tmp_path: Path) -> Path:
    """Create a temporary Parquet file for testing."""
    pytest.skip("pyarrow library is not installed") if not is_installed("pyarrow") else None

    file_path = tmp_path / "test.parquet"
    df = pd.DataFrame({"col1": [1, 2], "col2": ["a", "b"]})
    df.to_parquet(file_path, index=False)
    return file_path


# =====================
# Data Loading Tests
# =====================
def test_load_csv(temp_csv: Path) -> None:
    """Test loading data from CSV file."""
    df: pd.DataFrame = dt.load_csv(str(temp_csv))
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["col1", "col2"]
    assert df.shape == (2, 2)
    assert df["col1"].tolist() == [1, 2]
    assert df["col2"].tolist() == ["a", "b"]


def test_load_csv_path_object(temp_csv: Path) -> None:
    """Test loading CSV using Path object."""
    df: pd.DataFrame = dt.load_csv(temp_csv)
    assert df.shape == (2, 2)


def test_load_csv_file_not_found() -> None:
    """Test error handling for non-existent CSV file."""
    with pytest.raises(FileNotFoundError):
        dt.load_csv("nonexistent_file.csv")


def test_load_excel(temp_excel: Path) -> None:
    """Test loading data from Excel file."""
    pytest.skip("openpyxl library is not installed") if not is_installed("openpyxl") else None

    df: pd.DataFrame = dt.load_excel(str(temp_excel))
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["col1", "col2"]
    assert df.shape == (2, 2)
    assert df["col1"].tolist() == [1, 2]


def test_load_excel_sheet_name(temp_excel: Path) -> None:
    """Test loading specific Excel sheet."""
    df: pd.DataFrame = dt.load_excel(str(temp_excel), sheet_name="Sheet1")
    assert df.shape == (2, 2)


def test_load_excel_file_not_found() -> None:
    """Test error handling for non-existent Excel file."""
    pytest.skip("openpyxl library is not installed") if not is_installed("openpyxl") else None

    with pytest.raises(FileNotFoundError):
        dt.load_excel("nonexistent_file.xlsx")


# =====================
# Data Saving Tests
# =====================
def test_save_data_csv(tmp_path: Path, sample_dataframe: pd.DataFrame) -> None:
    """Test saving DataFrame to CSV format."""
    file_path: Path = tmp_path / "output.csv"
    dt.save_data(sample_dataframe, file_path, fmt="csv")
    assert file_path.exists()

    # Verify content
    loaded_df: pd.DataFrame = pd.read_csv(file_path)
    pd.testing.assert_frame_equal(loaded_df, sample_dataframe)


def test_save_data_excel(tmp_path: Path, sample_dataframe: pd.DataFrame) -> None:
    """Test saving DataFrame to Excel format."""
    pytest.skip("openpyxl library is not installed") if not is_installed("openpyxl") else None

    file_path: Path = tmp_path / "output.xlsx"
    dt.save_data(sample_dataframe, file_path, fmt="excel")
    assert file_path.exists()

    # Verify content
    loaded_df: pd.DataFrame = pd.read_excel(file_path)
    pd.testing.assert_frame_equal(loaded_df, sample_dataframe)


def test_save_data_parquet(tmp_path: Path, sample_dataframe: pd.DataFrame) -> None:
    """Test saving DataFrame to Parquet format."""
    pytest.skip("pyarrow library is not installed") if not is_installed("pyarrow") else None

    file_path: Path = tmp_path / "output.parquet"
    dt.save_data(sample_dataframe, file_path, fmt="parquet")
    assert file_path.exists()

    # Verify content
    loaded_df: pd.DataFrame = pd.read_parquet(file_path)
    pd.testing.assert_frame_equal(loaded_df, sample_dataframe)


def test_save_data_unsupported_format(tmp_path: Path, sample_dataframe: pd.DataFrame) -> None:
    """Test handling of unsupported file formats."""
    file_path: Path = tmp_path / "output.json"
    with pytest.raises(ValueError, match="Unsupported format"):
        dt.save_data(sample_dataframe, file_path, fmt="json")


def test_save_data_invalid_path(sample_dataframe: pd.DataFrame) -> None:
    """Test error handling for invalid save path."""
    with pytest.raises(OSError, match="Cannot save file into a non-existent directory"):
        dt.save_data(sample_dataframe, "/nonexistent/path/file.csv", fmt="csv")


# =====================
# Format Compatibility Tests
# =====================
def test_load_save_roundtrip_csv(tmp_path: Path, sample_dataframe: pd.DataFrame) -> None:
    """Test complete roundtrip: save to CSV then load back."""
    file_path = tmp_path / "roundtrip.csv"

    # Save
    dt.save_data(sample_dataframe, file_path, fmt="csv")

    # Load
    loaded_df = dt.load_csv(file_path)

    # Verify
    pd.testing.assert_frame_equal(loaded_df, sample_dataframe)


def test_load_save_roundtrip_excel(tmp_path: Path, sample_dataframe: pd.DataFrame) -> None:
    """Test complete roundtrip: save to Excel then load back."""
    pytest.skip("openpyxl library is not installed") if not is_installed("openpyxl") else None

    file_path = tmp_path / "roundtrip.xlsx"

    # Save
    dt.save_data(sample_dataframe, file_path, fmt="excel")

    # Load
    loaded_df = dt.load_excel(file_path)

    # Verify (note: Excel may change dtypes slightly)
    assert loaded_df.shape == sample_dataframe.shape
    assert list(loaded_df.columns) == list(sample_dataframe.columns)

    # Check numeric columns
    assert loaded_df["id"].tolist() == sample_dataframe["id"].tolist()
    assert loaded_df["score"].tolist() == pytest.approx(sample_dataframe["score"].tolist())


def test_load_save_roundtrip_parquet(tmp_path: Path, sample_dataframe: pd.DataFrame) -> None:
    """Test complete roundtrip: save to Parquet then load back."""
    pytest.skip("pyarrow library is not installed") if not is_installed("pyarrow") else None

    file_path = tmp_path / "roundtrip.parquet"

    # Save
    dt.save_data(sample_dataframe, file_path, fmt="parquet")

    # Load
    loaded_df = pd.read_parquet(file_path)

    # Verify (Parquet preserves exact dtypes)
    pd.testing.assert_frame_equal(loaded_df, sample_dataframe)


# =====================
# Edge Case Tests
# =====================
def test_save_empty_dataframe(tmp_path: Path) -> None:
    """Test saving an empty DataFrame."""
    empty_df = pd.DataFrame(columns=["A", "B", "C"])
    file_path = tmp_path / "empty.csv"

    dt.save_data(empty_df, file_path, fmt="csv")
    assert file_path.exists()

    loaded_df = pd.read_csv(file_path)
    assert loaded_df.shape == (0, 3)
    assert list(loaded_df.columns) == ["A", "B", "C"]


def test_load_empty_csv(tmp_path: Path) -> None:
    """Test loading an empty CSV file."""
    file_path = tmp_path / "empty.csv"
    file_path.write_text("col1,col2,col3\n")  # Header only

    df = dt.load_csv(file_path)
    assert df.shape == (0, 3)
    assert list(df.columns) == ["col1", "col2", "col3"]


@pytest.mark.parametrize("fmt", ["csv", "excel", "parquet"])
def test_save_with_different_dtypes(tmp_path: Path, fmt: str) -> None:
    """Test saving DataFrames with various data types."""
    pytest.skip("openpyxl library is not installed") if fmt == "excel" and not is_installed("openpyxl") else None
    pytest.skip("pyarrow library is not installed") if fmt == "parquet" and not is_installed("pyarrow") else None

    # Create DataFrame with mixed types
    df = pd.DataFrame(
        {
            "int_col": [1, 2, 3],
            "float_col": [1.1, 2.2, 3.3],
            "str_col": ["a", "b", "c"],
            "bool_col": [True, False, True],
            "datetime_col": pd.date_range("2023-01-01", periods=3),
        }
    )

    file_path = tmp_path / f"mixed_types.{fmt}"
    dt.save_data(df, file_path, fmt=fmt)
    assert file_path.exists()
