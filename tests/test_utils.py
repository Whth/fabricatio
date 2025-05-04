import pytest
from fabricatio import utils


def test_is_subclass_of_base():
    class Base:
        pass

    class Child(Base):
        pass

    assert utils.is_subclass_of_base(Child, __name__, "Base") is True
    assert utils.is_subclass_of_base(int, __name__, "Base") is False


def test_is_subclass_of_any_base():
    class Base1:
        pass

    class Base2:
        pass

    class Child(Base1, Base2):
        pass

    bases = [(__name__, "Base1"), (__name__, "Base2")]

    assert utils.is_subclass_of_any_base(Child, bases) is True
    assert utils.is_subclass_of_any_base(int, bases) is False


def test_override_kwargs():
    base = {"a": 1, "b": 2}
    overrides = {"b": 3, "c": 4}

    result = utils.override_kwargs(base, **overrides)

    # Verify that overrides are applied and original is preserved
    assert result == {"a": 1, "b": 3, "c": 4}


def test_fallback_kwargs():
    base = {"a": 1}
    fallbacks = {"b": 2, "c": 3}

    # Test when only some keys exist
    result = utils.fallback_kwargs(base, **fallbacks)
    assert result == {"a": 1, "b": 2, "c": 3}

    # Test when some keys already exist
    base = {"a": 1, "b": 4}
    result = utils.fallback_kwargs(base, **fallbacks)
    assert result == {"a": 1, "b": 4, "c": 3}


def test_ok():
    # Test with non-None value
    assert utils.ok("value") == "value"

    # Test with None value should raise ValueError
    with pytest.raises(ValueError):
        utils.ok(None)


def test_first_available():
    # Test with some None values
    assert utils.first_available([None, None, "value", "another"]) == "value"
    assert utils.first_available([1, 2, 3]) == 1

    # Test with all None should raise ValueError
    with pytest.raises(ValueError):
        utils.first_available([None, None])


def test_wrapp_in_block():
    content = "This is the content"
    title = "testBlock"

    result = utils.wrapp_in_block(content, title)

    # Test that the block wrapping works correctly
    assert result.startswith("--- Start of testBlock ---")
    assert content in result
    assert result.endswith("--- End of testBlock ---")


def test_wrapp_in_block_with_style():
    content = "This is the content"
    title = "styledBlock"

    result = utils.wrapp_in_block(content, title, "=")

    # Test that the block wrapping uses the specified style
    assert result.startswith("=== Start of styledBlock ===")
    assert content in result
    assert result.endswith("=== End of styledBlock ===")
