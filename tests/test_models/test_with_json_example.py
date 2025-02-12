import pytest

from fabricatio.models.generic import WithJsonExample


@pytest.fixture
def with_json_example():
    return WithJsonExample(json_example={"key": "value"})


def test_with_json_example_initialization(with_json_example):
    assert with_json_example.json_example == {"key": "value"}


def test_with_json_example_update_json_example(with_json_example):
    with_json_example.update_json_example({"new_key": "new_value"})
    assert with_json_example.json_example == {"new_key": "new_value"}
