"""Test module for rate function from fabricatio-diff Rust bindings.

This module contains pytest test cases verifying the correctness of the
normalized Damerau-Levenshtein distance calculation for string similarity.
"""

import pytest
from fabricatio_diff.rust import rate


class TestRateFunction:
    """Test suite for the rate() function."""

    def test_identical_strings(self) -> None:
        """Test that identical strings return a similarity of 1.0."""
        assert rate("hello", "hello") == 1.0
        assert rate("world", "world") == 1.0
        assert rate("", "") == 1.0

    def test_completely_different_strings(self) -> None:
        """Test that completely different strings return low similarity."""
        result = rate("abc", "xyz")
        assert result < 0.5
        assert result >= 0.0

    def test_single_character_difference(self) -> None:
        """Test strings differing by one character."""
        result = rate("hello", "hallo")
        assert 0.7 < result < 1.0

    def test_case_sensitivity(self) -> None:
        """Test that rate is case-sensitive."""
        assert rate("Hello", "hello") != 1.0
        assert rate("Hello", "HELLO") != 1.0

    def test_empty_string(self) -> None:
        """Test behavior with empty strings."""
        assert rate("", "") == 1.0
        result = rate("hello", "")
        assert 0.0 <= result < 1.0

    def test_whitespace_differences(self) -> None:
        """Test strings with whitespace variations."""
        result = rate("hello world", "hello  world")
        assert 0.0 < result < 1.0

    def test_word_order_change(self) -> None:
        """Test strings with changed word order."""
        result = rate("hello world", "world hello")
        assert 0.0 < result < 1.0

    def test_substring_similarity(self) -> None:
        """Test when one string is a substring of another."""
        result = rate("hello", "hello world")
        # "hello" vs "hello world" - some similarity but not high
        assert 0.0 < result < 1.0

    def test_numeric_strings(self) -> None:
        """Test with numeric strings."""
        assert rate("123", "123") == 1.0
        result = rate("123", "456")
        assert result < 1.0

    def test_special_characters(self) -> None:
        """Test with special characters."""
        assert rate("!@#$", "!@#$") == 1.0
        result = rate("!@#$", "%^&*")
        assert result < 1.0

    def test_similar_long_strings(self) -> None:
        """Test similarity of longer similar strings."""
        a = "The quick brown fox jumps over the lazy dog"
        b = "The quick brown fox jumps over the lazy cat"
        result = rate(a, b)
        assert 0.9 < result < 1.0

    def test_transposition_similarity(self) -> None:
        """Test strings with transposed characters (Damerau-Levenshtein strength)."""
        # 'hlelo' vs 'hello' - one transposition
        result = rate("hlelo", "hello")
        assert 0.7 < result < 1.0

    def test_insertion_similarity(self) -> None:
        """Test strings with character insertion."""
        result = rate("hello", "helloo")
        assert 0.8 < result < 1.0

    def test_deletion_similarity(self) -> None:
        """Test strings with character deletion."""
        result = rate("hello", "hell")
        assert 0.7 < result <= 1.0
