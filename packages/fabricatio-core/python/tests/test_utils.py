"""Test module for utility functions.

This module contains test cases for the helper functions used across the project.
It ensures that the utility functions behave as expected under various scenarios.
"""

from fabricatio_core.utils import is_subclass_of_any_base, is_subclass_of_base


class TestClass:
    """Test class in test module."""

    pass


class BaseClass:
    """Base class in base module."""

    pass


class DerivedClass(BaseClass):
    """Derived class that inherits from BaseClass."""

    pass


class MultipleInheritanceClass(TestClass, BaseClass):
    """Class with multiple inheritance."""

    pass


def test_is_subclass_of_base_true() -> None:
    """Test is_subclass_of_base returns True for actual subclass."""
    result = is_subclass_of_base(DerivedClass, "test_utils", "BaseClass")
    assert result is True


def test_is_subclass_of_base_false() -> None:
    """Test is_subclass_of_base returns False for non-subclass."""
    result = is_subclass_of_base(TestClass, "test_utils", "BaseClass")
    assert result is False


def test_is_subclass_of_base_self() -> None:
    """Test is_subclass_of_base returns True for class itself."""
    result = is_subclass_of_base(BaseClass, "test_utils", "BaseClass")
    assert result is True


def test_is_subclass_of_base_multiple_inheritance() -> None:
    """Test is_subclass_of_base with multiple inheritance."""
    result = is_subclass_of_base(MultipleInheritanceClass, "test_utils", "BaseClass")
    assert result is True


def test_is_subclass_of_base_wrong_module() -> None:
    """Test is_subclass_of_base returns False for wrong module."""
    result = is_subclass_of_base(DerivedClass, "wrong_module", "BaseClass")
    assert result is False


def test_is_subclass_of_base_wrong_name() -> None:
    """Test is_subclass_of_base returns False for wrong class name."""
    result = is_subclass_of_base(DerivedClass, "test_utils", "WrongClass")
    assert result is False


def test_is_subclass_of_any_base_true_single() -> None:
    """Test is_subclass_of_any_base returns True for single matching base."""
    bases = [("test_utils", "BaseClass")]
    result = is_subclass_of_any_base(DerivedClass, bases)
    assert result is True


def test_is_subclass_of_any_base_true_multiple() -> None:
    """Test is_subclass_of_any_base returns True with multiple bases."""
    bases = [("test_utils", "TestClass"), ("test_utils", "BaseClass")]
    result = is_subclass_of_any_base(MultipleInheritanceClass, bases)
    assert result is True


def test_is_subclass_of_any_base_false() -> None:
    """Test is_subclass_of_any_base returns False for non-matching bases."""
    bases = [("wrong_module", "BaseClass"), ("test_utils", "WrongClass")]
    result = is_subclass_of_any_base(DerivedClass, bases)
    assert result is False


def test_is_subclass_of_any_base_empty_list() -> None:
    """Test is_subclass_of_any_base returns False for empty bases list."""
    bases = []
    result = is_subclass_of_any_base(DerivedClass, bases)
    assert result is False


def test_is_subclass_of_any_base_first_match() -> None:
    """Test is_subclass_of_any_base returns True on first match."""
    bases = [("test_utils", "BaseClass"), ("wrong_module", "WrongClass")]
    result = is_subclass_of_any_base(DerivedClass, bases)
    assert result is True
