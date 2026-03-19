"""Test suite for DataSynToolbox in fabricatio_plot package.

This test suite covers the simplified synthetic data generation functions:
- Direct column generation (numeric, categorical, datetime, text)
- Post-processing operations on Series (correlation, missing values)
- Integration workflow (combining series into DataFrame)
- Error handling for invalid inputs

Each test ensures correct behavior of the corresponding function,
including proper error handling and reproducibility via np.random.seed.
"""

import numpy as np
import pandas as pd
import pytest
from fabricatio_plot.toolboxes import synthesize as dt


# =====================
# Column Generation Tests
# =====================
def test_numeric_column_uniform() -> None:
    """Test generating numeric column with uniform distribution."""
    np.random.seed(42)
    series = dt.numeric_column(n_rows=1000, low=10.0, high=20.0)

    assert len(series) == 1000
    assert series.min() >= 10.0
    assert series.max() <= 20.0
    assert series.dtype == np.float64


def test_numeric_column_normal() -> None:
    """Test generating numeric column with normal distribution."""
    np.random.seed(42)
    series = dt.normal_column(n_rows=1000, mean=100.0, std=15.0)

    assert len(series) == 1000
    # Allow some variance for random generation
    assert 90.0 <= series.mean() <= 110.0
    assert 10.0 <= series.std() <= 20.0


def test_categorical_column() -> None:
    """Test generating categorical column."""
    np.random.seed(42)
    categories = ["High", "Medium", "Low"]
    series = dt.categorical_column(n_rows=1000, categories=categories)

    assert len(series) == 1000
    assert set(series.unique()).issubset(set(categories))
    # Check distribution is roughly reasonable (not empty)
    assert all(series.value_counts() > 0)


def test_datetime_column() -> None:
    """Test generating datetime column."""
    np.random.seed(42)
    series = dt.datetime_column(n_rows=100, start="2022-01-01", end="2022-12-31")

    assert len(series) == 100
    assert pd.api.types.is_datetime64_any_dtype(series)
    assert series.min() >= pd.Timestamp("2022-01-01")
    assert series.max() <= pd.Timestamp("2022-12-31")


def test_text_column() -> None:
    """Test generating text column."""
    np.random.seed(42)
    series = dt.text_column(n_rows=10, prefix="prod_")

    assert len(series) == 10
    for text in series:
        assert isinstance(text, str)
        assert text.startswith("prod_")
        assert len(text) > len("prod_")


# =====================
# Post-Processing Tests (Series Level)
# =====================
def test_correlated_column() -> None:
    """Test generating a column correlated with a base series."""
    np.random.seed(42)
    base = dt.numeric_column(n_rows=1000, low=0, high=100)
    correlated = dt.correlated_column(base_series=base, correlation=0.8)

    assert len(correlated) == 1000
    assert correlated.index.equals(base.index)

    # Check correlation coefficient
    actual_corr = base.corr(correlated)
    assert actual_corr == pytest.approx(0.8, abs=0.05)


def test_correlated_column_invalid_value() -> None:
    """Test error handling for invalid correlation values."""
    base = pd.Series([1, 2, 3, 4, 5])

    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        dt.correlated_column(base_series=base, correlation=1.5)

    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        dt.correlated_column(base_series=base, correlation=-0.1)


def test_inject_missing() -> None:
    """Test injecting missing values into a series."""
    np.random.seed(42)
    series = pd.Series(range(100))
    missing_series = dt.inject_missing(series=series, rate=0.1)

    assert len(missing_series) == 100
    assert missing_series.isnull().sum() > 0

    # Approximate rate check
    actual_rate = missing_series.isnull().sum() / 100
    assert actual_rate == pytest.approx(0.1, abs=0.03)


def test_inject_missing_invalid_rate() -> None:
    """Test error handling for invalid missing rate."""
    series = pd.Series([1, 2, 3])

    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        dt.inject_missing(series=series, rate=1.5)


# =====================
# Reproducibility Tests
# =====================
def test_reproducible_generation() -> None:
    """Test that generation is reproducible with same seed."""
    np.random.seed(123)
    series1 = dt.numeric_column(n_rows=50, low=0, high=1)

    np.random.seed(123)
    series2 = dt.numeric_column(n_rows=50, low=0, high=1)

    pd.testing.assert_series_equal(series1, series2)


def test_different_seeds_produce_different_results() -> None:
    """Test that different seeds produce different results."""
    np.random.seed(1)
    series1 = dt.numeric_column(n_rows=10, low=0, high=1)

    np.random.seed(2)
    series2 = dt.numeric_column(n_rows=10, low=0, high=1)

    assert not series1.equals(series2)


# =====================
# Integration Tests
# =====================
def test_complete_workflow() -> None:
    """Test complete synthetic data generation workflow by combining series."""
    np.random.seed(42)
    n_rows = 200

    # Generate individual columns
    col_id = dt.text_column(n_rows=n_rows, prefix="PROD-")
    col_region = dt.categorical_column(n_rows=n_rows, categories=["North", "South"])
    col_sales = dt.numeric_column(n_rows=n_rows, low=100, high=5000)
    col_date = dt.datetime_column(n_rows=n_rows, start="2023-01-01", end="2023-12-31")

    # Assemble DataFrame
    df = pd.DataFrame(
        {
            "product_id": col_id,
            "region": col_region,
            "sales": col_sales,
            "date": col_date,
        }
    )

    # Add correlated column (e.g., revenue based on sales)
    col_revenue = dt.correlated_column(base_series=df["sales"], correlation=0.9)
    df["revenue"] = col_revenue

    # Inject missing values into specific columns
    df["sales"] = dt.inject_missing(series=df["sales"], rate=0.05)

    # Validate final result
    assert df.shape == (200, 5)
    assert set(df.columns) == {"product_id", "region", "sales", "date", "revenue"}
    assert df["product_id"].str.startswith("PROD-").all()
    assert pd.api.types.is_datetime64_any_dtype(df["date"])
    assert df["sales"].isnull().sum() > 0
    assert df["sales"].corr(df["revenue"]) == pytest.approx(0.9, abs=0.05)


def test_empty_column_generation() -> None:
    """Test handling of zero rows."""
    np.random.seed(42)
    series = dt.numeric_column(n_rows=0, low=0, high=1)
    assert len(series) == 0
    assert isinstance(series, pd.Series)
