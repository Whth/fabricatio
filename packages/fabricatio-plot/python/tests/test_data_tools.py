"""Test suite for data processing functions in the fabricatio_plot package.

This test suite covers functionality related to:
- Data loading from CSV and Excel files
- Data saving operations
- Column name retrieval
- Data summarization
- Missing value handling
- Column normalization
- Groupby aggregation
- Data sampling

Each test ensures correct behavior of the corresponding function,
including proper error handling for invalid inputs.
"""

from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from fabricatio_core.rust import is_installed
from fabricatio_plot.toolboxes import data as dt


# =====================
# Test Data Setup
# =====================
@pytest.fixture
def sample_dataframe() -> pd.DataFrame:
    """Create a sample DataFrame for testing."""
    return pd.DataFrame(
        {
            "numeric": [1, 2, 3, None, 5],
            "categorical": ["A", "B", "A", "C", None],
            "date": ["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04", "2023-01-05"],
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


# =====================
# Data Loading & Saving Tests
# =====================
def test_load_csv(temp_csv: Path) -> None:
    """Test loading data from CSV file."""
    df: pd.DataFrame = dt.load_csv(str(temp_csv))
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["col1", "col2"]
    assert df.shape == (2, 2)


def test_load_csv_path_object(temp_csv: Path) -> None:
    """Test loading CSV using Path object."""
    df: pd.DataFrame = dt.load_csv(temp_csv)
    assert df.shape == (2, 2)


def test_load_excel(temp_excel: Path) -> None:
    """Test loading data from Excel file."""
    df: pd.DataFrame = dt.load_excel(str(temp_excel))
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["col1", "col2"]
    assert df.shape == (2, 2)


def test_load_excel_sheet_name(temp_excel: Path) -> None:
    """Test loading specific Excel sheet."""
    df: pd.DataFrame = dt.load_excel(str(temp_excel), sheet_name="Sheet1")
    assert df.shape == (2, 2)


def test_save_data_csv(tmp_path: Path, sample_dataframe: pd.DataFrame) -> None:
    """Test saving DataFrame to CSV format."""
    file_path: Path = tmp_path / "output.csv"
    dt.save_data(sample_dataframe, file_path, fmt="csv")
    assert file_path.exists()
    loaded_df: pd.DataFrame = pd.read_csv(file_path)
    assert loaded_df.equals(sample_dataframe)


def test_save_data_excel(tmp_path: Path, sample_dataframe: pd.DataFrame) -> None:
    """Test saving DataFrame to Excel format."""
    pytest.skip("openpyxl library is not installed") if not is_installed("openpyxl") else None

    file_path: Path = tmp_path / "output.xlsx"
    dt.save_data(sample_dataframe, file_path, fmt="excel")
    assert file_path.exists()
    loaded_df: pd.DataFrame = pd.read_excel(file_path)
    assert loaded_df.equals(sample_dataframe)


def test_save_data_invalid_format(tmp_path: Path, sample_dataframe: pd.DataFrame) -> None:
    """Test handling of unsupported file formats."""
    file_path: Path = tmp_path / "output.json"
    with pytest.raises(ValueError, match="Unsupported format"):
        dt.save_data(sample_dataframe, file_path, fmt="json")


def test_get_column_names(sample_dataframe: pd.DataFrame) -> None:
    """Test retrieving column names."""
    columns: list[str] = dt.get_column_names(sample_dataframe)
    assert columns == ["numeric", "categorical", "date"]


# =====================
# Data Exploration & Summary Tests
# =====================
def test_get_data_summary(sample_dataframe: pd.DataFrame) -> None:
    """Test data summary generation."""
    summary: dict[str, Any] = dt.get_data_summary(sample_dataframe)

    assert summary["shape"] == (5, 3)
    assert summary["dtypes"] == {"numeric": "float64", "categorical": "object", "date": "object"}

    # Verify numeric summary
    assert "mean" in summary["numeric_summary"]["numeric"]
    assert summary["numeric_summary"]["numeric"]["mean"] == pytest.approx(2.75)

    # Verify categorical summary
    cat_summary = summary["categorical_summary"]["categorical"]
    assert cat_summary["unique_count"] == 3
    assert cat_summary["top_value"] == "A"


# =====================
# Data Cleaning & Transformation Tests
# =====================
def test_handle_missing_values_drop(sample_dataframe: pd.DataFrame) -> None:
    """Test dropping missing values."""
    cleaned: pd.DataFrame = dt.handle_missing_values(sample_dataframe, strategy="drop")
    assert cleaned.shape == (3, 3)
    assert cleaned.isnull().sum().sum() == 0


def test_handle_missing_values_fill(sample_dataframe: pd.DataFrame) -> None:
    """Test filling missing values."""
    cleaned: pd.DataFrame = dt.handle_missing_values(sample_dataframe, strategy="fill", fill_value=0)
    assert cleaned.isnull().sum().sum() == 0
    assert cleaned["numeric"].iloc[3] == 0
    assert cleaned["categorical"].iloc[4] == 0


def test_handle_missing_values_invalid(sample_dataframe: pd.DataFrame) -> None:
    """Test invalid missing value strategy."""
    with pytest.raises(ValueError, match="Invalid strategy"):
        dt.handle_missing_values(sample_dataframe, strategy="invalid")


def test_normalize_column(sample_dataframe: pd.DataFrame) -> None:
    """Test column normalization."""
    # Min-max normalization
    normalized: pd.DataFrame = dt.normalize_column(sample_dataframe, "numeric", "minmax")
    assert normalized["numeric"].min() == 0.0
    assert normalized["numeric"].max() == 1.0
    assert normalized["numeric"].iloc[0] == pytest.approx(0.0)
    assert normalized["numeric"].iloc[4] == pytest.approx(1.0)

    # Z-score normalization
    normalized = dt.normalize_column(sample_dataframe, "numeric", "zscore")
    assert normalized["numeric"].mean() == pytest.approx(0.0)
    assert normalized["numeric"].std() == pytest.approx(1.0)


def test_normalize_invalid_column(sample_dataframe: pd.DataFrame) -> None:
    """Test normalization of non-numeric column."""
    with pytest.raises(ValueError, match="must be numeric"):
        dt.normalize_column(sample_dataframe, "categorical", "minmax")


def test_normalize_invalid_method(sample_dataframe: pd.DataFrame) -> None:
    """Test invalid normalization method."""
    with pytest.raises(ValueError, match="Invalid method"):
        dt.normalize_column(sample_dataframe, "numeric", "invalid")


# =====================
# Data Analysis & Aggregation Tests
# =====================


def test_groupby_aggregate(sample_dataframe: pd.DataFrame) -> None:
    """Test groupby aggregation."""
    # Add more data for better aggregation
    df = pd.concat([sample_dataframe] * 2, ignore_index=True)

    grouped: pd.DataFrame = dt.groupby_aggregate(
        df, group_column="categorical", agg_columns=["numeric"], agg_functions=["sum", "mean"]
    )

    # Handle MultiIndex columns if they exist by flattening them
    grouped.columns = ["_".join(col).strip("_") for col in grouped.columns.values]

    assert set(grouped.columns) == {"categorical", "numeric_sum", "numeric_mean"}
    assert grouped[grouped["categorical"] == "A"]["numeric_sum"].iloc[0] == 8.0


def test_groupby_missing_column(sample_dataframe: pd.DataFrame) -> None:
    """Test groupby with missing columns."""
    with pytest.raises(ValueError, match="Columns not found"):
        dt.groupby_aggregate(
            sample_dataframe, group_column="categorical", agg_columns=["missing"], agg_functions=["sum"]
        )


# =====================
# Data Sampling & Splitting Tests
# =====================
def test_sample_data_n(sample_dataframe: pd.DataFrame) -> None:
    """Test sampling by number of rows."""
    sampled: pd.DataFrame = dt.sample_data(sample_dataframe, n=2)
    assert sampled.shape == (2, 3)


def test_sample_data_frac(sample_dataframe: pd.DataFrame) -> None:
    """Test sampling by fraction."""
    sampled: pd.DataFrame = dt.sample_data(sample_dataframe, frac=0.4)
    assert sampled.shape == (2, 3)


def test_sample_data_random_state(sample_dataframe: pd.DataFrame) -> None:
    """Test reproducible sampling with random state."""
    sampled1: pd.DataFrame = dt.sample_data(sample_dataframe, n=3, random_state=42)
    sampled2: pd.DataFrame = dt.sample_data(sample_dataframe, n=3, random_state=42)
    assert sampled1.equals(sampled2)


def test_sample_data_invalid_params(sample_dataframe: pd.DataFrame) -> None:
    """Test invalid sampling parameters."""
    with pytest.raises(ValueError, match="Either 'n' or 'frac' must be specified"):
        dt.sample_data(sample_dataframe)
